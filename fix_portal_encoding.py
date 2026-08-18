import glob

files = glob.glob('blueprints/*.py') + glob.glob('utils/*.py') + ['app.py', 'database.py', 'wsgi.py', 'run_dev.py']

for path in files:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Replace unicode smart quotes & em-dashes
        text = text.replace('\u2018', "'").replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"').replace('\u2014', '--')
        
        # Ensure utf-8 coding header at line 1 if missing
        if not text.startswith('# -*- coding: utf-8 -*-'):
            text = '# -*- coding: utf-8 -*-\n' + text
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Cleaned {path}")
    except Exception as e:
        print(f"Error on {path}: {e}")
