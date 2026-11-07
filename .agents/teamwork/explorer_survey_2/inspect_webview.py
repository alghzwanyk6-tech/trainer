import sqlite3
import shutil
import tempfile
import os

db_path = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\Vortx.exe.WebView2\EBWebView\Default\History"

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    tmp_path = tmp.name

shutil.copy2(db_path, tmp_path)

conn = sqlite3.connect(tmp_path)
cur = conn.cursor()

print("--- TABLES ---")
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cur.fetchall()]
print(tables)

if 'urls' in tables:
    print("\n--- URLS TABLE ---")
    cur.execute("SELECT id, url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 50;")
    for row in cur.fetchall():
        print(f"[{row[0]}] {row[1]} | Title: {row[2]} (Visits: {row[3]})")

conn.close()
os.remove(tmp_path)
