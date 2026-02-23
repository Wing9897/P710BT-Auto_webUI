# Brother Label Printer Web Tool

Web-based label printing tool for Brother PT series printers (P710BT, P750W, E550W).
Combines USB (pyusb) and Bluetooth RFCOMM transport with a React frontend.

## Quick Start

### Backend

```cmd
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```cmd
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173

## Features

- **Multi-format data import**: JSON array, CSV, tab/pipe/semicolon delimited, Excel (.xlsx)
- **Field types**: Plain text, QR Code, Code128, Code39, EAN13
- **Auto layout**: Auto font scaling, multi-line word wrap, center alignment
- **Tape widths**: 3.5mm, 6mm, 9mm, 12mm, 18mm, 24mm
- **Transport**: USB and Bluetooth Classic (RFCOMM)
- **Batch print**: Print labels for all data rows with progress tracking
- **Live preview**: Real-time label preview as you edit

## Architecture

```
backend/          Python FastAPI
  app/
    printer/      Transport ABC + USB/BT + Brother PT raster protocol
    services/     Label renderer (Pillow) + Data parser
    routers/      REST API endpoints
    models/       Pydantic schemas

frontend/         React + Vite + TypeScript + Tailwind CSS
  src/
    components/   DataImport, LabelEditor, LabelPreview, PrintPanel
    api/          Axios API client
    types/        TypeScript type definitions
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/data/parse | Parse input data (form multipart) |
| POST | /api/label/preview | Single label preview (PNG base64) |
| POST | /api/label/batch-preview | Batch preview for data rows |
| POST | /api/label/print | Print labels |
| GET | /api/printer/discover | Discover USB printers |
| GET | /api/printer/status | Get printer status |
| GET | /api/fonts | List available fonts |
