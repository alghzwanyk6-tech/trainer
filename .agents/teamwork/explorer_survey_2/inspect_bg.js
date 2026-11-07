const fs = require('fs');

const asarPath = "c:\\Users\\96655\\Downloads\\__VORTX STORE_ نسخة\\‏‏VORTX STORE_ نسخة\\Vortx (1)\\Vortx\\Vortx_buy\\xlu\\resources\\app.asar";
const fd = fs.openSync(asarPath, 'r');
const buf = Buffer.alloc(16);
fs.readSync(fd, buf, 0, 16, 0);
const headerSize = buf.readUInt32LE(12);
const headerBuf = Buffer.alloc(headerSize);
fs.readSync(fd, headerBuf, 0, headerSize, 16);
const header = JSON.parse(headerBuf.toString('utf8'));

function findNode(obj, pathParts) {
  let curr = obj;
  for (const part of pathParts) {
    if (!curr.files || !curr.files[part]) return null;
    curr = curr.files[part];
  }
  return curr;
}

const headerTotalSize = 16 + headerSize;

function readFileFromAsar(filePath) {
  const node = findNode(header, filePath.split('/'));
  if (!node) return null;
  const offset = parseInt(node.offset, 10);
  const size = node.size;
  const fileBuf = Buffer.alloc(size);
  fs.readSync(fd, fileBuf, 0, size, headerTotalSize + offset);
  return fileBuf;
}

const bgBuf = readFileFromAsar('app/background.js');
console.log('background.js size:', bgBuf.length);

// Let's write the first 1000 characters
const str = bgBuf.toString('utf8');
console.log('--- start of background.js ---');
console.log(str.slice(0, 1000));

// Check if there are mentions of koffi, dll, models, tokens, urls, endpoints, ports, etc.
const keywords = ['koffi', 'dll', 'load', 'token', 'auth', 'http', 'api', 'lucifer', 'stream', 'vigem', 'onnx'];
for (const kw of keywords) {
  let count = 0;
  let idx = 0;
  while ((idx = str.toLowerCase().indexOf(kw, idx)) !== -1) {
    count++;
    idx += kw.length;
  }
  console.log(`Keyword "${kw}": found ${count} times`);
}

fs.closeSync(fd);
