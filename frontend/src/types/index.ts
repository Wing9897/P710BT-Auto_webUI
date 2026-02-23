export interface FieldSpec {
  value: string;
  field_type: "text" | "qr" | "code128" | "code39" | "ean13";
  font_name?: string;
  font_size?: number;
}

export interface LabelSpec {
  fields: FieldSpec[];
  tape_width_mm: number;
  height_px?: number;
  margin_px: number;
  spacing_px: number;
  font_name?: string;
  font_size?: number;
}

export interface ParseResponse {
  columns: string[];
  data: Record<string, string>[];
  row_count: number;
}

export interface PreviewResponse {
  image: string; // data:image/png;base64,...
}

export interface BatchPreviewResponse {
  previews: { index: number; image: string }[];
}

export interface PrintRequest {
  label_template: LabelSpec;
  data: Record<string, string>[];
  field_mapping: Record<string, string>;
  transport_type: "usb" | "bluetooth";
  bt_address?: string;
  bt_channel?: number;
  usb_serial?: string;
  margin_px: number;
}

export interface PrintResult {
  total: number;
  printed: number;
  results: { index: number; status: string; message?: string }[];
}

export interface PrinterDevice {
  type: string;
  product: string;
  serial: string;
  manufacturer: string;
}

export const TAPE_WIDTHS = [4, 6, 9, 12, 18, 24] as const;
export const FIELD_TYPES = ["text", "qr", "code128", "code39", "ean13"] as const;
