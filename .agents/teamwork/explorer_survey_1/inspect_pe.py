import os
import struct

def get_pe_info(file_path):
    try:
        with open(file_path, 'rb') as f:
            dos_header = f.read(64)
            if len(dos_header) < 64 or dos_header[:2] != b'MZ':
                return {'valid': False, 'error': 'Not MZ'}
            e_lfanew = struct.unpack('<I', dos_header[60:64])[0]
            f.seek(e_lfanew)
            pe_sig = f.read(4)
            if pe_sig != b'PE\x00\x00':
                return {'valid': False, 'error': 'Not PE'}
            file_header = f.read(20)
            machine, num_sections, timedate, sym_ptr, num_sym, opt_hdr_size, characteristics = struct.unpack('<HHIIIHH', file_header)
            
            machine_name = 'Unknown'
            if machine == 0x8664:
                machine_name = 'x64 (AMD64)'
            elif machine == 0x014c:
                machine_name = 'x86 (i386)'
            elif machine == 0xaa64:
                machine_name = 'ARM64'
            
            # Read optional header magic
            magic = struct.unpack('<H', f.read(2))[0]
            is_pe32plus = (magic == 0x20b)
            
            # Read CLR data directory (directory 14, 0-indexed)
            # Offset to data directories in optional header:
            # PE32: standard fields (28) + windows fields (68) = 96
            # PE32+: standard fields (24) + windows fields (88) = 112
            dd_offset = e_lfanew + 24 + (112 if is_pe32plus else 96)
            clr_offset = dd_offset + 14 * 8
            f.seek(clr_offset)
            clr_data = f.read(8)
            is_clr = False
            if len(clr_data) == 8:
                clr_rva, clr_size = struct.unpack('<II', clr_data)
                is_clr = (clr_rva > 0 and clr_size > 0)
                
            return {
                'valid': True,
                'machine': machine_name,
                'is_pe32plus': is_pe32plus,
                'is_clr': is_clr,
                'size': os.path.getsize(file_path)
            }
    except Exception as e:
        return {'valid': False, 'error': str(e)}

root = r"C:\Users\96655\Downloads\__VORTX STORE_ نسخة"
results = []
for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        ext = os.path.splitext(fn)[1].lower()
        if ext in ('.exe', '.dll', '.node'):
            full_path = os.path.join(dirpath, fn)
            info = get_pe_info(full_path)
            rel_path = os.path.relpath(full_path, root)
            results.append((rel_path, ext, info))

print(f"Total binaries analyzed: {len(results)}")
import json
with open(r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_1\binary_pe_analysis.json", 'w', encoding='utf-8') as f:
    json.dump([{'path': r[0], 'ext': r[1], 'info': r[2]} for r in results], f, indent=2)

# Summaries
mach_counts = {}
clr_count = 0
for r in results:
    inf = r[2]
    if inf.get('valid'):
        m = inf.get('machine')
        mach_counts[m] = mach_counts.get(m, 0) + 1
        if inf.get('is_clr'):
            clr_count += 1
print("Machine architectures:", mach_counts)
print(".NET CLR assemblies:", clr_count)
