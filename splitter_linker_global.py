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
    
    global_assignments = []
    
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            segment = ast.get_source_segment(source_code, node)
            if segment:
                common_headers.append(segment)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            segment = ast.get_source_segment(source_code, node)
            if segment:
                global_assignments.append(segment)

    path_hack = "import sys\nimport os\nsys.path.append(os.path.dirname(os.path.abspath(__file__)))\n"
    header_str = path_hack + "\n".join(common_headers) + "\n\n"

    if global_assignments:
        globals_filename = "globals.py"
        filepath = os.path.join(OUTPUT_DIR, globals_filename)
        with open(filepath, 'w', encoding='utf-8') as out_f:
            out_f.write(header_str)
            out_f.write("\n".join(global_assignments))
            out_f.write("\n")
        print(f"Extracted: {globals_filename}")

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
                    if name == 'main':
                        out_f.write('\nif __name__ == "__main__":\n    main()\n')
                
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

    # Identify global variables from globals.py
    global_vars = set()
    globals_path = os.path.join(OUTPUT_DIR, 'globals.py')
    if os.path.exists(globals_path):
        with open(globals_path, 'r', encoding='utf-8') as f:
            try:
                g_tree = ast.parse(f.read())
                for node in g_tree.body:
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                global_vars.add(target.id)
                    elif isinstance(node, ast.AnnAssign):
                        if isinstance(node.target, ast.Name):
                            global_vars.add(node.target.id)
            except Exception as e:
                print(f"Error parsing globals.py: {e}")

    print(f"Found {len(modules)} modules. Linking dependencies...")

    for current_file in files:
        current_name = current_file[:-3]
        if current_name == 'globals':
            continue

        file_path = os.path.join(OUTPUT_DIR, current_file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        path_hack = "import sys\nimport os\nsys.path.append(os.path.dirname(os.path.abspath(__file__)))\n"
        content_body = content
        if content.startswith(path_hack):
            content_body = content[len(path_hack):]
        
        imports_to_add = []
        
        # Link modules
        for mod_name in modules:
            if mod_name == current_name or mod_name == 'globals':
                continue
            
            if re.search(r'\b' + re.escape(mod_name) + r'\b', content):
                imports_to_add.append(f"from {mod_name} import {mod_name}")

        # Link globals
        for g_var in global_vars:
            if re.search(r'\b' + re.escape(g_var) + r'\b', content):
                imports_to_add.append(f"from globals import {g_var}")
        
        if imports_to_add:
            # Remove duplicates and sort
            imports_to_add = sorted(list(set(imports_to_add)))
            import_block = "\n".join(imports_to_add) + "\n\n"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(path_hack + import_block + content_body)
            
            print(f"Updated {current_file}: Added {len(imports_to_add)} imports")
    print("Link process completed.")

def main():
    split()
    link()

    main_py_path = os.path.join(OUTPUT_DIR, 'main.py')
    if os.path.exists(main_py_path):
        new_name = os.path.join(OUTPUT_DIR, 'retarget_script2_7.py')
        if os.path.exists(new_name):
            os.remove(new_name)
        os.rename(main_py_path, new_name)
        print(f"Renamed main.py to retarget_script2_7.py")

    print("consider run [ruff check ./extracted --select F401,I --fix] to clean up unused imports.")

if __name__ == "__main__":
    main()
