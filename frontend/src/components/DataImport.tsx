import { useState, useRef } from "react";
import type { ParseResponse } from "../types";
import { parseData } from "../api";

interface Props {
  onDataParsed: (data: ParseResponse) => void;
}

export function DataImport({ onDataParsed }: Props) {
  const [text, setText] = useState("");
  const [format, setFormat] = useState("auto");
  const [delimiter, setDelimiter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<ParseResponse | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleParse = async (file?: File) => {
    setLoading(true);
    setError("");
    try {
      const fd = new FormData();
      if (file) {
        fd.append("file", file);
      } else {
        fd.append("text", text);
      }
      fd.append("format", format);
      if (delimiter) fd.append("delimiter", delimiter);

      const result = await parseData(fd);
      setPreview(result);
      onDataParsed(result);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-lg font-semibold mb-3">📥 資料匯入</h2>

      {/* Format selector */}
      <div className="flex gap-3 mb-3">
        <select
          className="border rounded px-3 py-1.5 text-sm"
          value={format}
          onChange={(e) => setFormat(e.target.value)}
        >
          <option value="auto">自動偵測</option>
          <option value="json">JSON</option>
          <option value="csv">CSV</option>
          <option value="delimited">自定義分隔符</option>
          <option value="excel">Excel (.xlsx)</option>
        </select>

        {format === "delimited" && (
          <input
            className="border rounded px-3 py-1.5 text-sm w-20"
            placeholder="分隔符"
            value={delimiter}
            onChange={(e) => setDelimiter(e.target.value)}
          />
        )}
      </div>

      {/* Text input */}
      {format !== "excel" && (
        <textarea
          className="w-full border rounded p-3 text-sm font-mono h-32 mb-3"
          placeholder={'貼上資料...\n例如 JSON: [{"name":"A","value":"1"}]\n例如 CSV:\nname,value\nA,1'}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      )}

      {/* File upload */}
      <div className="flex gap-3 mb-3">
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.tsv,.json,.xlsx,.xls,.txt"
          className="text-sm"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleParse(f);
          }}
        />
        {format !== "excel" && (
          <button
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            onClick={() => handleParse()}
            disabled={loading || !text.trim()}
          >
            {loading ? "解析中..." : "解析文字"}
          </button>
        )}
      </div>

      {error && <p className="text-red-600 text-sm mb-2">{error}</p>}

      {/* Data preview table */}
      {preview && preview.row_count > 0 && (
        <div className="overflow-auto max-h-48 border rounded">
          <table className="w-full text-xs">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                <th className="px-2 py-1 text-left">#</th>
                {preview.columns.map((col) => (
                  <th key={col} className="px-2 py-1 text-left">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.data.slice(0, 50).map((row, i) => (
                <tr key={i} className="border-t">
                  <td className="px-2 py-1 text-gray-400">{i + 1}</td>
                  {preview.columns.map((col) => (
                    <td key={col} className="px-2 py-1">
                      {row[col]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-gray-500 p-2">
            共 {preview.row_count} 筆資料
          </p>
        </div>
      )}
    </div>
  );
}
