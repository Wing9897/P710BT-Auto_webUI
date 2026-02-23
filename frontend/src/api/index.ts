import axios from "axios";
import type {
  LabelSpec,
  ParseResponse,
  PreviewResponse,
  BatchPreviewResponse,
  PrintRequest,
  PrintResult,
  PrinterDevice,
} from "../types";

const api = axios.create({ baseURL: "/api" });

export async function parseData(
  formData: FormData
): Promise<ParseResponse> {
  const { data } = await api.post("/data/parse", formData);
  return data;
}

export async function previewLabel(
  label: LabelSpec
): Promise<PreviewResponse> {
  const { data } = await api.post("/label/preview", label);
  return data;
}

export async function batchPreview(
  label_template: LabelSpec,
  rows: Record<string, string>[],
  field_mapping: Record<string, string>
): Promise<BatchPreviewResponse> {
  const { data } = await api.post("/label/batch-preview", {
    label_template,
    data: rows,
    field_mapping,
  });
  return data;
}

export async function printLabels(
  req: PrintRequest
): Promise<PrintResult> {
  const { data } = await api.post("/label/print", req);
  return data;
}

export async function discoverBtDevices(duration = 8): Promise<{ name: string; address: string }[]> {
  const { data } = await api.get("/printer/discover-bt", { params: { duration } });
  return data.devices;
}

export async function discoverPrinters(): Promise<PrinterDevice[]> {
  const { data } = await api.get("/printer/discover");
  return data.printers;
}

export async function getPrinterStatus(params: {
  transport_type: string;
  serial?: string;
  bt_address?: string;
}): Promise<Record<string, string>> {
  const { data } = await api.get("/printer/status", { params });
  return data;
}

export async function getFonts(): Promise<string[]> {
  const { data } = await api.get("/fonts");
  return data.fonts;
}
