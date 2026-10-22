import { parseAuto } from "./parser.js";
import { renderLabel, tapeLabel, TAPE_WIDTHS } from "./label.js";
import {
  grantedDevices,
  openDevice,
  printCanvases,
  productName,
  readStatus,
  requestDevice,
  usbSupported,
} from "./printer.js";

const $ = (id) => document.getElementById(id);
const FIELD_TYPES = [
  ["text", "文字"],
  ["qr", "QR Code"],
  ["code128", "CODE128"],
  ["code39", "CODE39"],
  ["ean13", "EAN13"],
];

const state = {
  rows: [],
  columns: [],
  checked: [],
  types: {},
  selected: new Set(),
  previews: [],
  previewIndex: 0,
  device: null,
  anchor: null,
};

const settingsKey = "p710bt-web-settings";

function setStatus(text) {
  $("status").textContent = text;
}

function showError(message) {
  const box = $("error-box");
  box.hidden = !message;
  box.textContent = message || "";
}

function readSettings() {
  return {
    tapeWidthMm: Number($("tape-select").value),
    fontFamily: $("font-select").value,
    fontSize: Number($("font-size").value) || null,
    marginPx: Number($("margin-input").value) || 0,
    spacingPx: 6,
  };
}

function saveSettings() {
  const data = {
    tape: $("tape-select").value,
    font: $("font-select").value,
    fontSize: $("font-size").value,
    margin: $("margin-input").value,
    printMargin: $("print-margin").value,
    chain: $("chain-check").checked,
  };
  localStorage.setItem(settingsKey, JSON.stringify(data));
}

function loadSettings() {
  try {
    const data = JSON.parse(localStorage.getItem(settingsKey) || "{}");
    if (data.tape) $("tape-select").value = data.tape;
    if (data.font) $("font-select").value = data.font;
    if (data.fontSize != null) $("font-size").value = data.fontSize;
    if (data.margin != null) $("margin-input").value = data.margin;
    if (data.printMargin != null) $("print-margin").value = data.printMargin;
    if (typeof data.chain === "boolean") $("chain-check").checked = data.chain;
  } catch { /* keep defaults */ }
}

function activeColumns() {
  return state.columns.filter((column) => state.checked.includes(column));
}

function buildSpec(row) {
  const settings = readSettings();
  const columns = activeColumns();
  const fields = (columns.length ? columns : ["標籤"]).map((column) => ({
    type: columns.length ? (state.types[column] || "text") : "text",
    value: row ? String(row[column] ?? "") : column,
  }));
  return { ...settings, fields };
}

function updatePrintButton() {
  const count = state.rows.length;
  $("print-btn").textContent = `列印 ${count} 張標籤`;
  $("print-btn").disabled = count === 0;
}

function renderColumns() {
  const host = $("columns");
  host.innerHTML = "";
  host.hidden = state.columns.length === 0;
  for (const column of state.columns) {
    const chip = document.createElement("label");
    chip.className = "chip";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = state.checked.includes(column);
    box.addEventListener("change", () => {
      if (box.checked) state.checked.push(column);
      else state.checked = state.checked.filter((item) => item !== column);
      state.checked = state.columns.filter((item) => state.checked.includes(item));
      selectEl.disabled = !box.checked;
      renderTable();
      schedulePreview();
    });
    const selectEl = document.createElement("select");
    for (const [value, label] of FIELD_TYPES) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      selectEl.append(option);
    }
    selectEl.value = state.types[column] || "text";
    selectEl.disabled = !box.checked;
    selectEl.addEventListener("change", () => {
      state.types[column] = selectEl.value;
      schedulePreview();
    });
    chip.append(box, document.createTextNode(column), selectEl);
    host.append(chip);
  }
}

function renderTable() {
  const head = $("data-table").tHead;
  const body = $("data-table").tBodies[0];
  const shown = state.rows.slice(0, 50);
  head.innerHTML = "";
  body.innerHTML = "";
  if (!state.columns.length) {
    $("count-label").textContent = "尚未載入資料。表格最多顯示前 50 筆，列印會用全部。";
    $("delete-btn").disabled = true;
    return;
  }
  const header = document.createElement("tr");
  for (const name of ["#", ...state.columns]) {
    const cell = document.createElement("th");
    cell.textContent = name;
    header.append(cell);
  }
  head.append(header);
  shown.forEach((row, index) => {
    const tr = document.createElement("tr");
    if (state.selected.has(index)) tr.classList.add("selected");
    const number = document.createElement("td");
    number.textContent = String(index + 1);
    tr.append(number);
    for (const column of state.columns) {
      const cell = document.createElement("td");
      cell.textContent = row[column] ?? "";
      if (!state.checked.includes(column)) cell.style.color = "#94a3b8";
      tr.append(cell);
    }
    tr.addEventListener("click", (event) => {
      $("data-table").focus();
      selectRow(index, event);
    });
    body.append(tr);
  });
  const extra = state.rows.length > shown.length ? `（表格只顯示前 ${shown.length} 筆）` : "";
  $("count-label").textContent = `共 ${state.rows.length} 筆資料　·　已選 ${activeColumns().length} / ${state.columns.length} 列${extra}`;
  $("delete-btn").disabled = state.selected.size === 0;
}

function selectRow(index, event) {
  if (event.shiftKey && state.anchor != null) {
    const [start, end] = [state.anchor, index].sort((a, b) => a - b);
    if (!event.ctrlKey && !event.metaKey) state.selected.clear();
    for (let i = start; i <= end; i += 1) state.selected.add(i);
  } else if (event.ctrlKey || event.metaKey) {
    if (state.selected.has(index)) state.selected.delete(index);
    else state.selected.add(index);
    state.anchor = index;
  } else {
    state.selected.clear();
    state.selected.add(index);
    state.anchor = index;
  }
  renderTable();
  $("data-table").focus();
}

function deleteSelected() {
  const indexes = [...state.selected].sort((a, b) => b - a);
  for (const index of indexes) state.rows.splice(index, 1);
  state.selected.clear();
  renderTable();
  updatePrintButton();
  schedulePreview();
}

function setRows(rows, filename) {
  showError("");
  if (!rows.length) {
    showError("解析結果為空");
    return;
  }
  state.rows = rows;
  state.columns = Object.keys(rows[0]);
  state.checked = [...state.columns];
  state.types = Object.fromEntries(state.columns.map((column) => [column, state.types[column] || "text"]));
  state.selected.clear();
  if (filename) $("file-label").textContent = filename;
  renderColumns();
  renderTable();
  updatePrintButton();
  schedulePreview();
  setStatus(`已載入 ${rows.length} 筆資料，共 ${state.columns.length} 列`);
}

async function parseText() {
  const text = $("paste-input").value.trim();
  if (!text) return;
  try {
    const rows = await parseAuto({
      text,
      format: $("format-select").value,
      delimiter: $("delim-input").value,
    });
    setRows(rows);
  } catch (error) {
    showError(error.message || String(error));
  }
}

async function parseFile(file) {
  $("file-label").textContent = `載入中… ${file.name}`;
  try {
    const ext = file.name.split(".").pop().toLowerCase();
    if (ext === "xls") throw new Error(".xls 舊格式不支援，請另存成 .xlsx");
    if (ext === "xlsx") {
      setRows(await parseAuto({ buffer: await file.arrayBuffer(), format: "excel" }), file.name);
      return;
    }
    const text = await file.text();
    const format = ext === "json" ? "json" : "csv";
    setRows(await parseAuto({ text, format }), file.name);
  } catch (error) {
    $("file-label").textContent = "支援 Excel、JSON、CSV";
    showError(error.message || String(error));
  }
}

function schedulePreview() {
  window.clearTimeout(schedulePreview.timer);
  schedulePreview.timer = window.setTimeout(updatePreview, 250);
}

function updatePreview() {
  const rows = state.rows.slice(0, 10);
  const specs = rows.length ? rows.map((row) => buildSpec(row)) : [buildSpec(null)];
  state.previews = [];
  const errors = [];
  specs.forEach((spec, index) => {
    try {
      state.previews.push(renderLabel(spec));
    } catch (error) {
      errors.push(`第 ${index + 1} 張：${error.message || error}`);
    }
  });
  if (errors.length) showError(errors.join("；"));
  state.previewIndex = Math.min(state.previewIndex, Math.max(0, state.previews.length - 1));
  showPreview();
  updatePrintButton();
}

function showPreview() {
  const image = $("preview-img");
  const empty = $("preview-empty");
  const canvas = state.previews[state.previewIndex];
  if (!canvas) {
    image.hidden = true;
    image.removeAttribute("src");
    empty.hidden = false;
    empty.textContent = "尚無預覽";
    $("nav").hidden = true;
    $("full-btn").disabled = true;
    return;
  }
  const scale = Math.min(4, Math.max(2, Math.ceil(160 / canvas.height)));
  image.src = canvas.toDataURL("image/png");
  image.style.width = `${canvas.width * scale}px`;
  image.style.maxWidth = "100%";
  image.style.height = "auto";
  image.hidden = false;
  empty.hidden = true;
  $("full-btn").disabled = false;
  const many = state.previews.length > 1;
  $("nav").hidden = !many;
  $("nav-label").textContent = `${state.previewIndex + 1} / ${state.previews.length}`;
  $("prev-btn").disabled = state.previewIndex === 0;
  $("next-btn").disabled = state.previewIndex >= state.previews.length - 1;
}

function openFull() {
  const canvas = state.previews[state.previewIndex];
  if (!canvas) return;
  $("full-img").src = canvas.toDataURL("image/png");
  $("full-caption").textContent = `標籤預覽　${state.previewIndex + 1} / ${state.previews.length}`;
  $("full-dialog").showModal();
}

function rememberDevice(device) {
  state.device = device;
  const select = $("printer-select");
  select.innerHTML = "";
  const option = document.createElement("option");
  option.value = "0";
  const serial = device.serialNumber ? `（${device.serialNumber}）` : "";
  option.textContent = `${productName(device)}${serial}`;
  select.append(option);
}

async function connectPrinter(pickNew) {
  $("connect-btn").disabled = true;
  try {
    const device = pickNew ? await requestDevice() : state.device;
    if (!device) throw new Error("尚未選擇打印機");
    await openDevice(device);
    rememberDevice(device);
    const status = await readStatus(device);
    if (TAPE_WIDTHS.includes(status.mediaWidth)) {
      $("tape-select").value = String(status.mediaWidth);
      saveSettings();
      schedulePreview();
      $("tape-info").hidden = false;
      $("tape-info").textContent = `偵測到膠帶寬度：${tapeLabel(status.mediaWidth)}（已套用）`;
    } else {
      $("tape-info").hidden = false;
      $("tape-info").textContent = "已連接，但沒有讀到膠帶寬度。請確認膠帶已裝上。";
    }
    setStatus("打印機已連接");
  } catch (error) {
    if (error.name === "NotFoundError") setStatus("沒有選擇打印機");
    else showResult(error.message || String(error), true);
  } finally {
    $("connect-btn").disabled = false;
  }
}

function showResult(text, failed) {
  const result = $("result");
  result.hidden = false;
  result.className = failed ? "error" : "ok";
  result.textContent = text;
}

async function printLabels() {
  if (!state.rows.length) return;
  const specs = [];
  try {
    for (const row of state.rows) specs.push(renderLabel(buildSpec(row)));
  } catch (error) {
    showResult(error.message || String(error), true);
    return;
  }
  if (!state.device) {
    try {
      await connectPrinter(true);
    } catch { return; }
    if (!state.device) return;
  }
  $("print-btn").disabled = true;
  const progress = $("progress");
  progress.hidden = false;
  progress.max = specs.length;
  progress.value = 0;
  showResult("正在列印…", false);
  try {
    await openDevice(state.device);
    const outcome = await printCanvases(state.device, specs, {
      marginDots: Number($("print-margin").value) || 0,
      chainPrint: $("chain-check").checked,
      onProgress(current, total) {
        progress.value = current;
        setStatus(`正在列印 ${current} / ${total}`);
      },
    });
    const lines = [`完成：${outcome.printed} / ${outcome.total} 張`, ...outcome.errors];
    showResult(lines.join("\n"), outcome.errors.length > 0);
    setStatus("列印結束");
  } catch (error) {
    showResult(error.message || String(error), true);
  } finally {
    progress.hidden = true;
    updatePrintButton();
  }
}

async function restorePrinters() {
  try {
    const devices = await grantedDevices();
    if (!devices.length) return;
    rememberDevice(devices[0]);
    await connectPrinter(false);
  } catch { /* permission or cable can wait for the button */ }
}

function setupInstall() {
  let promptEvent = null;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    promptEvent = event;
    $("install-btn").hidden = false;
  });
  $("install-btn").addEventListener("click", async () => {
    if (!promptEvent) return;
    promptEvent.prompt();
    await promptEvent.userChoice;
    promptEvent = null;
    $("install-btn").hidden = true;
  });
  if (window.matchMedia("(display-mode: standalone)").matches) {
    setStatus("已安裝在這部電腦，可以離線設計標籤");
  }
}

function setupContextNote() {
  const note = $("context-note");
  if (location.protocol === "file:") {
    note.hidden = false;
    note.textContent = "請用瀏覽器打開 GitHub Pages 上的這個網頁，不要直接雙擊檔案。否則無法連接打印機，也無法安裝。";
  } else if (!usbSupported()) {
    note.hidden = false;
    note.textContent = "這個瀏覽器不能直接連接 USB。設計和預覽仍然可用；列印請改用 Chrome 或 Edge。";
  }
}

function bind() {
  $("format-select").addEventListener("change", () => {
    $("delim-label").hidden = $("format-select").value !== "delimited";
  });
  $("parse-btn").addEventListener("click", parseText);
  $("paste-input").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") parseText();
  });
  $("sample-btn").addEventListener("click", async () => {
    try {
      const response = await fetch("./sample.csv");
      const text = await response.text();
      $("paste-input").value = text;
      $("format-select").value = "csv";
      $("delim-label").hidden = true;
      setRows(await parseAuto({ text, format: "csv" }), "範例資料");
    } catch (error) {
      showError(error.message || String(error));
    }
  });
  $("file-btn").addEventListener("click", () => $("file-input").click());
  $("file-input").addEventListener("change", () => {
    const file = $("file-input").files[0];
    if (file) parseFile(file);
    $("file-input").value = "";
  });
  $("delete-btn").addEventListener("click", deleteSelected);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Delete" && document.activeElement?.closest("#data-table")) deleteSelected();
  });
  for (const id of ["tape-select", "font-select", "font-size", "margin-input", "print-margin", "chain-check"]) {
    $(id).addEventListener("change", () => {
      saveSettings();
      schedulePreview();
    });
  }
  $("refresh-btn").addEventListener("click", updatePreview);
  $("full-btn").addEventListener("click", openFull);
  $("preview-stage").addEventListener("click", openFull);
  $("prev-btn").addEventListener("click", () => {
    state.previewIndex -= 1;
    showPreview();
  });
  $("next-btn").addEventListener("click", () => {
    state.previewIndex += 1;
    showPreview();
  });
  $("connect-btn").addEventListener("click", () => connectPrinter(true));
  $("print-btn").addEventListener("click", printLabels);
}

loadSettings();
bind();
setupInstall();
setupContextNote();
updatePreview();
restorePrinters();

if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
