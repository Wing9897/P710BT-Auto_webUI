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
    QGridLayout, QLabel, QPushButton, QTextEdit, QComboBox, QLineEdit,
    QSpinBox, QFileDialog, QTableWidget, QTableWidgetItem, QGroupBox,
    QSplitter, QMessageBox, QSizePolicy,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont

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

    def __init__(self, specs: list[LabelSpec], serial: str | None, margin_px: int):
        super().__init__()
        self.specs = specs
        self.serial = serial
        self.margin_px = margin_px

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
                    printer.print_image(image, self.margin_px)
                    printed += 1
                    self.label_done.emit(i, "ok")
                except Exception as e:
                    self.label_done.emit(i, str(e))
                self.progress.emit(i + 1, total)
        finally:
            printer.close()
        self.finished_all.emit(printed, total)


# ── Data Import Panel ───────────────────────────────────────────────────────

class DataImportPanel(QGroupBox):
    data_parsed = pyqtSignal(list, list)  # (columns, data_rows)

    def __init__(self):
        super().__init__("📥 資料匯入")
        self.columns: list[str] = []
        self.data_rows: list[dict] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Format row
        fmt_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["自動偵測", "JSON", "CSV", "自定義分隔符", "Excel (.xlsx)"])
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(self.format_combo)
        self.delim_edit = QLineEdit()
        self.delim_edit.setPlaceholderText("分隔符")
        self.delim_edit.setMaximumWidth(60)
        self.delim_edit.hide()
        fmt_layout.addWidget(self.delim_edit)
        fmt_layout.addStretch()
        layout.addLayout(fmt_layout)

        # Text input
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "貼上資料...\n"
            '例如 JSON: [{"name":"A","value":"1"}]\n'
            "例如 CSV:\nname,value\nA,1\n\n"
            "或用分隔符：123,321,sss"
        )
        self.text_edit.setMaximumHeight(120)
        layout.addWidget(self.text_edit)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.file_btn = QPushButton("📁 選擇檔案...")
        self.file_btn.clicked.connect(self._open_file)
        btn_layout.addWidget(self.file_btn)
        self.parse_btn = QPushButton("解析文字")
        self.parse_btn.clicked.connect(self._parse_text)
        btn_layout.addWidget(self.parse_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 11px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Preview table
        self.table = QTableWidget()
        self.table.setMaximumHeight(150)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.hide()
        layout.addWidget(self.table)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: gray; font-size: 11px;")
        self.count_label.hide()
        layout.addWidget(self.count_label)

    def _on_format_changed(self, idx):
        self.delim_edit.setVisible(idx == 3)  # "自定義分隔符"
        self.text_edit.setVisible(idx != 4)   # hide text for Excel

    def _format_key(self) -> str:
        return ["auto", "json", "csv", "delimited", "excel"][self.format_combo.currentIndex()]

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇資料檔案", "",
            "All supported (*.csv *.tsv *.json *.xlsx *.xls *.txt);;All files (*)"
        )
        if not path:
            return
        fmt = self._format_key()
        try:
            with open(path, "rb") as f:
                raw = f.read()
            if path.endswith((".xlsx", ".xls")):
                rows = parse_auto(file_bytes=raw, format="excel")
            else:
                text = raw.decode("utf-8", errors="replace")
                delim = self.delim_edit.text() or None
                rows = parse_auto(text=text, format=fmt, delimiter=delim)
            self._set_data(rows)
        except Exception as e:
            self._show_error(str(e))

    def _parse_text(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        fmt = self._format_key()
        delim = self.delim_edit.text() or None
        try:
            rows = parse_auto(text=text, format=fmt, delimiter=delim)
            self._set_data(rows)
        except Exception as e:
            self._show_error(str(e))

    def _set_data(self, rows: list[dict]):
        self.error_label.hide()
        if not rows:
            self._show_error("解析結果為空")
            return
        self.columns = list(rows[0].keys())
        self.data_rows = rows
        self._update_table()
        self.data_parsed.emit(self.columns, self.data_rows)

    def _update_table(self):
        display = self.data_rows[:50]
        self.table.setRowCount(len(display))
        self.table.setColumnCount(len(self.columns) + 1)
        self.table.setHorizontalHeaderLabels(["#"] + self.columns)
        for r, row in enumerate(display):
            self.table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            for c, col in enumerate(self.columns):
                self.table.setItem(r, c + 1, QTableWidgetItem(row.get(col, "")))
        self.table.resizeColumnsToContents()
        self.table.show()
        self.count_label.setText(f"共 {len(self.data_rows)} 筆資料")
        self.count_label.show()

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()


# ── Label Editor Panel ──────────────────────────────────────────────────────

class LabelEditorPanel(QGroupBox):
    label_changed = pyqtSignal()

    def __init__(self):
        super().__init__("✏️ 標籤編輯")
        self.fields: list[dict] = [{"value": "Sample", "field_type": "text"}]
        self.tape_width_mm = 24
        self.font_name: str | None = None
        self.font_size: int | None = None
        self.margin_px = 8
        self.spacing_px = 6
        self.field_mapping: dict[str, str] = {}
        self.columns: list[str] = []
        self._available_fonts: list[str] = []
        self._init_ui()
        self._load_fonts()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Global settings
        settings_layout = QGridLayout()
        settings_layout.addWidget(QLabel("膠帶寬度"), 0, 0)
        self.tape_combo = QComboBox()
        self.tape_combo.addItems([f"{w}mm" for w in TAPE_WIDTHS_MM])
        self.tape_combo.setCurrentIndex(TAPE_WIDTHS_MM.index(24))
        self.tape_combo.currentIndexChanged.connect(self._on_settings_changed)
        settings_layout.addWidget(self.tape_combo, 1, 0)

        settings_layout.addWidget(QLabel("字型"), 0, 1)
        self.font_combo = QComboBox()
        self.font_combo.addItem("預設", None)
        self.font_combo.currentIndexChanged.connect(self._on_settings_changed)
        settings_layout.addWidget(self.font_combo, 1, 1)

        settings_layout.addWidget(QLabel("字體大小"), 0, 2)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(0, 200)
        self.font_size_spin.setSpecialValueText("自動")
        self.font_size_spin.setValue(0)
        self.font_size_spin.valueChanged.connect(self._on_settings_changed)
        settings_layout.addWidget(self.font_size_spin, 1, 2)

        settings_layout.addWidget(QLabel("邊距 (px)"), 0, 3)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 50)
        self.margin_spin.setValue(8)
        self.margin_spin.valueChanged.connect(self._on_settings_changed)
        settings_layout.addWidget(self.margin_spin, 1, 3)

        layout.addLayout(settings_layout)

        # Fields header
        fields_header = QHBoxLayout()
        fields_header.addWidget(QLabel("欄位"))
        fields_header.addStretch()
        self.add_field_btn = QPushButton("+ 新增欄位")
        self.add_field_btn.clicked.connect(self._add_field)
        fields_header.addWidget(self.add_field_btn)
        layout.addLayout(fields_header)

        # Fields container
        self.fields_widget = QWidget()
        self.fields_layout = QVBoxLayout(self.fields_widget)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.fields_widget)

        self._rebuild_fields_ui()

    def _load_fonts(self):
        try:
            fonts = list_available_fonts()
            for f in fonts:
                self.font_combo.addItem(f, f)
            self._available_fonts = fonts
        except Exception:
            pass

    def _on_settings_changed(self):
        self.tape_width_mm = TAPE_WIDTHS_MM[self.tape_combo.currentIndex()]
        self.font_name = self.font_combo.currentData()
        self.font_size = self.font_size_spin.value() or None
        self.margin_px = self.margin_spin.value()
        self.label_changed.emit()

    def _add_field(self):
        self.fields.append({"value": "", "field_type": "text"})
        self._rebuild_fields_ui()
        self.label_changed.emit()

    def _remove_field(self, idx: int):
        if idx < len(self.fields):
            self.fields.pop(idx)
            self.field_mapping.pop(str(idx), None)
            self._rebuild_fields_ui()
            self.label_changed.emit()

    def _rebuild_fields_ui(self):
        while self.fields_layout.count():
            item = self.fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for idx, field in enumerate(self.fields):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)

            num_label = QLabel(str(idx + 1))
            num_label.setFixedWidth(20)
            num_label.setStyleSheet("color: gray; font-size: 11px;")
            row_layout.addWidget(num_label)

            type_combo = QComboBox()
            for ft in FIELD_TYPES:
                type_combo.addItem(FIELD_TYPE_LABELS[ft], ft)
            type_combo.setCurrentIndex(FIELD_TYPES.index(field["field_type"]))
            type_combo.currentIndexChanged.connect(
                lambda _, i=idx, c=type_combo: self._on_field_type_changed(i, c))
            row_layout.addWidget(type_combo)

            # Column mapping
            if self.columns:
                map_combo = QComboBox()
                map_combo.addItem("（固定文字）", "")
                for col in self.columns:
                    map_combo.addItem(f"📊 {col}", col)
                current_map = self.field_mapping.get(str(idx), "")
                map_idx = 0
                for mi in range(map_combo.count()):
                    if map_combo.itemData(mi) == current_map:
                        map_idx = mi
                        break
                map_combo.setCurrentIndex(map_idx)
                map_combo.currentIndexChanged.connect(
                    lambda _, i=idx, c=map_combo: self._on_mapping_changed(i, c))
                row_layout.addWidget(map_combo)

            value_edit = QLineEdit(field.get("value", ""))
            value_edit.setPlaceholderText("輸入文字...")
            value_edit.textChanged.connect(
                lambda txt, i=idx: self._on_value_changed(i, txt))
            if self.field_mapping.get(str(idx)):
                value_edit.hide()
            row_layout.addWidget(value_edit)

            remove_btn = QPushButton("✕")
            remove_btn.setFixedWidth(30)
            remove_btn.setStyleSheet("color: red;")
            remove_btn.clicked.connect(lambda _, i=idx: self._remove_field(i))
            row_layout.addWidget(remove_btn)

            self.fields_layout.addWidget(row_widget)

    def _on_field_type_changed(self, idx, combo):
        self.fields[idx]["field_type"] = combo.currentData()
        self.label_changed.emit()

    def _on_value_changed(self, idx, text):
        self.fields[idx]["value"] = text
        self.label_changed.emit()

    def _on_mapping_changed(self, idx, combo):
        val = combo.currentData()
        if val:
            self.field_mapping[str(idx)] = val
        else:
            self.field_mapping.pop(str(idx), None)
        self._rebuild_fields_ui()
        self.label_changed.emit()

    def set_columns(self, columns: list[str]):
        self.columns = columns
        self._rebuild_fields_ui()

    def set_tape_width(self, width_mm: int):
        if width_mm in TAPE_WIDTHS_MM:
            self.tape_width_mm = width_mm
            self.tape_combo.setCurrentIndex(TAPE_WIDTHS_MM.index(width_mm))

    def auto_create_fields(self, columns: list[str]):
        """Auto-create one text field per column (like web version)."""
        self.fields = [{"value": f"{{{col}}}", "field_type": "text"} for col in columns]
        self.field_mapping = {str(i): col for i, col in enumerate(columns)}
        self._rebuild_fields_ui()
        self.label_changed.emit()

    def build_label_spec(self, row: dict | None = None) -> LabelSpec:
        """Build a LabelSpec, optionally substituting values from a data row."""
        field_specs = []
        for i, f in enumerate(self.fields):
            value = f["value"]
            col = self.field_mapping.get(str(i))
            if col and row:
                value = row.get(col, value)
            field_specs.append(FieldSpec(
                value=value,
                field_type=FieldType(f["field_type"]),
                font_name=self.font_name,
                font_size=self.font_size,
            ))
        return LabelSpec(
            fields=field_specs,
            tape_width_mm=self.tape_width_mm,
            margin_px=self.margin_px,
            spacing_px=self.spacing_px,
            font_name=self.font_name,
            font_size=self.font_size,
        )


# ── Label Preview Panel ────────────────────────────────────────────────────

class LabelPreviewPanel(QGroupBox):
    def __init__(self):
        super().__init__("👁️ 預覽")
        self._images: list[QPixmap] = []
        self._current_idx = 0
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addStretch()
        self.refresh_btn = QPushButton("重新整理")
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # Image
        self.image_label = QLabel("尚無預覽")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(60)
        self.image_label.setStyleSheet("background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 4px; padding: 8px;")
        layout.addWidget(self.image_label)

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

    def _navigate(self, delta: int):
        new_idx = self._current_idx + delta
        if 0 <= new_idx < len(self._images):
            self._current_idx = new_idx
            self._show_current()

    def _show_current(self):
        if not self._images:
            self.image_label.setText("尚無預覽")
            self.nav_widget.hide()
            return
        pm = self._images[self._current_idx]
        scaled = pm.scaledToHeight(min(100, pm.height()), Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        if len(self._images) > 1:
            self.nav_label.setText(f"{self._current_idx + 1} / {len(self._images)}")
            self.prev_btn.setEnabled(self._current_idx > 0)
            self.next_btn.setEnabled(self._current_idx < len(self._images) - 1)
            self.nav_widget.show()
        else:
            self.nav_widget.hide()

    def update_previews(self, specs: list[LabelSpec]):
        """Render label specs into preview images."""
        self._images.clear()
        for spec in specs[:10]:  # Limit to 10 previews
            try:
                img = render_label(spec)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                qimg = QPixmap()
                qimg.loadFromData(buf.getvalue())
                self._images.append(qimg)
            except Exception:
                pass
        self._current_idx = 0
        self._show_current()


# ── Print Panel ─────────────────────────────────────────────────────────────

class PrintPanel(QGroupBox):
    tape_width_detected = pyqtSignal(int)

    def __init__(self):
        super().__init__("🖨️ 列印")
        self.printers: list[dict] = []
        self._worker: PrintWorker | None = None
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
        self.printers.clear()
        self.printer_combo.clear()
        self.printer_combo.addItem("自動選擇", "")
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
                    info = {
                        "product": dev.product or pid.name,
                        "serial": dev.serial_number or "",
                        "manufacturer": dev.manufacturer or "",
                    }
                    self.printers.append(info)
                    self.printer_combo.addItem(
                        f"{info['product']} ({info['serial']})", info["serial"]
                    )
        except Exception as e:
            log.warning("USB discovery failed: %s", e)

        if self.printers:
            self.printer_combo.setCurrentIndex(1)

    def _on_printer_selected(self, idx):
        serial = self.printer_combo.currentData()
        self._detect_tape(serial if serial else None)

    def _detect_tape(self, serial: str | None):
        try:
            transport = USBTransport(serial)
            printer = BrotherPrinter(transport)
            printer.connect()
            status = printer.status
            printer.close()
            if status and status.media_width > 0:
                self.tape_label.setText(
                    f"🎯 偵測到膠帶寬度：{status.media_width}mm（已自動套用）"
                )
                self.tape_label.show()
                self.tape_width_detected.emit(status.media_width)
        except Exception:
            self.tape_label.hide()

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
        self.result_label.hide()

        self._worker = PrintWorker(specs, serial, margin)
        self._worker.progress.connect(self._on_progress)
        self._worker.label_done.connect(self._on_label_done)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current, total):
        self.progress.setValue(current)

    def _on_label_done(self, idx, status):
        if status != "ok":
            current = self.result_label.text()
            self.result_label.setText(current + f"\n第 {idx + 1} 張失敗：{status}")
            self.result_label.setStyleSheet("color: red; font-size: 12px;")
            self.result_label.show()

    def _on_finished(self, printed, total):
        self.progress.hide()
        self.print_btn.setEnabled(True)
        msg = f"✅ 完成：{printed} / {total} 張"
        self.result_label.setText(msg + "\n" + self.result_label.text())
        self.result_label.setStyleSheet("color: green; font-size: 12px;")
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
        self.setMinimumSize(900, 650)
        self.data_rows: list[dict] = []
        self.columns: list[str] = []

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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left column
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        self.data_panel = DataImportPanel()
        left_layout.addWidget(self.data_panel)

        self.editor_panel = LabelEditorPanel()
        left_layout.addWidget(self.editor_panel)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # Right column
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.preview_panel = LabelPreviewPanel()
        right_layout.addWidget(self.preview_panel)

        self.print_panel = PrintPanel()
        right_layout.addWidget(self.print_panel)
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([450, 450])

        # Status bar
        self.statusBar().showMessage("就緒")

    def _connect_signals(self):
        self.data_panel.data_parsed.connect(self._on_data_parsed)
        self.editor_panel.label_changed.connect(self._schedule_preview)
        self.preview_panel.refresh_btn.clicked.connect(self._update_preview)
        self.print_panel.print_btn.clicked.connect(self._on_print)
        self.print_panel.tape_width_detected.connect(self.editor_panel.set_tape_width)

    def _on_data_parsed(self, columns: list[str], rows: list[dict]):
        self.columns = columns
        self.data_rows = rows
        self.editor_panel.set_columns(columns)
        self.editor_panel.auto_create_fields(columns)
        self.print_panel.set_label_count(len(rows))
        self.statusBar().showMessage(f"已載入 {len(rows)} 筆資料")
        self._schedule_preview()

    def _schedule_preview(self):
        self._preview_timer.start(400)

    def _update_preview(self):
        specs = self._build_all_specs()
        if not specs:
            spec = self.editor_panel.build_label_spec()
            specs = [spec]
        self.preview_panel.update_previews(specs)
        self.print_panel.set_label_count(len(self.data_rows))

    def _build_all_specs(self) -> list[LabelSpec]:
        if not self.data_rows:
            return []
        specs = []
        for row in self.data_rows:
            specs.append(self.editor_panel.build_label_spec(row))
        return specs

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
