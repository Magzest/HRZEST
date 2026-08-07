import re
import glob
import os

routes = {}

def scan_file(filepath):
    rel = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    pattern = re.compile(r'@[\w_]+\.route\(\s*["\']([^"\']+)["\'](?:,\s*methods=\[([^\]]+)\])?')
    for m in pattern.finditer(content):
        url = m.group(1)
        methods_raw = m.group(2)
        if methods_raw:
            methods = [b.strip(" \"'\t\n") for b in methods_raw.split(",")]
        else:
            methods = ["GET"]
        if rel not in routes:
            routes[rel] = []
        routes[rel].append((url, methods))

for f in sorted(glob.glob("/home/kali/.gemini/antigravity/scratch/HRZEST/blueprints/*.py")):
    scan_file(f)

scan_file("/home/kali/.gemini/antigravity/scratch/HRZEST/app.py")

with open("/home/kali/.gemini/antigravity/scratch/HRZEST/routes_output.txt", "w") as out:
    for file, rlist in routes.items():
        out.write(f"=== {file} ({len(rlist)} endpoints) ===\n")
        for u, m in rlist:
            m_str = ", ".join(m)
            out.write(f"  {u:<55} [{m_str}]\n")
        out.write("\n")

print("Done")
