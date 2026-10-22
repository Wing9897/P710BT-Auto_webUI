import { packbitsEncode } from "./packbits.js";
import { TAPE_MARGINS, printWidth } from "./label.js";

const VENDOR_ID = 0x04f9;
const PRODUCTS = [
  { id: 0x2060, name: "E550W" },
  { id: 0x2062, name: "P750W" },
  { id: 0x20af, name: "P710BT" },
];
const LINE_BYTES = 16;
const STATUS_LENGTH = 32;

const filters = PRODUCTS.map((product) => ({ vendorId: VENDOR_ID, productId: product.id }));

export function usbSupported() {
  return typeof navigator !== "undefined" && "usb" in navigator && window.isSecureContext;
}

export function productName(device) {
  return PRODUCTS.find((item) => item.id === device.productId)?.name
    || device.productName
    || "Brother";
}

function bytes(...parts) {
  const chunks = parts.map((part) => (part instanceof Uint8Array ? part : Uint8Array.from(part)));
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const out = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

function u16le(value) {
  return [value & 0xff, (value >> 8) & 0xff];
}

function u32le(value) {
  return [value & 0xff, (value >> 8) & 0xff, (value >> 16) & 0xff, (value >> 24) & 0xff];
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function write(device, endpoint, data) {
  let sent = 0;
  while (sent < data.length) {
    const chunk = data.subarray(sent, sent + 0x40);
    const result = await device.transferOut(endpoint, chunk);
    if (!result.bytesWritten) throw new Error("寫入打印機逾時");
    sent += result.bytesWritten;
  }
}

async function read(device, endpoint, length = 0x80) {
  try {
    const result = await device.transferIn(endpoint, length);
    if (!result.data) return new Uint8Array(0);
    return new Uint8Array(result.data.buffer, result.data.byteOffset, result.data.byteLength);
  } catch {
    return new Uint8Array(0);
  }
}

function findInterface(device) {
  for (const iface of device.configuration.interfaces) {
    for (const alt of iface.alternates) {
      const outEp = alt.endpoints.find((ep) => ep.direction === "out");
      const inEp = alt.endpoints.find((ep) => ep.direction === "in");
      if (outEp && inEp) {
        return {
          number: iface.interfaceNumber,
          alternate: alt.alternateSetting,
          outEp: alt.endpoints.find((ep) => ep.direction === "out" && ep.endpointNumber === 2)?.endpointNumber || outEp.endpointNumber,
          inEp: alt.endpoints.find((ep) => ep.direction === "in" && ep.endpointNumber === 1)?.endpointNumber || inEp.endpointNumber,
        };
      }
    }
  }
  throw new Error("打印機的 USB 介面不正確");
}

export async function requestDevice() {
  if (!usbSupported()) {
    throw new Error("請用 Chrome 或 Edge 打開這個網頁。直接雙擊 html 檔無法連接 USB。");
  }
  const device = await navigator.usb.requestDevice({ filters });
  await openDevice(device);
  return device;
}

export async function grantedDevices() {
  if (!usbSupported()) return [];
  return navigator.usb.getDevices();
}

export async function openDevice(device) {
  if (!device.opened) await device.open();
  if (device.configuration == null) await device.selectConfiguration(1);
  const iface = findInterface(device);
  try {
    await device.claimInterface(iface.number);
  } catch {
    throw new Error("無法佔用打印機。請關閉桌面程式，或其他正在使用打印機的程式。");
  }
  if (iface.alternate) await device.selectAlternateInterface(iface.number, iface.alternate);
  device.__p710 = iface;
  return device;
}

function statusError(raw) {
  const messages = [];
  const e1 = raw[8];
  const e2 = raw[9];
  if (e1 & 0x01) messages.push("沒有膠帶");
  if (e1 & 0x04) messages.push("裁刀卡住");
  if (e1 & 0x08) messages.push("電量不足");
  if (e1 & 0x40) messages.push("變壓器電壓異常");
  if (e2 & 0x01) messages.push("膠帶不適用");
  if (e2 & 0x10) messages.push("蓋子打開");
  if (e2 & 0x20) messages.push("過熱");
  return messages.join("、") || "打印機發生未知錯誤";
}

export async function readStatus(device) {
  const { outEp, inEp } = device.__p710;
  await write(device, outEp, new Uint8Array(100));
  await write(device, outEp, Uint8Array.of(0x1b, 0x40));
  for (let attempt = 0; attempt < 10; attempt += 1) {
    await write(device, outEp, Uint8Array.of(0x1b, 0x69, 0x53));
    const raw = await read(device, inEp, 0x80);
    if (raw.length >= STATUS_LENGTH) {
      return { mediaWidth: raw[10], raw };
    }
    await delay(80);
  }
  throw new Error("打印機沒有回應");
}

function imageToMask(canvas, mediaWidth) {
  const expected = printWidth(mediaWidth);
  const source = canvas;
  let image = source;
  if (source.height !== expected) {
    image = document.createElement("canvas");
    if (source.width === expected) {
      image.width = source.height;
      image.height = source.width;
      const ctx = image.getContext("2d");
      ctx.translate(image.width / 2, image.height / 2);
      ctx.rotate(Math.PI / 2);
      ctx.drawImage(source, -source.width / 2, -source.height / 2);
    } else {
      image.width = Math.max(1, Math.round(source.width * expected / source.height));
      image.height = expected;
      image.getContext("2d").drawImage(source, 0, 0, image.width, image.height);
    }
  }

  const ctx = image.getContext("2d", { willReadFrequently: true });
  const pixels = ctx.getImageData(0, 0, image.width, image.height).data;
  const margin = TAPE_MARGINS[mediaWidth];
  const buffer = new Uint8Array(image.width * 128);
  for (let x = 0; x < image.width; x += 1) {
    let offset = x * 128 + margin;
    for (let y = 0; y < image.height; y += 1) {
      const i = (y * image.width + x) * 4;
      const alpha = pixels[i + 3] / 255;
      const red = pixels[i] * alpha + 255 * (1 - alpha);
      const green = pixels[i + 1] * alpha + 255 * (1 - alpha);
      const blue = pixels[i + 2] * alpha + 255 * (1 - alpha);
      const gray = 0.299 * red + 0.587 * green + 0.114 * blue;
      buffer[offset] = gray < 128 ? 0xff : 0;
      offset += 1;
    }
  }

  const bits = new Uint8Array(buffer.length / 8);
  for (let i = 0; i < buffer.length; i += 8) {
    let byte = 0;
    for (let bit = 0; bit < 8; bit += 1) {
      if (buffer[i + bit] > 0) byte |= 1 << (7 - bit);
    }
    bits[i / 8] = byte;
  }
  return bits;
}

function rasterCommands(bits) {
  const commands = [];
  for (let i = 0; i < bits.length; i += LINE_BYTES) {
    const line = bits.subarray(i, i + LINE_BYTES);
    let blank = true;
    for (const value of line) if (value !== 0) blank = false;
    if (blank) commands.push(Uint8Array.of(0x5a));
    else {
      const packed = packbitsEncode(line);
      commands.push(bytes([0x47], u16le(packed.length), packed));
    }
  }
  return commands;
}

async function printRaster(device, raster, mediaWidth, marginDots, lastPage, chainPrint) {
  const { outEp, inEp } = device.__p710;
  await write(device, outEp, Uint8Array.of(0x1b, 0x69, 0x61, 0x01));
  await write(device, outEp, Uint8Array.of(0x1b, 0x69, 0x21, 0x00));
  await write(device, outEp, bytes(
    [0x1b, 0x69, 0x7a, 0x84, 0x00, mediaWidth & 0xff, 0x00],
    u32le(raster.length >> 4),
    [0x00, 0x00],
  ));
  await write(device, outEp, Uint8Array.of(0x1b, 0x69, 0x4d, 0x40));
  await write(device, outEp, Uint8Array.of(0x1b, 0x69, 0x4b, chainPrint ? 0x00 : 0x08));
  await write(device, outEp, bytes([0x1b, 0x69, 0x64], u16le(marginDots)));
  await write(device, outEp, Uint8Array.of(0x4d, 0x02));
  for (const command of rasterCommands(raster)) await write(device, outEp, command);
  await write(device, outEp, Uint8Array.of(lastPage ? 0x1a : 0x0c));

  for (let attempt = 0; attempt < 300; attempt += 1) {
    const res = await read(device, inEp, 0x80);
    if (res.length < STATUS_LENGTH) {
      await delay(100);
      continue;
    }
    const kind = res[18];
    if (kind === 0x01) {
      try { await read(device, inEp, 0x80); } catch { /* phase change is optional */ }
      return;
    }
    if (kind === 0x02) throw new Error(statusError(res));
    if (kind === 0x04) throw new Error("打印途中打印機已關閉");
  }
  throw new Error("打印機沒有確認列印完成");
}

export async function printCanvases(device, canvases, { marginDots = 0, chainPrint = true, onProgress } = {}) {
  let printed = 0;
  const errors = [];
  for (let i = 0; i < canvases.length; i += 1) {
    try {
      const status = await readStatus(device);
      const mediaWidth = status.mediaWidth;
      if (TAPE_MARGINS[mediaWidth] == null) {
        throw new Error(mediaWidth ? `不支援的膠帶寬度 ${mediaWidth} mm` : "打印機沒有偵測到膠帶");
      }
      const raster = imageToMask(canvases[i], mediaWidth);
      const lastPage = i === canvases.length - 1;
      await printRaster(device, raster, mediaWidth, marginDots, lastPage, chainPrint);
      printed += 1;
    } catch (error) {
      errors.push(`第 ${i + 1} 張失敗：${error.message || error}`);
    }
    if (onProgress) onProgress(i + 1, canvases.length);
  }
  return { printed, total: canvases.length, errors };
}
