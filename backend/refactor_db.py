import os
import glob

files = glob.glob('d:/samruddhi/xx/backend/**/*.py', recursive=True)

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content.replace('from psycopg.rows import dict_row', 'from psycopg.rows import dict_row')
    new_content = new_content.replace('row_factory=dict_row', 'row_factory=dict_row')

    if new_content != content:
        print(f"Refactored {file}")
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
