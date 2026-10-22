/** CSV, JSON, delimited text, and Excel (.xlsx) — same rules as the desktop app. */

function stripBom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

export function detectDelimiter(text) {
  const first = text.trim().split(/\r?\n/, 1)[0] || "";
  for (const delimiter of ["\t", "|", ";", ","]) {
    if (first.includes(delimiter)) return delimiter;
  }
  return ",";
}

export function parseCsv(text, delimiter = ",") {
  const source = stripBom(text);
  const table = [];
  let row = [];
  let cell = "";
  let quoted = false;

  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (quoted) {
      if (char === '"') {
        if (source[i + 1] === '"') {
          cell += '"';
          i += 1;
        } else quoted = false;
      } else cell += char;
    } else if (char === '"') {
      quoted = true;
    } else if (char === delimiter) {
      row.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      row.push(cell);
      table.push(row);
      row = [];
      cell = "";
      if (char === "\r" && source[i + 1] === "\n") i += 1;
    } else {
      cell += char;
    }
  }
  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    table.push(row);
  }

  const records = table.filter((line) => line.some((value) => value !== ""));
  if (records.length < 2) return [];
  const headers = records[0].map((header, index) => header || `col_${index}`);
  return records.slice(1).map((line) => {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = line[index] ?? "";
    });
    return record;
  });
}

export function parseJson(text) {
  const data = JSON.parse(stripBom(text));
  if (!Array.isArray(data)) throw new Error("JSON 必須是陣列");
  return data.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error("JSON 每一項都必須是物件");
    }
    const record = {};
    for (const [key, value] of Object.entries(item)) record[String(key)] = value == null ? "" : String(value);
    return record;
  });
}

export function parseDelimited(text, delimiter) {
  if (!delimiter) throw new Error("請填分隔符");
  const lines = stripBom(text).split(/\r?\n/).filter((line) => line.trim());
  if (lines.length === 0) return [];
  if (lines.length === 1) {
    return lines[0].split(delimiter).map((value) => value.trim()).filter(Boolean).map((value) => ({ value }));
  }
  return parseCsv(text, delimiter);
}

function u16(bytes, offset) {
  return bytes[offset] | (bytes[offset + 1] << 8);
}

function u32(bytes, offset) {
  return (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0;
}

async function inflateRaw(bytes) {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("這個瀏覽器讀不了 Excel，請改用 Chrome 或 Edge，或另存成 CSV");
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function unzip(buffer) {
  const bytes = new Uint8Array(buffer);
  let eocd = -1;
  const start = Math.max(0, bytes.length - 22 - 65536);
  for (let i = bytes.length - 22; i >= start; i -= 1) {
    if (bytes[i] === 0x50 && bytes[i + 1] === 0x4b && bytes[i + 2] === 0x05 && bytes[i + 3] === 0x06) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("這不是有效的 Excel 檔（.xlsx）");

  const files = new Map();
  let cursor = u32(bytes, eocd + 16);
  const count = u16(bytes, eocd + 10);
  for (let n = 0; n < count; n += 1) {
    if (u32(bytes, cursor) !== 0x02014b50) break;
    const method = u16(bytes, cursor + 10);
    const compressedSize = u32(bytes, cursor + 20);
    const nameLength = u16(bytes, cursor + 28);
    const extraLength = u16(bytes, cursor + 30);
    const commentLength = u16(bytes, cursor + 32);
    const localOffset = u32(bytes, cursor + 42);
    const name = new TextDecoder().decode(bytes.subarray(cursor + 46, cursor + 46 + nameLength));
    cursor += 46 + nameLength + extraLength + commentLength;

    const localNameLength = u16(bytes, localOffset + 26);
    const localExtraLength = u16(bytes, localOffset + 28);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const compressed = bytes.subarray(dataStart, dataStart + compressedSize);
    let raw;
    if (method === 0) raw = compressed;
    else if (method === 8) raw = await inflateRaw(compressed);
    else throw new Error("這個 Excel 的壓縮方式不支援，請另存一次或改用 CSV");
    files.set(name, raw);
  }
  return files;
}

function localElements(root, name) {
  const found = [];
  const walk = (node) => {
    for (const child of node.children || []) {
      if (child.localName === name) found.push(child);
      walk(child);
    }
  };
  walk(root);
  return found;
}

function textOf(node) {
  return localElements(node, "t").map((item) => item.textContent || "").join("");
}

function columnIndex(ref) {
  let value = 0;
  for (const char of ref) {
    const code = char.toUpperCase().charCodeAt(0);
    if (code < 65 || code > 90) break;
    value = value * 26 + (code - 64);
  }
  return value - 1;
}

export async function parseExcel(buffer) {
  const files = await unzip(buffer);
  let sheetName = "xl/worksheets/sheet1.xml";
  if (!files.has(sheetName)) {
    sheetName = [...files.keys()].filter((name) => /^xl\/worksheets\/sheet\d+\.xml$/.test(name)).sort()[0];
  }
  if (!sheetName) throw new Error("Excel 裡找不到工作表");

  const shared = [];
  if (files.has("xl/sharedStrings.xml")) {
    const xml = new DOMParser().parseFromString(new TextDecoder().decode(files.get("xl/sharedStrings.xml")), "application/xml");
    for (const item of localElements(xml.documentElement, "si")) shared.push(textOf(item));
  }

  const sheet = new DOMParser().parseFromString(new TextDecoder().decode(files.get(sheetName)), "application/xml");
  const rows = [];
  for (const row of localElements(sheet.documentElement, "row")) {
    const cells = [];
    for (const cell of localElements(row, "c")) {
      const ref = cell.getAttribute("r") || "";
      const index = columnIndex(ref);
      if (index < 0) continue;
      const kind = cell.getAttribute("t") || "";
      const raw = localElements(cell, "v")[0]?.textContent ?? "";
      let value = raw;
      if (kind === "s") value = shared[Number(raw)] ?? "";
      else if (kind === "inlineStr") value = textOf(cell);
      cells[index] = value ?? "";
    }
    if (cells.length) rows.push(cells);
  }
  if (rows.length < 2) return [];

  const width = Math.max(...rows.map((row) => row.length));
  const headers = [];
  for (let i = 0; i < width; i += 1) headers.push(rows[0][i] || `col_${i}`);
  return rows.slice(1).map((row) => {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = row[index] ?? "";
    });
    return record;
  });
}

export async function parseAuto({ text = null, buffer = null, format = "auto", delimiter = null } = {}) {
  if (format === "excel") {
    if (!buffer) throw new Error("沒有 Excel 檔");
    return parseExcel(buffer);
  }
  if (text == null) throw new Error("沒有文字資料");
  if (format === "json") return parseJson(text);
  if (format === "csv") return parseCsv(text, delimiter || detectDelimiter(text));
  if (format === "delimited") return parseDelimited(text, delimiter);
  const trimmed = text.trim();
  if (trimmed.startsWith("[")) {
    try {
      return parseJson(trimmed);
    } catch (error) {
      if (error instanceof SyntaxError) return parseCsv(trimmed, delimiter || detectDelimiter(trimmed));
      throw error;
    }
  }
  return parseCsv(trimmed, delimiter || detectDelimiter(trimmed));
}
