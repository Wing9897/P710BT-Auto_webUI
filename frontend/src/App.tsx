import { useState, useCallback } from "react";
import type { ParseResponse, LabelSpec, FieldSpec } from "./types";
import { DataImport } from "./components/DataImport";
import { LabelEditor } from "./components/LabelEditor";
import { LabelPreview } from "./components/LabelPreview";
import { PrintPanel } from "./components/PrintPanel";

const defaultField: FieldSpec = { value: "Sample", field_type: "text" };
const defaultLabel: LabelSpec = {
  fields: [defaultField],
  tape_width_mm: 24,
  margin_px: 8,
  spacing_px: 6,
};

export default function App() {
  const [parsed, setParsed] = useState<ParseResponse | null>(null);
  const [label, setLabel] = useState<LabelSpec>(defaultLabel);
  const [fieldMapping, setFieldMapping] = useState<Record<string, string>>({});

  const handleDataParsed = useCallback((data: ParseResponse) => {
    setParsed(data);
    // auto-create one text field per column
    if (data.columns.length > 0) {
      const fields: FieldSpec[] = data.columns.map((col) => ({
        value: `{${col}}`,
        field_type: "text" as const,
      }));
      setLabel((prev) => ({ ...prev, fields }));
      const mapping: Record<string, string> = {};
      data.columns.forEach((col, i) => {
        mapping[String(i)] = col;
      });
      setFieldMapping(mapping);
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-xl font-bold text-gray-800">
          🏷️ Brother Label Printer
        </h1>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column: Data + Editor */}
        <div className="space-y-6">
          <DataImport onDataParsed={handleDataParsed} />
          <LabelEditor
            label={label}
            setLabel={setLabel}
            columns={parsed?.columns ?? []}
            fieldMapping={fieldMapping}
            setFieldMapping={setFieldMapping}
          />
        </div>

        {/* Right column: Preview + Print */}
        <div className="space-y-6">
          <LabelPreview
            label={label}
            data={parsed?.data ?? []}
            fieldMapping={fieldMapping}
          />
          <PrintPanel
            label={label}
            data={parsed?.data ?? []}
            fieldMapping={fieldMapping}
          />
        </div>
      </main>
    </div>
  );
}
