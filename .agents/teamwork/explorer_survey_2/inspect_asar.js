const fs = require('fs');

const asarPath = "c:\\Users\\96655\\Downloads\\__VORTX STORE_ نسخة\\‏‏VORTX STORE_ نسخة\\Vortx (1)\\Vortx\\Vortx_buy\\xlu\\resources\\app.asar";

const fd = fs.openSync(asarPath, 'r');
const buf = Buffer.alloc(16);
fs.readSync(fd, buf, 0, 16, 0);

const headerSize = buf.readUInt32LE(12);
const headerBuf = Buffer.alloc(headerSize);
fs.readSync(fd, headerBuf, 0, headerSize, 16);
const header = JSON.parse(headerBuf.toString('utf8'));

function listFiles(obj, prefix = '') {
  let files = [];
  if (obj.files) {
    for (const [k, v] of Object.entries(obj.files)) {
      const full = prefix ? prefix + '/' + k : k;
      if (v.files) {
        files = files.concat(listFiles(v, full));
      } else {
        files.push({ path: full, size: v.size, offset: v.offset });
      }
    }
  }
  return files;
}

const allFiles = listFiles(header);
const nonNodeModules = allFiles.filter(f => !f.path.startsWith('node_modules/'));
console.log('Non-node_modules files (' + nonNodeModules.length + '):');
nonNodeModules.forEach(f => console.log(f.path, f.size));

fs.closeSync(fd);
