import os
import re

EXTRACTED_DIR = './extracted'

def main():
    modules = {}
    files = [f for f in os.listdir(EXTRACTED_DIR) if f.endswith('.py')]
    
    for f in files:
        module_name = f[:-3]
        modules[module_name] = f

    print(f"Found {len(modules)} modules. Linking dependencies...")

    for current_file in files:
        current_name = current_file[:-3]
        file_path = os.path.join(EXTRACTED_DIR, current_file)
        
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

if __name__ == "__main__":
    main()