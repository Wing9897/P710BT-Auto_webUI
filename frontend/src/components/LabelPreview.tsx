import { useState, useEffect, useCallback } from "react";
import type { LabelSpec } from "../types";
import { previewLabel, batchPreview } from "../api";

interface Props {
  label: LabelSpec;
  data: Record<string, string>[];
  fieldMapping: Record<string, string>;
}

export function LabelPreview({ label, data, fieldMapping }: Props) {
  const [images, setImages] = useState<{ index: number; image: string }[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [loading, setLoading] = useState(false);

  const doPreview = useCallback(async () => {
    if (label.fields.length === 0) return;
    setLoading(true);
    try {
      if (data.length > 0 && Object.keys(fieldMapping).length > 0) {
        // Batch preview (first 10)
        const slice = data.slice(0, 10);
        const res = await batchPreview(label, slice, fieldMapping);
        setImages(res.previews);
        setCurrentIdx(0);
      } else {
        // Single preview
        const res = await previewLabel(label);
        setImages([{ index: 0, image: res.image }]);
        setCurrentIdx(0);
      }
    } catch {
      setImages([]);
    } finally {
      setLoading(false);
    }
  }, [label, data, fieldMapping]);

  // Auto-preview on changes (debounced)
  useEffect(() => {
    const timer = setTimeout(doPreview, 500);
    return () => clearTimeout(timer);
  }, [doPreview]);

  const current = images[currentIdx];

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-lg font-semibold">👁️ 預覽</h2>
        <button
          className="text-sm text-blue-600 hover:underline"
          onClick={doPreview}
          disabled={loading}
        >
          {loading ? "渲染中..." : "重新整理"}
        </button>
      </div>

      {/* Preview image */}
      <div className="border rounded bg-gray-100 p-4 flex items-center justify-center min-h-[80px] overflow-auto">
        {current ? (
          <img
            src={current.image}
            alt={`Label preview ${currentIdx + 1}`}
            className="max-w-full h-auto"
            style={{ imageRendering: "pixelated" }}
          />
        ) : (
          <p className="text-gray-400 text-sm">
            {loading ? "渲染中..." : "尚無預覽"}
          </p>
        )}
      </div>

      {/* Navigation */}
      {images.length > 1 && (
        <div className="flex items-center justify-center gap-3 mt-3">
          <button
            className="px-2 py-1 border rounded text-sm disabled:opacity-30"
            disabled={currentIdx === 0}
            onClick={() => setCurrentIdx((i) => i - 1)}
          >
            ◀
          </button>
          <span className="text-sm text-gray-600">
            {currentIdx + 1} / {images.length}
            {data.length > images.length && (
              <span className="text-gray-400">
                {" "}(共 {data.length} 筆)
              </span>
            )}
          </span>
          <button
            className="px-2 py-1 border rounded text-sm disabled:opacity-30"
            disabled={currentIdx >= images.length - 1}
            onClick={() => setCurrentIdx((i) => i + 1)}
          >
            ▶
          </button>
        </div>
      )}
    </div>
  );
}
