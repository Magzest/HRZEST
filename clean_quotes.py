import glob

files = glob.glob('blueprints/*.py') + glob.glob('utils/*.py') + ['app.py', 'database.py', 'wsgi.py', 'run_dev.py']
bad_chars = {
    '\u2018': "'",
    '\u2019': "'",
    '\u201c': '"',
    '\u201d': '"',
    '\u2014': '--',
}

for path in files:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        modified = False
        for bad, good in bad_chars.items():
            if bad in text:
                text = text.replace(bad, good)
                modified = True
        if modified:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Cleaned {path}")
    except Exception as e:
        print(f"Error on {path}: {e}")
