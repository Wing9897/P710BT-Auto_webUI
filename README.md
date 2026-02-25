# P710BT-Auto WebUI — Brother Label Printer Desktop Tool

PySide6 desktop application for Brother PT series printers (P710BT, P750W, E550W).
Single-file GUI with USB connectivity — no web server or browser required.

## Download

Pre-built binaries are available on the [Releases](../../releases) page — no Python installation required.

| Platform | Architecture | Format | File |
|----------|-------------|--------|------|
| Windows | x64 | Portable (no install) | `P710BT-Auto-windows-x64.zip` |
| Windows | x64 | Installer | `P710BT-Auto-windows-x64-setup.exe` |
| Linux | x64 | AppImage (no install) | `P710BT-Auto-linux-x64.AppImage` |
| Linux | x64 | DEB package | `P710BT-Auto-linux-x64.deb` |
| Linux | ARM64 | AppImage (no install) | `P710BT-Auto-linux-arm64.AppImage` |
| Linux | ARM64 | DEB package | `P710BT-Auto-linux-arm64.deb` |
| macOS | Apple Silicon (M1/M2/M3/M4) + Intel via Rosetta 2 | DMG | `P710BT-Auto-macos-arm64.dmg` |

### Usage
- **Windows (portable)**: Extract `.zip` → run `main_desktop.exe`
- **Windows (installer)**: Run `setup.exe` → desktop shortcut created automatically
- **Linux AppImage**: `chmod +x *.AppImage` → run directly (no installation)
- **Linux DEB**: `sudo dpkg -i *.deb` → run `p710bt-auto`
- **macOS**: Open `.dmg` → double-click `main_desktop.app`

> **Windows only**: Install [Zadig](https://zadig.akeo.ie/) to set up the WinUSB driver for the printer (one-time setup).

---

## 設計理念

本工具針對**批量標籤列印**場景而設計，核心概念是「資料驅動標籤」：

```
匯入資料 → 設計版型 → 即時預覽 → 一鍵批量列印
```

每一行資料對應一張標籤，程式自動將欄位映射到版型，無需逐張手動輸入。

---

## 工作流程

### 1. 匯入資料
支援多種格式直接匯入，或貼上文字：

| 格式 | 說明 |
|------|------|
| CSV | 可自訂分隔符號 |
| JSON | 陣列格式 |
| Excel | `.xlsx` |
| 貼上文字 | 自訂分隔符號解析 |

資料表預覽顯示前 50 筆，支援刪除個別行。

### 2. 設計標籤版型
- **膠帶寬度**：3.5 / 6 / 9 / 12 / 18 / 24mm（連接打印機後自動偵測）
- **欄位類型**：純文字、QR Code、Code128、Code39、EAN13
- **自動排版**：字體大小自動縮放配合標籤寬度、多行自動換行、置中對齊

### 3. 即時預覽
- 根據實際資料渲染標籤縮圖
- 支援翻頁瀏覽（前 10 張）
- 全螢幕放大預覽

### 4. 列印
- USB 直連打印機（無需驅動程式，透過 libusb）
- 自動偵測已插入膠帶寬度及餘量
- 批量列印全部資料行，顯示進度及結果
- **連續列印模式**：省去標籤之間的切割，節省膠帶

---

## 應用場景

- 倉庫貨品標籤（批量列印貨號 + 條碼）
- 活動名牌（CSV 名單 → 一鍵列印）
- 零售價格標籤（Excel 產品表）
- 資產管理（QR Code 批量生成）

---

## Features

- **Multi-format data import**: JSON array, CSV, custom delimiter, Excel (.xlsx)
- **Field types**: Plain text, QR Code, Code128, Code39, EAN13
- **Auto layout**: Auto font scaling, multi-line word wrap, center alignment
- **Tape widths**: 3.5mm, 6mm, 9mm, 12mm, 18mm, 24mm (auto-detected)
- **USB printing**: Direct USB connection via libusb
- **Batch print**: Print labels for all data rows with progress bar
- **Live preview**: Real-time label preview with pagination

---

## Run from Source

```cmd
pip install -r backend\requirements.txt
python main_desktop.py
```

Or on Windows use the provided scripts:

```cmd
install.bat          # install dependencies
start.bat            # launch app
```

**Prerequisites**: Python 3.10+

## Architecture

```
main_desktop.py       PySide6 desktop GUI (entry point)
backend/
  app/
    printer/          USB transport + Brother PT raster protocol
      constants.py    Protocol constants, printer IDs, tape margins
      transport.py    USB transport (libusb)
      protocol.py     Brother PT command builder + printer driver
      raster.py       Image → raster data conversion
    services/
      data_parser.py  Multi-format data parser
      label_renderer.py  Label rendering engine (Pillow)
```
