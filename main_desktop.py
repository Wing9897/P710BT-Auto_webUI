"""Brother Label Printer — PyQt6 Desktop Application.

Single-file GUI that reuses the existing backend modules for
data parsing, label rendering, USB printer communication, etc.
"""
from __future__ import annotations

import sys
import os
import io
import logging

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QComboBox, QLineEdit,
    QSpinBox, QFileDialog, QTableWidget, QTableWidgetItem, QGroupBox,
    QSplitter, QMessageBox, QSizePolicy, QCheckBox, QScrollArea,
    QProgressBar, QDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor

from app.services.data_parser import parse_auto
from app.services.label_renderer import (
    LabelSpec, FieldSpec, FieldType, render_label, list_available_fonts,
)
from app.printer.transport import USBTransport
from app.printer.protocol import BrotherPrinter
from app.printer.constants import TAPE_WIDTHS_MM, USBID_BROTHER, SupportedPrinterIDs

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

FIELD_TYPES = ["text", "qr", "code128", "code39", "ean13"]
FIELD_TYPE_LABELS = {"text": "文字", "qr": "QR Code", "code128": "CODE128",
                     "code39": "CODE39", "ean13": "EAN13"}


# ── Worker Threads ──────────────────────────────────────────────────────────

class PrintWorker(QThread):
    """Background thread for printing labels."""
    progress = pyqtSignal(int, int)        # (current, total)
    label_done = pyqtSignal(int, str)      # (index, status_msg)
    finished_all = pyqtSignal(int, int)    # (printed, total)
    error = pyqtSignal(str)

    def __init__(self, specs: list[LabelSpec], serial: str | None, margin_px: int,
                 chain_print: bool = False):
        super().__init__()
        self.specs = specs
        self.serial = serial
        self.margin_px = margin_px
        self.chain_print = chain_print

    def run(self):
        try:
            transport = USBTransport(self.serial)
            printer = BrotherPrinter(transport)
            printer.connect()
        except Exception as e:
            self.error.emit(f"連線印表機失敗：{e}")
            return

        printed = 0
        total = len(self.specs)
        try:
            for i, spec in enumerate(self.specs):
                try:
                    image = render_label(spec)
                    last_page = (i == total - 1)
                    printer.print_image(
                        image, self.margin_px,
                        last_page=last_page,
                        chain_print=self.chain_print,
                    )
                    printed += 1
                    self.label_done.emit(i, "ok")
                except Exception as e:
                    self.label_done.emit(i, str(e))
                self.progress.emit(i + 1, total)
            self.finished_all.emit(printed, total)
        finally:
            printer.close()


class PreviewWorker(QThread):
    """Background thread for rendering label previews."""
    images_ready = pyqtSignal(list)  # list of bytes (PNG)

    def __init__(self, specs: list[LabelSpec]):
        super().__init__()
        self.specs = specs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        for spec in self.specs[:10]:
            if self._cancelled:
                return
            try:
                img = render_label(spec)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                results.append(buf.getvalue())
            except Exception as e:
                log.warning("Preview render failed: %s", e)
        if not self._cancelled:
            self.images_ready.emit(results)


class ParseWorker(QThread):
    """Background thread for parsing data files / text."""
    parsed = pyqtSignal(list)   # list[dict]
    error = pyqtSignal(str)

    def __init__(self, *, path: str | None = None, text: str | None = None,
                 fmt: str = "csv", delimiter: str | None = None):
        super().__init__()
        self._path = path
        self._text = text
        self._fmt = fmt
        self._delimiter = delimiter

    def run(self):
        try:
            if self._path:
                with open(self._path, "rb") as f:
                    raw = f.read()
                ext = os.path.splitext(self._path)[1].lower()
                if ext == ".xls":
                    raise ValueError(".xls 舊格式不支援，請先另存為 .xlsx 再匯入")
                elif ext == ".xlsx":
                    rows = parse_auto(file_bytes=raw, format="excel")
                elif ext == ".json":
                    rows = parse_auto(text=raw.decode("utf-8", errors="replace"), format="json")
                else:
                    rows = parse_auto(text=raw.decode("utf-8", errors="replace"), format="csv")
            else:
                rows = parse_auto(text=self._text, format=self._fmt, delimiter=self._delimiter)
            self.parsed.emit(rows)
        except Exception as e:
            self.error.emit(str(e))


class USBScanWorker(QThread):
    """Background thread for USB printer discovery + tape detection."""
    printers_found = pyqtSignal(list)           # list[dict]
    tape_detected = pyqtSignal(int, str)        # (width_mm, serial)

    def __init__(self, serial: str | None = None, detect_tape: bool = False):
        super().__init__()
        self._serial = serial
        self._detect_tape = detect_tape

    def run(self):
        # Discover printers
        found = []
        try:
            import usb.core
            try:
                import libusb_package
                backend = libusb_package.get_libusb1_backend()
            except ImportError:
                backend = None
            for pid in SupportedPrinterIDs:
                dev = usb.core.find(idVendor=USBID_BROTHER, idProduct=pid, backend=backend)
                if dev:
                    found.append({
                        "product": dev.product or pid.name,
                        "serial": dev.serial_number or "",
                        "manufacturer": dev.manufacturer or "",
                    })
        except Exception as e:
            log.warning("USB discovery failed: %s", e)

        self.printers_found.emit(found)

        # Optionally detect tape width
        if self._detect_tape and (found or self._serial is not None):
            serial = self._serial if self._serial else (found[0]["serial"] if found else None)
            try:
                transport = USBTransport(serial)
                printer = BrotherPrinter(transport)
                printer.connect()
                status = printer.status
                printer.close()
                if status and status.media_width > 0:
                    self.tape_detected.emit(status.media_width, serial or "")
            except Exception:
                pass


# ── Data Import Panel ───────────────────────────────────────────────────────

class DataImportPanel(QWidget):
    # emits (columns, field_types, data_rows)
    data_parsed = pyqtSignal(list, list, list)

    def __init__(self):
        super().__init__()
        self.columns: list[str] = []
        self.data_rows: list[dict] = []
        self.selected_columns: list[str] = []
        self._col_checkboxes: list[QCheckBox] = []
        self._type_combos: list[QComboBox] = []
        self._parse_worker: ParseWorker | None = None
        self._pending_filename: str | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── 貼上輸入 block ──
        paste_box = QGroupBox("📋 貼上輸入")
        paste_layout = QVBoxLayout(paste_box)
        paste_layout.setSpacing(4)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("格式："))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JSON", "CSV", "自定義分隔符"])
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_row.addWidget(self.format_combo)
        self.delim_edit = QLineEdit()
        self.delim_edit.setPlaceholderText("分隔符")
        self.delim_edit.setFixedWidth(55)
        self.delim_edit.hide()
        fmt_row.addWidget(self.delim_edit)
        fmt_row.addStretch()
        paste_layout.addLayout(fmt_row)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "貼上資料...\n"
            '例如 JSON: [{"name":"A","value":"1"}]\n'
            "例如 CSV:\nname,value\nA,1"
        )
        paste_layout.addWidget(self.text_edit, 1)

        self.paste_btn = QPushButton("解析")
        self.paste_btn.clicked.connect(self._parse_text)
        paste_layout.addWidget(self.paste_btn)

        layout.addWidget(paste_box)

        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #dc2626; font-size: 11px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # ── 資料預覽 block (with file button in toolbar) ──
        table_box = QGroupBox("📊 資料預覽")
        table_layout = QVBoxLayout(table_box)
        table_layout.setSpacing(4)

        # Toolbar: file button + filename + delete button
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.file_btn = QPushButton("📁 開啟檔案")
        self.file_btn.setFixedWidth(100)
        self.file_btn.clicked.connect(self._open_file)
        toolbar.addWidget(self.file_btn)
        self.file_path_label = QLabel("支援 Excel / JSON / CSV")
        self.file_path_label.setStyleSheet("color: gray; font-size: 11px;")
        toolbar.addWidget(self.file_path_label, 1)
        self.delete_btn = QPushButton("🗑️ 刪除選中")
        self.delete_btn.setFixedWidth(90)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("color: #dc2626;")
        self.delete_btn.clicked.connect(self._delete_selected_rows)
        toolbar.addWidget(self.delete_btn)
        table_layout.addLayout(toolbar)

        # Column selection row — horizontal scroll area
        self.col_select_widget = QWidget()
        self.col_select_layout = QHBoxLayout(self.col_select_widget)
        self.col_select_layout.setContentsMargins(2, 2, 2, 2)
        self.col_select_layout.setSpacing(6)

        self.col_scroll = QScrollArea()
        self.col_scroll.setWidget(self.col_select_widget)
        self.col_scroll.setWidgetResizable(True)
        self.col_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.col_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.col_scroll.setFixedHeight(46)
        self.col_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.col_scroll.hide()
        table_layout.addWidget(self.col_scroll)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.itemSelectionChanged.connect(
            lambda: self.delete_btn.setEnabled(bool(self.table.selectedItems()))
        )
        # Delete key support
        self.table.keyPressEvent = self._table_key_press
        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setHighlightSections(False)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.setStyleSheet("""
            QTableWidget {
                border: none;
                font-size: 12px;
                background: #ffffff;
                alternate-background-color: #f1f5f9;
                color: #111827;
            }
            QTableWidget::item {
                padding: 2px 6px;
            }
            QTableWidget::item:selected {
                background: #bfdbfe;
                color: #1e3a5f;
            }
            QHeaderView::section {
                background: #e2e8f0;
                border: none;
                border-bottom: 2px solid #94a3b8;
                border-right: 1px solid #cbd5e1;
                padding: 4px 6px;
                font-weight: bold;
                font-size: 11px;
                color: #1e293b;
            }
        """)
        table_layout.addWidget(self.table, 1)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: gray; font-size: 11px;")
        self.count_label.hide()
        table_layout.addWidget(self.count_label)

        layout.addWidget(table_box, 1)

    def _on_format_changed(self, idx):
        self.delim_edit.setVisible(idx == 2)

    def _format_key(self) -> str:
        return ["json", "csv", "delimited"][self.format_combo.currentIndex()]

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇資料檔案", "",
            "All supported (*.csv *.tsv *.json *.xlsx *.xls *.txt);;All files (*)"
        )
        if not path:
            return
        self._pending_filename = os.path.basename(path)
        self.file_path_label.setText(f"⏳ 載入中… {self._pending_filename}")
        self._start_parse(path=path)

    def _parse_text(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        self._pending_filename = None
        self._start_parse(text=text, fmt=self._format_key(),
                          delimiter=self.delim_edit.text() or None)

    def _start_parse(self, *, path: str | None = None, text: str | None = None,
                     fmt: str = "csv", delimiter: str | None = None):
        self.error_label.hide()
        self.paste_btn.setEnabled(False)
        self.file_btn.setEnabled(False)
        self._parse_worker = ParseWorker(path=path, text=text, fmt=fmt, delimiter=delimiter)
        self._parse_worker.parsed.connect(self._on_parse_done)
        self._parse_worker.error.connect(self._on_parse_error)
        self._parse_worker.finished.connect(self._parse_worker.deleteLater)
        self._parse_worker.start()

    def _on_parse_done(self, rows: list[dict]):
        self.paste_btn.setEnabled(True)
        self.file_btn.setEnabled(True)
        if self._pending_filename:
            self.file_path_label.setText(self._pending_filename)
        self._set_data(rows)

    def _on_parse_error(self, msg: str):
        self.paste_btn.setEnabled(True)
        self.file_btn.setEnabled(True)
        self.file_path_label.setText("支援 Excel / JSON / CSV")
        self._show_error(msg)

    def _set_data(self, rows: list[dict]):
        self.error_label.hide()
        if not rows:
            self._show_error("解析結果為空")
            return
        self.columns = list(rows[0].keys())
        self.data_rows = rows
        self.selected_columns = list(self.columns)
        self.delete_btn.setEnabled(False)
        self._build_column_checkboxes()
        self._update_table()
        self._emit_selected()

    def _build_column_checkboxes(self):
        """Build per-column: checkbox + field-type combo."""
        while self.col_select_layout.count():
            item = self.col_select_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        lbl = QLabel("列：")
        lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.col_select_layout.addWidget(lbl)

        self._col_checkboxes = []
        self._type_combos = []
        for col in self.columns:
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 4, 0)
            cell_layout.setSpacing(2)

            cb = QCheckBox(col)
            cb.setChecked(True)
            cell_layout.addWidget(cb)

            tc = QComboBox()
            for ft in FIELD_TYPES:
                tc.addItem(FIELD_TYPE_LABELS[ft], ft)
            tc.setFixedWidth(78)
            cell_layout.addWidget(tc)

            self.col_select_layout.addWidget(cell)
            self._col_checkboxes.append(cb)
            self._type_combos.append(tc)

        # Connect signals after all widgets are built to avoid spurious emissions
        for cb in self._col_checkboxes:
            cb.toggled.connect(self._on_column_toggled)
        for tc in self._type_combos:
            tc.currentIndexChanged.connect(self._emit_selected)

        self.col_select_layout.addStretch()
        self.col_scroll.show()

    def _on_column_toggled(self):
        self.selected_columns = [
            cb.text() for cb in self._col_checkboxes if cb.isChecked()
        ]
        # grey out type combo when column unchecked
        for cb, tc in zip(self._col_checkboxes, self._type_combos):
            tc.setEnabled(cb.isChecked())
        self._update_table()
        self._emit_selected()

    def _emit_selected(self):
        if not self.selected_columns:
            return
        field_types = [
            tc.currentData()
            for cb, tc in zip(self._col_checkboxes, self._type_combos)
            if cb.isChecked()
        ]
        self.data_parsed.emit(self.selected_columns, field_types, self.data_rows)

    def _update_table(self):
        display = self.data_rows[:50]
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(display))
        self.table.setColumnCount(len(self.columns) + 1)
        self.table.setHorizontalHeaderLabels(["#"] + self.columns)

        for r, row in enumerate(display):
            num = QTableWidgetItem(str(r + 1))
            num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setForeground(QColor("#94a3b8"))
            self.table.setItem(r, 0, num)
            for c, col in enumerate(self.columns):
                item = QTableWidgetItem(str(row.get(col, "")))
                if col not in self.selected_columns:
                    item.setForeground(QColor("#94a3b8"))
                    item.setBackground(QColor("#f1f5f9"))
                self.table.setItem(r, c + 1, item)

        # Fit columns, cap at 220px, # column fixed narrow
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 36)
        for c in range(1, self.table.columnCount()):
            if self.table.columnWidth(c) > 220:
                self.table.setColumnWidth(c, 220)

        self.table.setUpdatesEnabled(True)
        self.count_label.setText(
            f"共 {len(self.data_rows)} 筆資料　·　已選 {len(self.selected_columns)} / {len(self.columns)} 列"
        )
        self.count_label.show()

    def _table_key_press(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected_rows()
        else:
            QTableWidget.keyPressEvent(self.table, event)

    def _delete_selected_rows(self):
        selected = sorted(
            {idx.row() for idx in self.table.selectedIndexes()},
            reverse=True,
        )
        if not selected:
            return
        # Map table rows → data_rows indices (table shows first 50)
        for table_row in selected:
            if table_row < len(self.data_rows):
                self.data_rows.pop(table_row)
        self.selected_columns = [cb.text() for cb in self._col_checkboxes if cb.isChecked()]
        self._update_table()
        self._emit_selected()

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()


# ── Label Editor Panel ──────────────────────────────────────────────────────

class LabelEditorPanel(QGroupBox):
    label_changed = pyqtSignal()

    def __init__(self):
        super().__init__("✏️ 標籤設定")
        self.tape_width_mm = 24
        self.font_name: str | None = None
        self.font_size: int | None = None
        self.margin_px = 8
        self.spacing_px = 6
        # fields & mapping set externally via set_fields()
        self._fields: list[dict] = []
        self._init_ui()
        self._load_fonts()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("膠帶："))
        self.tape_combo = QComboBox()
        self.tape_combo.addItems([f"{w}mm" for w in TAPE_WIDTHS_MM])
        self.tape_combo.setCurrentIndex(TAPE_WIDTHS_MM.index(24))
        self.tape_combo.currentIndexChanged.connect(self._on_settings_changed)
        layout.addWidget(self.tape_combo)

        layout.addWidget(QLabel("字型："))
        self.font_combo = QComboBox()
        self.font_combo.addItem("預設", None)
        self.font_combo.currentIndexChanged.connect(self._on_settings_changed)
        layout.addWidget(self.font_combo)

        layout.addWidget(QLabel("大小："))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(0, 200)
        self.font_size_spin.setSpecialValueText("自動")
        self.font_size_spin.setValue(0)
        self.font_size_spin.setFixedWidth(55)
        self.font_size_spin.valueChanged.connect(self._on_settings_changed)
        layout.addWidget(self.font_size_spin)

        layout.addWidget(QLabel("邊距："))
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 50)
        self.margin_spin.setValue(8)
        self.margin_spin.setFixedWidth(50)
        self.margin_spin.valueChanged.connect(self._on_settings_changed)
        layout.addWidget(self.margin_spin)

        layout.addStretch()

    def _load_fonts(self):
        """Load fonts in a background thread to avoid blocking UI startup."""
        def _worker():
            try:
                fonts = list_available_fonts()
            except Exception:
                return
            def _add():
                for f in fonts:
                    self.font_combo.addItem(f, f)
            QTimer.singleShot(0, _add)
        from threading import Thread
        Thread(target=_worker, daemon=True).start()

    def _on_settings_changed(self):
        self.tape_width_mm = TAPE_WIDTHS_MM[self.tape_combo.currentIndex()]
        self.font_name = self.font_combo.currentData()
        self.font_size = self.font_size_spin.value() or None
        self.margin_px = self.margin_spin.value()
        self.label_changed.emit()

    def set_tape_width(self, width_mm: int):
        if width_mm in TAPE_WIDTHS_MM:
            self.tape_width_mm = width_mm
            self.tape_combo.blockSignals(True)
            self.tape_combo.setCurrentIndex(TAPE_WIDTHS_MM.index(width_mm))
            self.tape_combo.blockSignals(False)
            self.label_changed.emit()

    def set_fields(self, columns: list[str], field_types: list[str]):
        """Called when data import panel updates column/type selection."""
        self._fields = [
            {"col": col, "field_type": ft}
            for col, ft in zip(columns, field_types)
        ]
        self.label_changed.emit()

    def build_label_spec(self, row: dict | None = None) -> LabelSpec:
        field_specs = []
        for f in self._fields:
            value = str(row.get(f["col"], "")) if row else f["col"]
            field_specs.append(FieldSpec(
                value=value,
                field_type=FieldType(f["field_type"]),
            ))
        if not field_specs:
            field_specs = [FieldSpec(value="Sample")]
        return LabelSpec(
            fields=field_specs,
            tape_width_mm=self.tape_width_mm,
            margin_px=self.margin_px,
            spacing_px=self.spacing_px,
            font_name=self.font_name,
            font_size=self.font_size,
        )


# ── Label Preview Panel ────────────────────────────────────────────────────

class ScaledLabel(QLabel):
    """QLabel that always scales its pixmap to fit available space without affecting layout."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pixmap_src: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setSourcePixmap(self, pm: QPixmap):
        self._pixmap_src = pm
        self._refresh()

    def clearPixmap(self):
        self._pixmap_src = None
        super().clear()

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        return QSize(60, 60)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self):
        if self._pixmap_src is None:
            return
        w = max(8, self.width() - 16)
        h = max(8, self.height() - 16)
        scaled = self._pixmap_src.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        super().setPixmap(scaled)


class LabelPreviewPanel(QGroupBox):
    def __init__(self):
        super().__init__("👁️ 預覽")
        self._images: list[QPixmap] = []
        self._current_idx = 0
        self._worker: PreviewWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addStretch()
        self.refresh_btn = QPushButton("重新整理")
        header.addWidget(self.refresh_btn)
        self.fullsize_btn = QPushButton("⛶ 完整顯示")
        self.fullsize_btn.setEnabled(False)
        self.fullsize_btn.clicked.connect(self._show_fullsize)
        header.addWidget(self.fullsize_btn)
        layout.addLayout(header)

        # Image — click also opens full view
        self.image_label = ScaledLabel("尚無預覽")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(60)
        self.image_label.setStyleSheet(
            "background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 4px; padding: 8px;"
        )
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.mousePressEvent = lambda _: self._show_fullsize()
        layout.addWidget(self.image_label, 1)

        # Navigation
        self.nav_widget = QWidget()
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedWidth(40)
        self.prev_btn.clicked.connect(lambda: self._navigate(-1))
        nav_layout.addStretch()
        nav_layout.addWidget(self.prev_btn)
        self.nav_label = QLabel("0 / 0")
        nav_layout.addWidget(self.nav_label)
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedWidth(40)
        self.next_btn.clicked.connect(lambda: self._navigate(1))
        nav_layout.addWidget(self.next_btn)
        nav_layout.addStretch()
        self.nav_widget.hide()
        layout.addWidget(self.nav_widget)

    def _show_fullsize(self):
        if not self._images:
            return
        pm = self._images[self._current_idx]
        dlg = QDialog(self)
        dlg.setWindowTitle(f"標籤預覽　{self._current_idx + 1} / {len(self._images)}")
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        lbl = QLabel()
        lbl.setPixmap(pm)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(lbl)
        dlg_layout.addWidget(scroll)

        close_btn = QPushButton("關閉")
        close_btn.clicked.connect(dlg.accept)
        dlg_layout.addWidget(close_btn)

        screen = QApplication.primaryScreen().availableGeometry()
        w = min(pm.width() + 40, screen.width() - 100)
        h = min(pm.height() + 100, screen.height() - 100)
        dlg.resize(w, h)
        dlg.exec()

    def _navigate(self, delta: int):
        new_idx = self._current_idx + delta
        if 0 <= new_idx < len(self._images):
            self._current_idx = new_idx
            self._show_current()

    def _show_current(self):
        if not self._images:
            self.image_label.clearPixmap()
            self.image_label.setText("尚無預覽")
            self.fullsize_btn.setEnabled(False)
            self.nav_widget.hide()
            return
        pm = self._images[self._current_idx]
        self.image_label.setSourcePixmap(pm)
        self.image_label.setText("")
        self.fullsize_btn.setEnabled(True)
        if len(self._images) > 1:
            self.nav_label.setText(f"{self._current_idx + 1} / {len(self._images)}")
            self.prev_btn.setEnabled(self._current_idx > 0)
            self.next_btn.setEnabled(self._current_idx < len(self._images) - 1)
            self.nav_widget.show()
        else:
            self.nav_widget.hide()

    def update_previews(self, specs: list[LabelSpec]):
        """Start background rendering; cancel any previous in-progress render."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()

        self._images.clear()
        self.image_label.clearPixmap()
        self.image_label.setText("⏳ 生成預覽中…")
        self.fullsize_btn.setEnabled(False)
        self.nav_widget.hide()

        self._worker = PreviewWorker(specs)
        self._worker.images_ready.connect(self._on_images_ready)
        self._worker.finished.connect(self._on_preview_worker_done)
        self._worker.start()

    def _on_preview_worker_done(self):
        # 只清除自己的參照，避免覆蓋到已啟動的新 worker
        if self.sender() is self._worker:
            self._worker = None

    def _on_images_ready(self, png_list: list):
        self._images.clear()
        for png_bytes in png_list:
            pm = QPixmap()
            pm.loadFromData(png_bytes)
            self._images.append(pm)
        self._current_idx = 0
        self._show_current()


# ── Print Panel ─────────────────────────────────────────────────────────────

class PrintPanel(QGroupBox):
    tape_width_detected = pyqtSignal(int)

    def __init__(self):
        super().__init__("🖨️ 列印")
        self.printers: list[dict] = []
        self._worker: PrintWorker | None = None
        self._scan_worker: USBScanWorker | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Printer selector
        printer_layout = QHBoxLayout()
        printer_layout.addWidget(QLabel("印表機"))
        self.printer_combo = QComboBox()
        self.printer_combo.addItem("自動選擇", "")
        self.printer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.printer_combo.currentIndexChanged.connect(self._on_printer_selected)
        printer_layout.addWidget(self.printer_combo)
        self.scan_btn = QPushButton("搜尋")
        self.scan_btn.clicked.connect(self.discover_printers)
        printer_layout.addWidget(self.scan_btn)
        layout.addLayout(printer_layout)

        # Tape info
        self.tape_label = QLabel()
        self.tape_label.setStyleSheet("color: green; font-size: 11px;")
        self.tape_label.hide()
        layout.addWidget(self.tape_label)

        # Margin
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(QLabel("列印邊距 (dots)"))
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 500)
        self.margin_spin.setValue(0)
        margin_layout.addWidget(self.margin_spin)
        margin_layout.addStretch()
        layout.addLayout(margin_layout)

        # Chain print option
        self.chain_check = QCheckBox("連續列印（不裁切中間標籤，節省膠帶）")
        self.chain_check.setChecked(True)
        layout.addWidget(self.chain_check)

        # Print button
        self.print_btn = QPushButton("🖨️ 列印 0 張標籤")
        self.print_btn.setStyleSheet(
            "background-color: #16a34a; color: white; padding: 8px; "
            "border-radius: 4px; font-weight: bold;"
        )
        self.print_btn.setEnabled(False)
        layout.addWidget(self.print_btn)

        # Progress
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)

        # Result
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-size: 12px;")
        self.result_label.hide()
        layout.addWidget(self.result_label)

    def discover_printers(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("搜尋中…")
        self._scan_worker = USBScanWorker(detect_tape=True)
        self._scan_worker.printers_found.connect(self._on_printers_found)
        self._scan_worker.tape_detected.connect(self._on_tape_detected)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_worker.start()

    def _on_scan_finished(self):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("搜尋")

    def _on_printers_found(self, found: list[dict]):
        self.printers = found
        self.printer_combo.blockSignals(True)
        self.printer_combo.clear()
        self.printer_combo.addItem("自動選擇", "")
        for info in found:
            self.printer_combo.addItem(
                f"{info['product']} ({info['serial']})", info["serial"]
            )
        if found:
            self.printer_combo.setCurrentIndex(1)
        self.printer_combo.blockSignals(False)

    def _on_tape_detected(self, width_mm: int, serial: str):
        self.tape_label.setText(f"🎯 偵測到膠帶寬度：{width_mm}mm（已自動套用）")
        self.tape_label.show()
        self.tape_width_detected.emit(width_mm)

    def _on_printer_selected(self, idx):
        serial = self.printer_combo.currentData() or None
        if serial is None and idx == 0:
            self.tape_label.hide()
            return
        # Re-detect tape for newly selected printer in background
        self._scan_worker = USBScanWorker(serial=serial, detect_tape=True)
        self._scan_worker.tape_detected.connect(self._on_tape_detected)
        self._scan_worker.printers_found.connect(lambda _: None)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_worker.start()

    def set_label_count(self, count: int):
        self.print_btn.setText(f"🖨️ 列印 {count} 張標籤")
        self.print_btn.setEnabled(count > 0)

    def start_print(self, specs: list[LabelSpec]):
        if not specs:
            return
        serial = self.printer_combo.currentData() or None
        margin = self.margin_spin.value()

        self.print_btn.setEnabled(False)
        self.progress.setRange(0, len(specs))
        self.progress.setValue(0)
        self.progress.show()
        self.result_label.setText("")
        self.result_label.hide()
        self._print_errors: list[str] = []

        self._worker = PrintWorker(specs, serial, margin, self.chain_check.isChecked())
        self._worker.progress.connect(self._on_progress)
        self._worker.label_done.connect(self._on_label_done)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_progress(self, current, total):
        self.progress.setValue(current)

    def _on_label_done(self, idx, status):
        if status != "ok":
            self._print_errors.append(f"第 {idx + 1} 張失敗：{status}")

    def _on_finished(self, printed, total):
        self.progress.hide()
        self.print_btn.setEnabled(True)
        lines = [f"✅ 完成：{printed} / {total} 張"] + self._print_errors
        self.result_label.setText("\n".join(lines))
        self.result_label.setStyleSheet(
            "color: red; font-size: 12px;" if self._print_errors else "color: green; font-size: 12px;"
        )
        self.result_label.show()

    def _on_error(self, msg):
        self.progress.hide()
        self.print_btn.setEnabled(True)
        self.result_label.setText(f"❌ {msg}")
        self.result_label.setStyleSheet("color: red; font-size: 12px;")
        self.result_label.show()


# ── Main Window ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏷️ Brother Label Printer")
        self.setMinimumSize(1200, 750)
        self.data_rows: list[dict] = []

        self._init_ui()
        self._connect_signals()
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)

        # Auto-discover printers on startup
        QTimer.singleShot(500, self.print_panel.discover_printers)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left column — data import fills entire height
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 4, 0)

        self.data_panel = DataImportPanel()
        left_layout.addWidget(self.data_panel)   # no stretch — panel itself stretches internally

        splitter.addWidget(left_widget)

        # Right column — settings bar + vertical splitter for preview / print
        right_widget = QWidget()
        right_vbox = QVBoxLayout(right_widget)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(4)

        self.editor_panel = LabelEditorPanel()
        right_vbox.addWidget(self.editor_panel)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.preview_panel = LabelPreviewPanel()
        right_splitter.addWidget(self.preview_panel)

        self.print_panel = PrintPanel()
        right_splitter.addWidget(self.print_panel)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)
        right_splitter.setSizes([530, 180])

        right_vbox.addWidget(right_splitter, 1)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 400])

        # Status bar
        self.statusBar().showMessage("就緒")

    def _connect_signals(self):
        self.data_panel.data_parsed.connect(self._on_data_parsed)
        self.editor_panel.label_changed.connect(self._schedule_preview)
        self.preview_panel.refresh_btn.clicked.connect(self._update_preview)
        self.print_panel.print_btn.clicked.connect(self._on_print)
        self.print_panel.tape_width_detected.connect(self.editor_panel.set_tape_width)

    def _on_data_parsed(self, columns: list[str], field_types: list[str], rows: list[dict]):
        self.data_rows = rows
        self.editor_panel.set_fields(columns, field_types)   # emits label_changed → _schedule_preview
        self.print_panel.set_label_count(len(rows))
        self.statusBar().showMessage(f"已載入 {len(rows)} 筆資料，共 {len(columns)} 列")

    def _schedule_preview(self):
        self._preview_timer.start(400)

    def _update_preview(self):
        rows = self.data_rows[:10]
        if rows:
            specs = [self.editor_panel.build_label_spec(r) for r in rows]
        else:
            specs = [self.editor_panel.build_label_spec()]
        self.preview_panel.update_previews(specs)
        self.print_panel.set_label_count(len(self.data_rows))

    def _build_all_specs(self) -> list[LabelSpec]:
        return [self.editor_panel.build_label_spec(row) for row in self.data_rows]

    def _on_print(self):
        specs = self._build_all_specs()
        if not specs:
            QMessageBox.warning(self, "提示", "沒有資料可列印，請先匯入資料。")
            return
        self.print_panel.start_print(specs)


# ── Entry Point ─────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
