lines = open('blueprints/employee_portal.py', encoding='utf-8').readlines()
in_triple = False
for i, line in enumerate(lines):
    count = line.count('"""')
    if count % 2 != 0:
        in_triple = not in_triple
        print(f"Line {i+1} toggled triple quote -> in_state={in_triple}: {line.strip()[:60]}")
