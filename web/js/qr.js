/**
 * Byte-mode QR Code, error correction M.
 * Module placement follows the same rules as the desktop app's qrcode library.
 */

const ALIGN = [
  [],
  [6, 18],
  [6, 22],
  [6, 26],
  [6, 30],
  [6, 34],
  [6, 22, 38],
  [6, 24, 42],
  [6, 26, 46],
  [6, 28, 50],
  [6, 30, 54],
  [6, 32, 58],
  [6, 34, 62],
  [6, 26, 46, 66],
  [6, 26, 48, 70],
  [6, 26, 50, 74],
  [6, 30, 54, 78],
  [6, 30, 56, 82],
  [6, 30, 58, 86],
  [6, 34, 62, 90],
  [6, 28, 50, 72, 94],
  [6, 26, 50, 74, 98],
  [6, 30, 54, 78, 102],
  [6, 28, 54, 80, 106],
  [6, 32, 58, 84, 110],
  [6, 30, 58, 86, 114],
  [6, 34, 62, 90, 118],
  [6, 26, 50, 74, 98, 122],
  [6, 30, 54, 78, 102, 126],
  [6, 26, 52, 78, 104, 130],
  [6, 30, 56, 82, 108, 134],
  [6, 34, 60, 86, 112, 138],
  [6, 30, 58, 86, 114, 142],
  [6, 34, 62, 90, 118, 146],
  [6, 30, 54, 78, 102, 126, 150],
  [6, 24, 50, 76, 102, 128, 154],
  [6, 28, 54, 80, 106, 132, 158],
  [6, 32, 58, 84, 110, 136, 162],
  [6, 26, 54, 82, 110, 138, 166],
  [6, 30, 58, 86, 114, 142, 170],
];

// Error correction M: repeating [block count, total codewords, data codewords].
const RS_M = {
  1: [1, 26, 16],
  2: [1, 44, 28],
  3: [1, 70, 44],
  4: [2, 50, 32],
  5: [2, 67, 43],
  6: [4, 43, 27],
  7: [4, 49, 31],
  8: [2, 60, 38, 2, 61, 39],
  9: [3, 58, 36, 2, 59, 37],
  10: [4, 69, 43, 1, 70, 44],
  11: [1, 80, 50, 4, 81, 51],
  12: [6, 58, 36, 2, 59, 37],
  13: [8, 59, 37, 1, 60, 38],
  14: [4, 64, 40, 5, 65, 41],
  15: [5, 65, 41, 5, 66, 42],
  16: [7, 73, 45, 3, 74, 46],
  17: [10, 74, 46, 1, 75, 47],
  18: [9, 69, 43, 4, 70, 44],
  19: [3, 70, 44, 11, 71, 45],
  20: [3, 67, 41, 13, 68, 42],
  21: [17, 68, 42],
  22: [17, 74, 46],
  23: [4, 75, 47, 14, 76, 48],
  24: [6, 73, 45, 14, 74, 46],
  25: [8, 75, 47, 13, 76, 48],
  26: [19, 74, 46, 4, 75, 47],
  27: [22, 73, 45, 3, 74, 46],
  28: [3, 73, 45, 23, 74, 46],
  29: [21, 73, 45, 7, 74, 46],
  30: [19, 75, 47, 10, 76, 48],
  31: [2, 74, 46, 29, 75, 47],
  32: [10, 74, 46, 23, 75, 47],
  33: [14, 74, 46, 21, 75, 47],
  34: [14, 74, 46, 23, 75, 47],
  35: [12, 75, 47, 26, 76, 48],
  36: [6, 75, 47, 34, 76, 48],
  37: [29, 74, 46, 14, 75, 47],
  38: [13, 74, 46, 32, 75, 47],
  39: [40, 75, 47, 7, 76, 48],
  40: [18, 75, 47, 31, 76, 48],
};

const G15 = (1 << 10) | (1 << 8) | (1 << 5) | (1 << 4) | (1 << 2) | (1 << 1) | 1;
const G18 = (1 << 12) | (1 << 11) | (1 << 10) | (1 << 9) | (1 << 8) | (1 << 5) | (1 << 2) | 1;
const G15_MASK = (1 << 14) | (1 << 12) | (1 << 10) | (1 << 4) | (1 << 1);

const EXP = new Array(256);
const LOG = new Array(256).fill(0);
for (let i = 0; i < 8; i += 1) EXP[i] = 1 << i;
for (let i = 8; i < 256; i += 1) {
  EXP[i] = EXP[i - 4] ^ EXP[i - 5] ^ EXP[i - 6] ^ EXP[i - 8];
}
for (let i = 0; i < 255; i += 1) LOG[EXP[i]] = i;

function glog(n) {
  if (n < 1) throw new Error("QR 計算錯誤");
  return LOG[n];
}

function gexp(n) {
  return EXP[((n % 255) + 255) % 255];
}

class Polynomial {
  constructor(num, shift) {
    let offset = 0;
    for (; offset < num.length; offset += 1) {
      if (num[offset] !== 0) break;
    }
    if (offset === num.length) offset = num.length - 1;
    this.num = num.slice(offset).concat(Array(shift).fill(0));
  }

  mul(other) {
    const num = Array(this.num.length + other.num.length - 1).fill(0);
    for (let i = 0; i < this.num.length; i += 1) {
      if (this.num[i] === 0) continue;
      for (let j = 0; j < other.num.length; j += 1) {
        if (other.num[j] === 0) continue;
        num[i + j] ^= gexp(glog(this.num[i]) + glog(other.num[j]));
      }
    }
    return new Polynomial(num, 0);
  }

  mod(other) {
    if (this.num.length === 1 && this.num[0] === 0) return this;
    const difference = this.num.length - other.num.length;
    if (difference < 0) return this;
    const ratio = glog(this.num[0]) - glog(other.num[0]);
    const num = [];
    for (let i = 0; i < other.num.length; i += 1) {
      const mixed = other.num[i] === 0 ? 0 : gexp(glog(other.num[i]) + ratio);
      num.push(this.num[i] ^ mixed);
    }
    if (difference) num.push(...this.num.slice(-difference));
    return new Polynomial(num, 0).mod(other);
  }
}

const generators = new Map();

function rsGenerator(ecCount) {
  const cached = generators.get(ecCount);
  if (cached) return cached;
  let poly = new Polynomial([1], 0);
  for (let i = 0; i < ecCount; i += 1) {
    poly = poly.mul(new Polynomial([1, gexp(i)], 0));
  }
  generators.set(ecCount, poly);
  return poly;
}

function rsBlocks(version) {
  const raw = RS_M[version];
  const blocks = [];
  for (let i = 0; i < raw.length; i += 3) {
    const [count, total, data] = raw.slice(i, i + 3);
    for (let n = 0; n < count; n += 1) blocks.push({ total, data });
  }
  return blocks;
}

function dataBitsAvailable(version) {
  return rsBlocks(version).reduce((sum, block) => sum + block.data * 8, 0);
}

class BitBuffer {
  constructor() {
    this.buffer = [];
    this.length = 0;
  }

  put(num, length) {
    for (let i = 0; i < length; i += 1) {
      this.putBit(((num >> (length - i - 1)) & 1) === 1);
    }
  }

  putBit(bit) {
    const index = this.length >> 3;
    if (this.buffer.length <= index) this.buffer.push(0);
    if (bit) this.buffer[index] |= 0x80 >> (this.length % 8);
    this.length += 1;
  }
}

function chooseVersion(byteLength) {
  for (let version = 1; version <= 40; version += 1) {
    const countBits = version < 10 ? 8 : 16;
    const needed = 4 + countBits + byteLength * 8;
    if (needed <= dataBitsAvailable(version)) return version;
  }
  throw new Error("QR 內容太長");
}

function createData(version, bytes) {
  const blocks = rsBlocks(version);
  const bitLimit = blocks.reduce((sum, block) => sum + block.data * 8, 0);
  const buffer = new BitBuffer();
  buffer.put(0b0100, 4);
  buffer.put(bytes.length, version < 10 ? 8 : 16);
  for (const byte of bytes) buffer.put(byte, 8);
  if (buffer.length > bitLimit) throw new Error("QR 內容太長");

  for (let i = 0; i < Math.min(bitLimit - buffer.length, 4); i += 1) buffer.putBit(false);
  const remain = buffer.length % 8;
  if (remain) {
    for (let i = 0; i < 8 - remain; i += 1) buffer.putBit(false);
  }
  const padBytes = (bitLimit - buffer.length) / 8;
  for (let i = 0; i < padBytes; i += 1) buffer.put(i % 2 === 0 ? 0xec : 0x11, 8);

  let offset = 0;
  let maxData = 0;
  let maxEc = 0;
  const dataBlocks = [];
  const ecBlocks = [];
  for (const block of blocks) {
    const ecCount = block.total - block.data;
    maxData = Math.max(maxData, block.data);
    maxEc = Math.max(maxEc, ecCount);
    const current = buffer.buffer.slice(offset, offset + block.data);
    offset += block.data;
    const gen = rsGenerator(ecCount);
    const mod = new Polynomial(current, gen.num.length - 1).mod(gen);
    const ec = [];
    const modOffset = mod.num.length - ecCount;
    for (let i = 0; i < ecCount; i += 1) {
      const index = i + modOffset;
      ec.push(index >= 0 ? mod.num[index] : 0);
    }
    dataBlocks.push(current);
    ecBlocks.push(ec);
  }

  const out = [];
  for (let i = 0; i < maxData; i += 1) {
    for (const block of dataBlocks) if (i < block.length) out.push(block[i]);
  }
  for (let i = 0; i < maxEc; i += 1) {
    for (const block of ecBlocks) if (i < block.length) out.push(block[i]);
  }
  return out;
}

function bitLength(value) {
  let n = value >>> 0;
  let bits = 0;
  while (n) {
    bits += 1;
    n >>>= 1;
  }
  return bits;
}

function bchTypeInfo(data) {
  let d = (data << 10) >>> 0;
  while (bitLength(d) - bitLength(G15) >= 0) {
    d = (d ^ (G15 << (bitLength(d) - bitLength(G15)))) >>> 0;
  }
  return ((data << 10) | d) ^ G15_MASK;
}

function bchTypeNumber(data) {
  let d = (data << 12) >>> 0;
  while (bitLength(d) - bitLength(G18) >= 0) {
    d = (d ^ (G18 << (bitLength(d) - bitLength(G18)))) >>> 0;
  }
  return ((data << 12) | d) >>> 0;
}

function maskOf(pattern) {
  switch (pattern) {
    case 0: return (row, col) => (row + col) % 2 === 0;
    case 1: return (row) => row % 2 === 0;
    case 2: return (_row, col) => col % 3 === 0;
    case 3: return (row, col) => (row + col) % 3 === 0;
    case 4: return (row, col) => (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0;
    case 5: return (row, col) => ((row * col) % 2) + ((row * col) % 3) === 0;
    case 6: return (row, col) => (((row * col) % 2) + ((row * col) % 3)) % 2 === 0;
    default: return (row, col) => (((row * col) % 3) + ((row + col) % 2)) % 2 === 0;
  }
}

function placeFinder(modules, row, col) {
  const count = modules.length;
  for (let r = -1; r <= 7; r += 1) {
    if (row + r < 0 || row + r >= count) continue;
    for (let c = -1; c <= 7; c += 1) {
      if (col + c < 0 || col + c >= count) continue;
      const edge = (r >= 0 && r <= 6 && (c === 0 || c === 6))
        || (c >= 0 && c <= 6 && (r === 0 || r === 6))
        || (r >= 2 && r <= 4 && c >= 2 && c <= 4);
      modules[row + r][col + c] = edge;
    }
  }
}

function blankModules(version) {
  const count = version * 4 + 17;
  const modules = Array.from({ length: count }, () => Array(count).fill(null));
  placeFinder(modules, 0, 0);
  placeFinder(modules, count - 7, 0);
  placeFinder(modules, 0, count - 7);

  const pos = ALIGN[version - 1];
  for (const row of pos) {
    for (const col of pos) {
      if (modules[row][col] !== null) continue;
      for (let r = -2; r <= 2; r += 1) {
        for (let c = -2; c <= 2; c += 1) {
          modules[row + r][col + c] = r === -2 || r === 2 || c === -2 || c === 2 || (r === 0 && c === 0);
        }
      }
    }
  }

  for (let row = 8; row < count - 8; row += 1) {
    if (modules[row][6] === null) modules[row][6] = row % 2 === 0;
  }
  for (let col = 8; col < count - 8; col += 1) {
    if (modules[6][col] === null) modules[6][col] = col % 2 === 0;
  }
  return modules;
}

function cloneModules(source) {
  return source.map((row) => row.slice());
}

function setupTypeInfo(modules, maskPattern, test) {
  const count = modules.length;
  const bits = bchTypeInfo(maskPattern);
  for (let i = 0; i < 15; i += 1) {
    const mod = !test && ((bits >> i) & 1) === 1;
    if (i < 6) modules[i][8] = mod;
    else if (i < 8) modules[i + 1][8] = mod;
    else modules[count - 15 + i][8] = mod;
  }
  for (let i = 0; i < 15; i += 1) {
    const mod = !test && ((bits >> i) & 1) === 1;
    if (i < 8) modules[8][count - i - 1] = mod;
    else if (i < 9) modules[8][15 - i - 1 + 1] = mod;
    else modules[8][15 - i - 1] = mod;
  }
  modules[count - 8][8] = !test;
}

function setupTypeNumber(modules, version, test) {
  const count = modules.length;
  const bits = bchTypeNumber(version);
  for (let i = 0; i < 18; i += 1) {
    const mod = !test && ((bits >> i) & 1) === 1;
    modules[Math.floor(i / 3)][(i % 3) + count - 11] = mod;
    modules[(i % 3) + count - 11][Math.floor(i / 3)] = mod;
  }
}

function mapData(modules, data, maskPattern) {
  const count = modules.length;
  const mask = maskOf(maskPattern);
  let inc = -1;
  let row = count - 1;
  let bitIndex = 7;
  let byteIndex = 0;

  for (let step = count - 1; step > 0; step -= 2) {
    const col = step <= 6 ? step - 1 : step;
    const cols = [col, col - 1];
    for (;;) {
      for (const c of cols) {
        if (modules[row][c] !== null) continue;
        let dark = false;
        if (byteIndex < data.length) dark = ((data[byteIndex] >> bitIndex) & 1) === 1;
        if (mask(row, c)) dark = !dark;
        modules[row][c] = dark;
        bitIndex -= 1;
        if (bitIndex === -1) {
          byteIndex += 1;
          bitIndex = 7;
        }
      }
      row += inc;
      if (row < 0 || row >= count) {
        row -= inc;
        inc = -inc;
        break;
      }
    }
  }
}

function penalty(modules) {
  const count = modules.length;
  let score = 0;

  const addRuns = (get) => {
    let previous = get(0);
    let length = 0;
    for (let i = 0; i < count; i += 1) {
      const color = get(i);
      if (color === previous) length += 1;
      else {
        if (length >= 5) score += length - 2;
        length = 1;
        previous = color;
      }
    }
    if (length >= 5) score += length - 2;
  };
  for (let row = 0; row < count; row += 1) addRuns((col) => modules[row][col]);
  for (let col = 0; col < count; col += 1) addRuns((row) => modules[row][col]);

  for (let row = 0; row < count - 1; row += 1) {
    for (let col = 0; col < count - 1; col += 1) {
      const value = modules[row][col];
      if (
        value === modules[row][col + 1]
        && value === modules[row + 1][col]
        && value === modules[row + 1][col + 1]
      ) score += 3;
    }
  }

  const likeFinder = (get, index) => (
    !get(index + 1)
    && get(index + 4)
    && !get(index + 5)
    && get(index + 6)
    && !get(index + 9)
    && (
      (get(index) && get(index + 2) && get(index + 3) && !get(index + 7) && !get(index + 8) && !get(index + 10))
      || (!get(index) && !get(index + 2) && !get(index + 3) && get(index + 7) && get(index + 8) && get(index + 10))
    )
  );
  for (let row = 0; row < count; row += 1) {
    const line = modules[row];
    for (let col = 0; col <= count - 11; col += 1) {
      if (likeFinder((index) => line[index], col)) score += 40;
      if (line[col + 10]) col += 1;
    }
  }
  for (let col = 0; col < count; col += 1) {
    for (let row = 0; row <= count - 11; row += 1) {
      if (likeFinder((index) => modules[index][col], row)) score += 40;
      if (modules[row + 10][col]) row += 1;
    }
  }

  let dark = 0;
  for (const row of modules) for (const cell of row) if (cell) dark += 1;
  const rating = Math.trunc(Math.abs((dark / (count * count)) * 100 - 50) / 5);
  score += rating * 10;
  return score;
}

function build(version, data, maskPattern, test) {
  const modules = cloneModules(blankModules(version));
  setupTypeInfo(modules, maskPattern, test);
  if (version >= 7) setupTypeNumber(modules, version, test);
  mapData(modules, data, maskPattern);
  return modules;
}

/** @returns {boolean[][]} dark modules, without the quiet zone */
export function qrModules(text) {
  const bytes = new TextEncoder().encode(String(text));
  const version = chooseVersion(bytes.length);
  const data = createData(version, bytes);
  let bestMask = 0;
  let bestScore = Infinity;
  for (let mask = 0; mask < 8; mask += 1) {
    const score = penalty(build(version, data, mask, true));
    if (score < bestScore) {
      bestScore = score;
      bestMask = mask;
    }
  }
  return build(version, data, bestMask, false);
}
