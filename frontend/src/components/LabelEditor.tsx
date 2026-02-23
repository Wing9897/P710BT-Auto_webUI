import { useEffect, useState } from "react";
import type { LabelSpec, FieldSpec } from "../types";
import { TAPE_WIDTHS, FIELD_TYPES } from "../types";
import { getFonts } from "../api";

interface Props {
  label: LabelSpec;
  setLabel: React.Dispatch<React.SetStateAction<LabelSpec>>;
  columns: string[];
  fieldMapping: Record<string, string>;
  setFieldMapping: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}

export function LabelEditor({
  label,
  setLabel,
  columns,
  fieldMapping,
  setFieldMapping,
}: Props) {
  const [fonts, setFonts] = useState<string[]>([]);

  useEffect(() => {
    getFonts().then(setFonts).catch(() => {});
  }, []);

  const updateField = (idx: number, patch: Partial<FieldSpec>) => {
    setLabel((prev) => ({
      ...prev,
      fields: prev.fields.map((f, i) => (i === idx ? { ...f, ...patch } : f)),
    }));
  };

  const addField = () => {
    setLabel((prev) => ({
      ...prev,
      fields: [...prev.fields, { value: "", field_type: "text" }],
    }));
  };

  const removeField = (idx: number) => {
    setLabel((prev) => ({
      ...prev,
      fields: prev.fields.filter((_, i) => i !== idx),
    }));
    setFieldMapping((prev) => {
      const next = { ...prev };
      delete next[String(idx)];
      return next;
    });
  };

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-lg font-semibold mb-3">✏️ 標籤編輯</h2>

      {/* Global settings */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div>
          <label className="text-xs text-gray-500">膠帶寬度</label>
          <select
            className="w-full border rounded px-2 py-1.5 text-sm"
            value={label.tape_width_mm}
            onChange={(e) =>
              setLabel((p) => ({ ...p, tape_width_mm: Number(e.target.value) }))
            }
          >
            {TAPE_WIDTHS.map((w) => (
              <option key={w} value={w}>
                {w}mm
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">字型</label>
          <select
            className="w-full border rounded px-2 py-1.5 text-sm"
            value={label.font_name ?? ""}
            onChange={(e) =>
              setLabel((p) => ({
                ...p,
                font_name: e.target.value || undefined,
              }))
            }
          >
            <option value="">預設</option>
            {fonts.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">字體大小</label>
          <input
            type="number"
            className="w-full border rounded px-2 py-1.5 text-sm"
            placeholder="自動"
            value={label.font_size ?? ""}
            onChange={(e) =>
              setLabel((p) => ({
                ...p,
                font_size: e.target.value ? Number(e.target.value) : undefined,
              }))
            }
          />
        </div>
        <div>
          <label className="text-xs text-gray-500">邊距 (px)</label>
          <input
            type="number"
            className="w-full border rounded px-2 py-1.5 text-sm"
            value={label.margin_px}
            onChange={(e) =>
              setLabel((p) => ({ ...p, margin_px: Number(e.target.value) }))
            }
          />
        </div>
      </div>

      {/* Fields */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-medium">欄位</h3>
          <button
            className="text-sm text-blue-600 hover:underline"
            onClick={addField}
          >
            + 新增欄位
          </button>
        </div>

        {label.fields.map((field, idx) => (
          <div
            key={idx}
            className="border rounded p-3 space-y-2 bg-gray-50"
          >
            <div className="flex gap-2 items-center">
              <span className="text-xs font-mono text-gray-400 w-5">
                {idx + 1}
              </span>

              {/* Field type */}
              <select
                className="border rounded px-2 py-1 text-sm"
                value={field.field_type}
                onChange={(e) =>
                  updateField(idx, {
                    field_type: e.target.value as FieldSpec["field_type"],
                  })
                }
              >
                {FIELD_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t === "text"
                      ? "文字"
                      : t === "qr"
                      ? "QR Code"
                      : t.toUpperCase()}
                  </option>
                ))}
              </select>

              {/* Data column mapping */}
              {columns.length > 0 && (
                <select
                  className="border rounded px-2 py-1 text-sm flex-1"
                  value={fieldMapping[String(idx)] ?? ""}
                  onChange={(e) =>
                    setFieldMapping((prev) => ({
                      ...prev,
                      [String(idx)]: e.target.value,
                    }))
                  }
                >
                  <option value="">（固定文字）</option>
                  {columns.map((col) => (
                    <option key={col} value={col}>
                      📊 {col}
                    </option>
                  ))}
                </select>
              )}

              <button
                className="text-red-500 hover:text-red-700 text-sm px-1"
                onClick={() => removeField(idx)}
              >
                ✕
              </button>
            </div>

            {/* Value / static text */}
            {!fieldMapping[String(idx)] && (
              <input
                className="w-full border rounded px-2 py-1.5 text-sm"
                placeholder="輸入文字..."
                value={field.value}
                onChange={(e) => updateField(idx, { value: e.target.value })}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
