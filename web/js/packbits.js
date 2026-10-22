/** PackBits encoder. Same byte output as the desktop app's packbits library. */

export function packbitsEncode(input) {
  const data = input instanceof Uint8Array ? input : Uint8Array.from(input);
  if (data.length === 0) return new Uint8Array(0);
  if (data.length === 1) return Uint8Array.of(0x00, data[0]);

  const result = [];
  const buf = [];
  let pos = 0;
  let repeatCount = 0;
  const maxLength = 127;
  let state = "RAW";

  const finishRaw = () => {
    if (buf.length === 0) return;
    result.push(buf.length - 1);
    result.push(...buf);
    buf.length = 0;
  };

  const finishRle = () => {
    result.push((256 - (repeatCount - 1)) & 0xff);
    result.push(data[pos]);
  };

  while (pos < data.length - 1) {
    const currentByte = data[pos];
    if (data[pos] === data[pos + 1]) {
      if (state === "RAW") {
        finishRaw();
        state = "RLE";
        repeatCount = 1;
      } else if (state === "RLE") {
        if (repeatCount === maxLength) {
          finishRle();
          repeatCount = 0;
        }
        repeatCount += 1;
      }
    } else if (state === "RLE") {
      repeatCount += 1;
      finishRle();
      state = "RAW";
      repeatCount = 0;
    } else if (state === "RAW") {
      if (buf.length === maxLength) finishRaw();
      buf.push(currentByte);
    }
    pos += 1;
  }

  if (state === "RAW") {
    buf.push(data[pos]);
    finishRaw();
  } else {
    repeatCount += 1;
    finishRle();
  }

  return Uint8Array.from(result);
}
