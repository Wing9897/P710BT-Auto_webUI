import { useState, useEffect } from "react";
import type { LabelSpec, PrintResult, PrinterDevice } from "../types";
import { printLabels, discoverPrinters, discoverBtDevices } from "../api";

interface BtDevice {
  name: string;
  address: string;
}

interface Props {
  label: LabelSpec;
  data: Record<string, string>[];
  fieldMapping: Record<string, string>;
}

export function PrintPanel({ label, data, fieldMapping }: Props) {
  const [transport, setTransport] = useState<"usb" | "bluetooth">("usb");
  const [btDevice, setBtDevice] = useState<BtDevice | null>(null);
  const [btDevices, setBtDevices] = useState<BtDevice[]>([]);
  const [btChannel, setBtChannel] = useState(1);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState("");
  const [usbSerial, setUsbSerial] = useState("");
  const [marginPx, setMarginPx] = useState(0);
  const [printers, setPrinters] = useState<PrinterDevice[]>([]);
  const [printing, setPrinting] = useState(false);
  const [result, setResult] = useState<PrintResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    discoverPrinters().then(setPrinters).catch(() => {});
  }, []);

  const handleScanBt = async () => {
    setScanning(true);
    setScanError("");
    setBtDevices([]);
    try {
      const devices = await discoverBtDevices(8);
      if (devices.length === 0) {
        setScanError("找不到裝置。請確認 P710BT 已開機並在 Windows 藍牙設定配對過。");
      } else {
        setBtDevices(devices);
        // Auto-select if only one or if P710 found
        const p710 = devices.find(d => d.name.toLowerCase().includes("p710") || d.name.toLowerCase().includes("brother"));
        setBtDevice(p710 ?? devices[0]);
      }
    } catch (e: any) {
      setScanError(e.response?.data?.detail || e.message);
    } finally {
      setScanning(false);
    }
  };

  const handlePrint = async () => {
    if (data.length === 0) { setError("沒有資料可列印"); return; }
    if (transport === "bluetooth" && !btDevice) { setError("請先掃描並選擇藍牙裝置"); return; }
    setPrinting(true);
    setError("");
    setResult(null);
    try {
      const res = await printLabels({
        label_template: label,
        data,
        field_mapping: fieldMapping,
        transport_type: transport,
        bt_address: transport === "bluetooth" ? btDevice?.address : undefined,
        bt_channel: btChannel,
        usb_serial: usbSerial || undefined,
        margin_px: marginPx,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setPrinting(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-lg font-semibold mb-3">🖨️ 列印</h2>

      {/* Connection type */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <label className="text-xs text-gray-500">連接方式</label>
          <div className="flex gap-2 mt-1">
            {(["usb", "bluetooth"] as const).map((t) => (
              <button
                key={t}
                className={`flex-1 py-1.5 rounded border text-sm font-medium transition-colors ${
                  transport === t
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                }`}
                onClick={() => setTransport(t)}
              >
                {t === "usb" ? "🔌 USB" : "📶 藍牙"}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500">列印邊距 (dots)</label>
          <input
            type="number"
            className="w-full border rounded px-2 py-1.5 text-sm mt-1"
            value={marginPx}
            onChange={(e) => setMarginPx(Number(e.target.value))}
          />
        </div>
      </div>

      {/* USB selector */}
      {transport === "usb" && (
        <div className="mb-4">
          <label className="text-xs text-gray-500">印表機</label>
          <div className="flex gap-2 mt-1">
            <select
              className="flex-1 border rounded px-2 py-1.5 text-sm"
              value={usbSerial}
              onChange={(e) => setUsbSerial(e.target.value)}
            >
              <option value="">自動選擇</option>
              {printers.map((p) => (
                <option key={p.serial} value={p.serial}>
                  {p.product} ({p.serial})
                </option>
              ))}
            </select>
            <button
              className="text-sm px-3 py-1.5 border rounded hover:bg-gray-50"
              onClick={() => discoverPrinters().then(setPrinters).catch(() => {})}
            >
              搜尋
            </button>
          </div>
        </div>
      )}

      {/* BT scanner */}
      {transport === "bluetooth" && (
        <div className="mb-4 space-y-2">
          <div className="flex gap-2">
            <button
              className="flex-1 py-2 bg-blue-50 border border-blue-300 rounded text-sm text-blue-700 hover:bg-blue-100 disabled:opacity-50 font-medium"
              onClick={handleScanBt}
              disabled={scanning}
            >
              {scanning ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">⏳</span> 掃描中（約8秒）...
                </span>
              ) : (
                "🔍 掃描附近藍牙裝置"
              )}
            </button>
          </div>

          {scanError && (
            <p className="text-red-600 text-xs bg-red-50 p-2 rounded">{scanError}</p>
          )}

          {btDevices.length > 0 && (
            <div className="space-y-1">
              <label className="text-xs text-gray-500">選擇裝置</label>
              {btDevices.map((d) => (
                <button
                  key={d.address}
                  className={`w-full text-left px-3 py-2 rounded border text-sm transition-colors ${
                    btDevice?.address === d.address
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white hover:bg-gray-50 border-gray-200"
                  }`}
                  onClick={() => setBtDevice(d)}
                >
                  <span className="font-medium">{d.name}</span>
                  <span className={`ml-2 text-xs font-mono ${btDevice?.address === d.address ? "text-blue-200" : "text-gray-400"}`}>
                    {d.address}
                  </span>
                </button>
              ))}
            </div>
          )}

          {btDevice && (
            <div className="flex items-center gap-3 p-2 bg-green-50 rounded border border-green-200 text-sm">
              <span className="text-green-700">✅ 已選擇：<strong>{btDevice.name}</strong></span>
              <span className="text-gray-400 font-mono text-xs ml-auto">{btDevice.address}</span>
            </div>
          )}

          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 w-16">Channel</label>
            <input
              type="number"
              className="w-20 border rounded px-2 py-1 text-sm"
              value={btChannel}
              onChange={(e) => setBtChannel(Number(e.target.value))}
            />
            <span className="text-xs text-gray-400">（通常為 1）</span>
          </div>
        </div>
      )}

      {/* Print button */}
      <button
        className="w-full bg-green-600 text-white py-2.5 rounded font-medium hover:bg-green-700 disabled:opacity-50 text-sm"
        onClick={handlePrint}
        disabled={printing || data.length === 0}
      >
        {printing ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin">⏳</span> 列印中...
          </span>
        ) : (
          `🖨️ 列印 ${data.length} 張標籤`
        )}
      </button>

      {error && <p className="text-red-600 text-sm mt-2">{error}</p>}

      {result && (
        <div className="mt-3 p-3 bg-gray-50 rounded text-sm">
          <p className="font-medium text-green-700">
            ✅ 完成：{result.printed} / {result.total} 張
          </p>
          {result.results
            .filter((r) => r.status === "error")
            .map((r) => (
              <p key={r.index} className="text-red-600 text-xs mt-1">
                第 {r.index + 1} 張失敗：{r.message}
              </p>
            ))}
        </div>
      )}
    </div>
  );
}

