import re

pdb_path = r"c:\Users\96655\Downloads\Color_detection\Color Detection_Secure\Color Detection.pdb"

with open(pdb_path, 'rb') as f:
    data = f.read()

print(f"PDB size: {len(data):,} bytes")

# Search for source file paths (.cs files)
cs_files = sorted(set([s.decode('utf-8', errors='ignore') for s in re.findall(rb'[A-Za-z0-9_\-\\\:\.]+\.cs', data)]))
print(f"Total .cs source files found ({len(cs_files)}):")
for f in cs_files:
    print(" ", f)
