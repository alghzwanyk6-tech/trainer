import struct
import json
import os

asar_path = r"C:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\xlu\resources\app.asar"

with open(asar_path, 'rb') as f:
    header_size_data = f.read(16)
    # asar format:
    # 4 bytes: 4 (uint32)
    # 4 bytes: header_data_size (uint32)
    # 4 bytes: header_size (uint32)
    # 4 bytes: header_string_size (uint32)
    u1, header_data_size, header_size, header_string_size = struct.unpack('<IIII', header_size_data)
    print(f"Header: u1={u1}, data_size={header_data_size}, size={header_size}, str_size={header_string_size}")
    header_json_bytes = f.read(header_string_size)
    header_json = json.loads(header_json_bytes.decode('utf-8'))
    
    with open(r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_1\asar_header.json", 'w', encoding='utf-8') as out:
        json.dump(header_json, out, indent=2)

print("Saved asar_header.json successfully.")
