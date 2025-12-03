import os
import ast
import pandas as pd # もしpandasがなければ標準ライブラリで出力します

TARGET_DIR = './extracted'

def analyze_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.splitlines()
        loc = len([l for l in lines if l.strip() and not l.strip().startswith('#')]) # 空行とコメント除く

    try:
        tree = ast.parse(content)
    except:
        return loc, 0

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # 簡易カウント（厳密なモジュール数より、import文の個数を重視）
            imports.add(ast.dump(node))
    
    return loc, len(imports)

def main():
    if not os.path.exists(TARGET_DIR):
        print("Directory not found.")
        return

    data = []
    files = []

    for root, _, filenames in os.walk(TARGET_DIR):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))

    print(f"Analyzing complexity for {len(files)} files...")

    for path in files:
        loc, fan_out = analyze_file(path)
        
        # Heuristic Score: 行数 + (依存数 * 5)
        # 依存が多いほど複雑さは跳ね上がるため重み付け
        score = loc + (fan_out * 5)
        
        rel_name = os.path.splitext(os.path.relpath(path, TARGET_DIR))[0]
        data.append({
            "File": rel_name,
            "LOC": loc,
            "Imports": fan_out,
            "Score": score
        })

    # Sort by Score desc
    data.sort(key=lambda x: x["Score"], reverse=True)

    print(f"\n{'File':<60} | {'LOC':<6} | {'Imports':<8}")
    print("-" * 80)
    
    for row in data[:20]: # Top 20 dangerous files
        print(f"{row['File']:<60} | {row['LOC']:<6} | {row['Imports']:<8}")

if __name__ == "__main__":
    main()