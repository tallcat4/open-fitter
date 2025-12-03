import ast
import os

TARGET_FILE = 'retarget_script2_7.py'
OUTPUT_DIR = './extracted'

def main():
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

if __name__ == "__main__":
    main()