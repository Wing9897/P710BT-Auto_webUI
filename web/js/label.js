import { encodeBarcode } from "./barcode.js";
import { qrModules } from "./qr.js";

export const TAPE_MARGINS = { 4: 52, 6: 48, 9: 39, 12: 29, 18: 8, 24: 0 };
export const TAPE_WIDTHS = [4, 6, 9, 12, 18, 24];

export function tapeLabel(mm) {
  return mm === 4 ? "3.5 mm" : `${mm} mm`;
}

export function printWidth(mm) {
  const margin = TAPE_MARGINS[mm];
  if (margin == null) throw new Error("不支援的膠帶寬度");
  return 128 - margin * 2;
}

const measureCanvas = document.createElement("canvas");
const measure = measureCanvas.getContext("2d");

function lineMetrics(family, size, sample = "國Ay") {
  measure.font = `${size}px ${family}`;
  const metrics = measure.measureText(sample);
  const ascent = metrics.actualBoundingBoxAscent || size * 0.8;
  const descent = metrics.actualBoundingBoxDescent || size * 0.2;
  return { ascent, descent, height: Math.max(1, ascent + descent) };
}

function lineBox(family, size) {
  return lineMetrics(family, size).height;
}

function textWidth(text, family, size) {
  measure.font = `${size}px ${family}`;
  return measure.measureText(text || " ").width;
}

function wrapText(text, family, size, maxWidth) {
  const lines = [];
  for (const paragraph of String(text).split("\n")) {
    if (!paragraph) {
      lines.push("");
      continue;
    }
    if (textWidth(paragraph, family, size) <= maxWidth) {
      lines.push(paragraph);
      continue;
    }
    let current = "";
    for (const char of paragraph) {
      const next = current + char;
      if (textWidth(next, family, size) <= maxWidth) current = next;
      else {
        if (current) lines.push(current);
        current = char;
      }
    }
    if (current) lines.push(current);
  }
  return lines.length ? lines : [""];
}

function renderText(text, targetH, family, fontSize) {
  const sample = String(text).split("\n")[0] || " ";
  let size = fontSize;
  if (!size) {
    let lo = 6;
    let hi = Math.max(6, targetH * 2);
    size = 10;
    for (let i = 0; i < 20; i += 1) {
      const mid = Math.floor((lo + hi) / 2);
      if (lineBox(family, mid) <= targetH) {
        size = mid;
        lo = mid + 1;
      } else hi = mid - 1;
    }
  }

  let lines = wrapText(text, family, size, 10000);
  let lineH = lineBox(family, size);
  let totalH = lineH * lines.length + 2 * Math.max(0, lines.length - 1);
  while (totalH > targetH && size > 6) {
    size -= 1;
    lines = wrapText(text, family, size, 10000);
    lineH = lineBox(family, size);
    totalH = lineH * lines.length + 2 * Math.max(0, lines.length - 1);
  }

  const widths = lines.map((line) => Math.ceil(textWidth(line, family, size)));
  const width = Math.max(1, ...widths);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = targetH;
  const ctx = canvas.getContext("2d");
  ctx.font = `${size}px ${family}`;
  ctx.fillStyle = "#000";
  ctx.textBaseline = "alphabetic";
  let y = Math.max(0, Math.floor((targetH - totalH) / 2));
  lines.forEach((line, index) => {
    const { ascent } = lineMetrics(family, size, line || "國");
    const x = Math.floor((width - widths[index]) / 2);
    ctx.fillText(line, x, y + ascent);
    y += lineH + 2;
  });
  return canvas;
}

function renderQr(value, targetH) {
  const modules = qrModules(value);
  const count = modules.length + 2;
  const box = Math.max(1, Math.floor(targetH / count));
  const canvas = document.createElement("canvas");
  canvas.width = targetH;
  canvas.height = targetH;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, targetH, targetH);
  ctx.fillStyle = "#000";
  const offset = Math.floor((targetH - box * count) / 2);
  for (let row = 0; row < modules.length; row += 1) {
    for (let col = 0; col < modules.length; col += 1) {
      if (!modules[row][col]) continue;
      ctx.fillRect(offset + (col + 1) * box, offset + (row + 1) * box, box, box);
    }
  }
  return canvas;
}

function renderBarcode(type, value, targetH) {
  const bits = encodeBarcode(type, value);
  const module = 2;
  const canvas = document.createElement("canvas");
  canvas.width = bits.length * module;
  canvas.height = targetH;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#000";
  for (let i = 0; i < bits.length; i += 1) {
    if (bits[i] === "1") ctx.fillRect(i * module, 0, module, targetH);
  }
  return canvas;
}

export function renderLabel(spec) {
  const tapeH = printWidth(spec.tapeWidthMm);
  const contentH = Math.max(4, tapeH - 2 * spec.marginPx);
  const family = spec.fontFamily || "sans-serif";
  const parts = [];

  for (const field of spec.fields) {
    if (!String(field.value ?? "").length) continue;
    const size = field.fontSize || spec.fontSize || null;
    const renderH = size ? Math.min(size, contentH) : contentH;
    if (field.type === "text") parts.push(renderText(field.value, renderH, family, size));
    else if (field.type === "qr") parts.push(renderQr(field.value, renderH));
    else parts.push(renderBarcode(field.type, field.value, renderH));
  }

  const canvas = document.createElement("canvas");
  if (parts.length === 0) {
    canvas.width = Math.max(10, tapeH);
    canvas.height = tapeH;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    return canvas;
  }

  const spacing = spec.spacingPx ?? 6;
  const totalW = parts.reduce((sum, part) => sum + part.width, 0)
    + spacing * (parts.length - 1)
    + 2 * spec.marginPx;
  canvas.width = Math.max(1, totalW);
  canvas.height = tapeH;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  let x = spec.marginPx;
  for (const part of parts) {
    const y = Math.floor((tapeH - part.height) / 2);
    ctx.drawImage(part, x, y);
    x += part.width + spacing;
  }
  return canvas;
}
