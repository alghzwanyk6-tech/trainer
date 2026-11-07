const fs = require('fs');
const path = require('path');

const asarPath = "c:\\Users\\96655\\Downloads\\__VORTX STORE_ نسخة\\‏‏VORTX STORE_ نسخة\\Vortx (1)\\Vortx\\Vortx_buy\\xlu\\resources\\app.asar";
const fd = fs.openSync(asarPath, 'r');
const buf = Buffer.alloc(16);
fs.readSync(fd, buf, 0, 16, 0);
const headerSize = buf.readUInt32LE(12);
const headerBuf = Buffer.alloc(headerSize);
fs.readSync(fd, headerBuf, 0, headerSize, 16);
const header = JSON.parse(headerBuf.toString('utf8'));

// The base offset of file data is 16 + headerSize (aligned)
// In Electron asar format:
// uint32 size_header_magic (4)
// uint32 size_header_full (4 + 4 + jsonLen)
// uint32 size_header_json_and_prefix (4 + jsonLen)
// uint32 size_json (jsonLen)
// So payload starts at 16 + headerSize? Wait, let's verify offset calculation.

// Let's find package.json in the header
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
  if (!node) {
    console.error('File not found in asar:', filePath);
    return null;
  }
  const offset = parseInt(node.offset, 10);
  const size = node.size;
  const fileBuf = Buffer.alloc(size);
  fs.readSync(fd, fileBuf, 0, size, headerTotalSize + offset);
  return fileBuf;
}

const pkgBuf = readFileFromAsar('package.json');
if (pkgBuf) {
  console.log('--- package.json ---');
  console.log(pkgBuf.toString('utf8'));
}

const mainBuf = readFileFromAsar('app/main.js');
if (mainBuf) {
  console.log('--- app/main.js ---');
  console.log(mainBuf.toString('utf8'));
}

fs.closeSync(fd);
