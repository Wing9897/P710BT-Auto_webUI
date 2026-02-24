# Brother Label Printer Desktop Tool

PyQt6 desktop application for Brother PT series printers (P710BT, P750W, E550W).
Single-file GUI with USB connectivity — no web server or browser required.

## Quick Start

```cmd
install.bat          # install Python dependencies
start.bat            # launch desktop app
```

Or manually:

```cmd
pip install -r backend\requirements.txt
python main_desktop.py
```

## Prerequisites

- **Python 3.10+**
- **Zadig** — install WinUSB driver for the printer (one-time setup)

## Features

- **Multi-format data import**: JSON array, CSV, custom delimiter, Excel (.xlsx)
- **Field types**: Plain text, QR Code, Code128, Code39, EAN13
- **Auto layout**: Auto font scaling, multi-line word wrap, center alignment
- **Tape widths**: 3.5mm, 6mm, 9mm, 12mm, 18mm, 24mm (auto-detected)
- **USB printing**: Direct USB connection via libusb
- **Batch print**: Print labels for all data rows with progress bar
- **Live preview**: Real-time label preview with pagination

## Architecture

```
main_desktop.py       PyQt6 desktop GUI (entry point)
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
