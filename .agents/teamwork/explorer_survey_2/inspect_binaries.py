import pefile
import os

files = [
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\Vortx Stream.exe",
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\lu.exe",
]

for fp in files:
    print(f"\n==================== {os.path.basename(fp)} ====================")
    pe = pefile.PE(fp)
    print(f"Machine: {hex(pe.FILE_HEADER.Machine)}")
    print(f"Subsystem: {hex(pe.OPTIONAL_HEADER.Subsystem)}")
    
    # Version Info
    if hasattr(pe, 'FileInfo'):
        for fileinfo in pe.FileInfo:
            for finfo in fileinfo:
                if hasattr(finfo, 'StringTable'):
                    for st in finfo.StringTable:
                        for k, v in st.entries.items():
                            print(f"  {k.decode('utf-8', 'ignore')}: {v.decode('utf-8', 'ignore')}")
    
    # Imports
    print("\nImported DLLs:")
    if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
        for entry in pe.DIRECTORY_ENTRY_IMPORT[:10]:
            print(f"  {entry.dll.decode('utf-8', 'ignore')} ({len(entry.imports)} imports)")
        if len(pe.DIRECTORY_ENTRY_IMPORT) > 10:
            print(f"  ... and {len(pe.DIRECTORY_ENTRY_IMPORT) - 10} more DLLs")

