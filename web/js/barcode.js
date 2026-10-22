import {
  CODE128,
  CODE128_STOP,
  CODE39,
  CODE39_EDGE,
  CODE39_GAP,
  CODE39_REF,
} from "./patterns.js";

const EAN_A = [
  "0001101", "0011001", "0010011", "0111101", "0100011",
  "0110001", "0101111", "0111011", "0110111", "0001011",
];
const EAN_B = [
  "0100111", "0110011", "0011011", "0100001", "0011101",
  "0111001", "0000101", "0010001", "0001001", "0010111",
];
const EAN_C = [
  "1110010", "1100110", "1101100", "1000010", "1011100",
  "1001110", "1010000", "1000100", "1001000", "1110100",
];
const EAN_LEFT = [
  "AAAAAA", "AABABB", "AABBAB", "AABBBA", "ABAABB",
  "ABBAAB", "ABBBAA", "ABABAB", "ABABBA", "ABBABA",
];

function code128Value(char) {
  const code = char.charCodeAt(0);
  if (code < 32 || code > 126) {
    throw new Error(`CODE128 不支援這個字元：${char}`);
  }
  return code - 32;
}

/** Code 128, code set B. Quiet zone included. */
export function encodeCode128(value) {
  if (!value) throw new Error("CODE128 內容是空的");
  const values = [104];
  for (const char of value) values.push(code128Value(char));
  let checksum = values[0];
  for (let i = 1; i < values.length; i += 1) checksum += i * values[i];
  values.push(checksum % 103);

  let bits = "0".repeat(10);
  for (const code of values) bits += CODE128[code];
  bits += CODE128_STOP;
  bits += "11";
  bits += "0".repeat(10);
  return bits;
}

function code39Checksum(value) {
  let sum = 0;
  for (const char of value) sum += CODE39_REF.indexOf(char);
  return CODE39_REF[sum % 43];
}

/** Code 39 with the same checksum the desktop app adds. */
export function encodeCode39(value) {
  const text = value.toUpperCase();
  if (!text) throw new Error("CODE39 內容是空的");
  for (const char of text) {
    if (!CODE39[char]) throw new Error(`CODE39 不支援這個字元：${char}`);
  }
  const full = text + code39Checksum(text);
  const parts = [CODE39_EDGE];
  for (const char of full) parts.push(CODE39[char]);
  parts.push(CODE39_EDGE);
  return "0".repeat(10) + parts.join(CODE39_GAP) + "0".repeat(10);
}

function eanChecksum(twelve) {
  let even = 0;
  let odd = 0;
  for (let i = 0; i < twelve.length; i += 1) {
    const digit = twelve.charCodeAt(i) - 48;
    if ((twelve.length - i) % 2 === 0) even += digit;
    else odd += digit;
  }
  return (10 - ((even + odd * 3) % 10)) % 10;
}

/** EAN-13. 12 digits get a checksum; 13 digits must already be valid. */
export function encodeEan13(value) {
  const digits = value.replace(/\s+/g, "");
  if (!/^\d{12,13}$/.test(digits)) {
    throw new Error("EAN13 需要 12 或 13 位數字");
  }
  const body = digits.slice(0, 12);
  const check = eanChecksum(body);
  if (digits.length === 13 && Number(digits[12]) !== check) {
    throw new Error("EAN13 檢查碼不正確");
  }
  const ean = body + String(check);
  const pattern = EAN_LEFT[Number(ean[0])];
  let bits = "0".repeat(7) + "101";
  for (let i = 0; i < 6; i += 1) {
    const table = pattern[i] === "A" ? EAN_A : EAN_B;
    bits += table[Number(ean[i + 1])];
  }
  bits += "01010";
  for (let i = 7; i < 13; i += 1) bits += EAN_C[Number(ean[i])];
  bits += "101" + "0".repeat(7);
  return bits;
}

export function encodeBarcode(type, value) {
  if (type === "code128") return encodeCode128(value);
  if (type === "code39") return encodeCode39(value);
  if (type === "ean13") return encodeEan13(value);
  throw new Error(`不支援的條碼：${type}`);
}
