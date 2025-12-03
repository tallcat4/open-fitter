import ast
import os
import re

TARGET_FILE = 'retarget_script2_7.py'
OUTPUT_DIR = './extracted'

def split():
    print("Starting split process...")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(TARGET_FILE, 'r', encoding='utf-8-sig') as f:
        source_code = f.read()

    tree = ast.parse(source_code)

    common_headers = []
    
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            segment = ast.get_source_segment(source_code, node)
            if segment:
                common_headers.append(segment)
        elif isinstance(node, ast.Assign):
            pass

    header_str = "\n".join(common_headers) + "\n\n"

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            name = node.name

            segment = ast.get_source_segment(source_code, node)
            
            if segment:
                filename = f"{name}.py"
                filepath = os.path.join(OUTPUT_DIR, filename)
                
                with open(filepath, 'w', encoding='utf-8') as out_f:
                    out_f.write(header_str)
                    out_f.write(segment)
                    out_f.write("\n")
                
                print(f"Extracted: {filename}")
    print("Split process completed.")

def link():
    print("Starting link process...")
    modules = {}
    if not os.path.exists(OUTPUT_DIR):
        print(f"Directory {OUTPUT_DIR} does not exist. Skipping link.")
        return

    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.py')]
    
    for f in files:
        module_name = f[:-3]
        modules[module_name] = f

    print(f"Found {len(modules)} modules. Linking dependencies...")

    for current_file in files:
        current_name = current_file[:-3]
        file_path = os.path.join(OUTPUT_DIR, current_file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        imports_to_add = []
        
        for mod_name in modules:
            if mod_name == current_name:
                continue
            
            if re.search(r'\b' + re.escape(mod_name) + r'\b', content):
                imports_to_add.append(mod_name)
        
        if imports_to_add:
            new_imports = []
            for mod in sorted(imports_to_add):
                new_imports.append(f"from .{mod} import {mod}")
            
            import_block = "\n".join(new_imports) + "\n\n"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(import_block + content)
            
            print(f"Updated {current_file}: Added {len(new_imports)} imports")
    print("Link process completed.")

def main():
    split()
    link()
    print("consider run [ruff check ./extracted --select F401,I --fix] to clean up unused imports.")

if __name__ == "__main__":
    main()
