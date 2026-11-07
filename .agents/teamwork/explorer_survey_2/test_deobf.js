const fs = require('fs');
const vm = require('vm');

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

const headerTotalSize = (16 + headerSize + 3) & ~3;

function readFileFromAsar(filePath) {
  const node = findNode(header, filePath.split('/'));
  if (!node) return null;
  const offset = parseInt(node.offset, 10);
  const size = node.size;
  const fileBuf = Buffer.alloc(size);
  fs.readSync(fd, fileBuf, 0, size, headerTotalSize + offset);
  return fileBuf;
}

const bgStr = readFileFromAsar('app/background.js').toString('utf8');
const endIife = bgStr.indexOf('}(a1_0x1b40,0x1dcf0)');
const setupCode = bgStr.slice(0, endIife + '}(a1_0x1b40,0x1dcf0)'.length) + ');';

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(setupCode, sandbox);

const decodeFn = sandbox['a1_0x5425'];
console.log('Decode function loaded successfully:', typeof decodeFn);

const decodedMap = {};
for (let i = 0xa3; i < 0x500; i++) {
  try {
    const val = decodeFn(i);
    decodedMap[i] = val;
  } catch (e) {}
}

console.log('Total decoded strings:', Object.keys(decodedMap).length);

// Dump all strings to a JSON file
fs.writeFileSync('c:\\Users\\96655\\ui\\aim_trainer_project\\.agents\\teamwork\\explorer_survey_2\\decoded_strings.json', JSON.stringify(decodedMap, null, 2), 'utf8');
console.log('Wrote decoded_strings.json successfully!');

fs.closeSync(fd);
