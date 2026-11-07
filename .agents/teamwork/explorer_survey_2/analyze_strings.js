const fs = require('fs');

const data = JSON.parse(fs.readFileSync('c:\\Users\\96655\\ui\\aim_trainer_project\\.agents\\teamwork\\explorer_survey_2\\decoded_strings.json', 'utf8'));

const entries = Object.entries(data);

console.log('--- URLs and Endpoints ---');
entries.filter(([k, v]) => v.includes('http') || v.includes('ws://') || v.includes('wss://') || v.includes('.com') || v.includes('.org') || v.includes('.net')).forEach(([k, v]) => console.log(`  [0x${parseInt(k).toString(16)}]: ${v}`));

console.log('\n--- Tokens, Auth, License ---');
entries.filter(([k, v]) => /token|auth|key|license|user|login|password|session/i.test(v)).forEach(([k, v]) => console.log(`  [0x${parseInt(k).toString(16)}]: ${v}`));

console.log('\n--- IPC, Events, Window, App ---');
entries.filter(([k, v]) => /ipc|event|window|channel|stream|server|client|port|vortx|lucifer/i.test(v)).forEach(([k, v]) => console.log(`  [0x${parseInt(k).toString(16)}]: ${v}`));

console.log('\n--- Native, DLL, System, Executables ---');
entries.filter(([k, v]) => /dll|exe|koffi|spawn|exec|process|driver|vigem/i.test(v)).forEach(([k, v]) => console.log(`  [0x${parseInt(k).toString(16)}]: ${v}`));
