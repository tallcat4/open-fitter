import os
import ast
import collections
import re

TARGET_DIR = './extracted'
# マージしてはいけないエントリーポイントや重要なファイル
KEEP_FILES = {'retarget_script2_7', 'main', 'globals'}

def get_imports(file_path, all_modules):
    """ファイル内のimport文から、抽出済みモジュールへの参照を取得"""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except:
        return set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split('.')[0]
                if name in all_modules: imports.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.lstrip('.')
                parts = module_name.split('.')
                name = parts[0] 
                if name in all_modules:
                    imports.add(name)
                
                for alias in node.names:
                     if alias.name in all_modules:
                         imports.add(alias.name)
    return imports

def split_imports_and_body(code):
    """コードをインポート部分と本文に分離する"""
    # まずASTでの解析を試みる
    try:
        tree = ast.parse(code)
        import_lines = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    for i in range(node.lineno, node.end_lineno + 1):
                        import_lines.add(i)
                elif hasattr(node, 'lineno'):
                     import_lines.add(node.lineno)
        
        lines = code.splitlines()
        extracted_imports = []
        body_lines = []
        
        for i, line in enumerate(lines, 1):
            if i in import_lines:
                extracted_imports.append(line)
            else:
                body_lines.append(line)
        return extracted_imports, "\n".join(body_lines)

    except SyntaxError:
        print("Warning: SyntaxError during parsing. Falling back to robust line splitting.")
        
    # Fallback: 括弧のバランスを見てマルチラインインポートを判定
    lines = code.splitlines()
    imports = []
    body_lines = []
    
    in_import = False
    paren_depth = 0
    
    for line in lines:
        stripped = line.strip()
        
        # インポート開始判定
        if not in_import:
            if re.match(r'^(import|from)\s', stripped):
                in_import = True
        
        if in_import:
            imports.append(line)
            # 括弧のカウント
            paren_depth += line.count('(') - line.count(')')
            
            # インポート終了判定
            if paren_depth <= 0 and not stripped.endswith('\\'):
                in_import = False
                paren_depth = 0
        else:
            body_lines.append(line)
            
    return imports, "\n".join(body_lines)

def merge_files(parent_name, child_name):
    """子ファイルを親ファイルに統合する"""
    parent_path = os.path.join(TARGET_DIR, f"{parent_name}.py")
    child_path = os.path.join(TARGET_DIR, f"{child_name}.py")
    
    print(f"Merging {child_name} -> {parent_name} ...")
    
    with open(parent_path, 'r', encoding='utf-8') as f:
        parent_code = f.read()
    with open(child_path, 'r', encoding='utf-8') as f:
        child_code = f.read()

    # 1. 子コードのクリーニング
    path_hack = "import sys\nimport os\nsys.path.append(os.path.dirname(os.path.abspath(__file__)))\n"
    if child_code.startswith(path_hack):
        child_code = child_code[len(path_hack):]
    
    child_code = re.sub(r'if __name__ == "__main__":\s+main\(\)', '', child_code)
    
    # 2. インポート文の整理
    child_imports, child_body_code = split_imports_and_body(child_code)
    parent_imports, parent_body_code = split_imports_and_body(parent_code)

    # インポートのマージ
    # 子モジュールへのインポートはコメントアウトする（構文破壊回避のため削除はしない）
    
    final_imports = []
    for line in (parent_imports + child_imports):
        # 子モジュール名を含む行はコメントアウト
        if re.search(r'\b' + re.escape(child_name) + r'\b', line):
             final_imports.append(f"# {line}  # Merged")
        else:
             final_imports.append(line)
    
    # 重複排除（コメント行以外）
    unique_imports = []
    seen = set()
    for line in final_imports:
        if line.strip().startswith('#'):
            unique_imports.append(line)
        elif line not in seen:
            unique_imports.append(line)
            seen.add(line)

    # 本文の結合
    separator = f"\n\n# --- Merged from {child_name} ---\n"
    
    if 'if __name__ == "__main__":' in parent_body_code:
        parts = parent_body_code.split('if __name__ == "__main__":')
        new_body = parts[0] + separator + child_body_code + '\n\nif __name__ == "__main__":' + parts[1]
    else:
        new_body = parent_body_code + separator + child_body_code

    new_code = "\n".join(unique_imports) + "\n\n" + new_body

    with open(parent_path, 'w', encoding='utf-8') as f:
        f.write(new_code)
    
    # 子ファイルを削除
    os.remove(child_path)
    print(f"Merged and deleted {child_name}.py")

def analyze_and_merge_step():
    """1ステップ分の分析とマージを行う。マージが発生したらTrueを返す"""
    files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.py')]
    all_modules = {f[:-3] for f in files}
    
    # 依存関係の構築
    # referenced_by[callee] = [caller1, caller2, ...]
    referenced_by = collections.defaultdict(list)
    
    # 依存関係グラフ (トポロジカルソート用)
    # graph[caller] = [callee1, callee2, ...]
    dependency_graph = collections.defaultdict(list)
    
    for caller_file in files:
        caller_name = caller_file[:-3]
        path = os.path.join(TARGET_DIR, caller_file)
        deps = get_imports(path, all_modules)
        
        for callee in deps:
            if callee != caller_name:
                referenced_by[callee].append(caller_name)
                dependency_graph[caller_name].append(callee)

    # 1対1関係の候補を探す
    candidates = []
    for child in all_modules:
        if child in KEEP_FILES:
            continue
            
        callers = referenced_by[child]
        if len(callers) == 1:
            parent = callers[0]
            # 親が自分自身でないことを確認（再帰呼び出しなど）
            if parent != child:
                candidates.append((child, parent))
    
    if not candidates:
        return False

    # マージ順序の決定
    # 下位（依存されない、または依存階層が深い）ものから処理したい。
    # candidates の中で、child が他の candidate の parent になっていないものを優先する。
    
    # childとして登場する名前のセット
    children_set = {c[0] for c in candidates}
    
    # 「安全な」マージ候補：childが他の誰かのparentになっていない
    safe_merges = []
    for child, parent in candidates:
        # もしこのchildが、別のペアのparentになっているなら、今はマージしない（そのペアを先にマージすべき）
        is_parent_of_another = False
        for other_child, other_parent in candidates:
            if other_parent == child:
                is_parent_of_another = True
                break
        
        if not is_parent_of_another:
            safe_merges.append((child, parent))
    
    if not safe_merges:
        # 循環参照などで詰まっている場合、とりあえず先頭を処理
        print("Warning: Cyclic or complex dependency detected in merge candidates. Forcing one merge.")
        safe_merges.append(candidates[0])

    # 実行（1ステップにつき安全なものをすべてマージしてもよいが、
    # ファイル書き換えが競合しないように、親が重複しない範囲で行う）
    
    processed_parents = set()
    merged_count = 0
    
    for child, parent in safe_merges:
        if parent in processed_parents:
            continue # 同じ親に対して複数の子を一度にマージするのは避ける（ファイル書き込み競合回避）
        
        # マージ実行
        merge_files(parent, child)
        processed_parents.add(parent)
        merged_count += 1
        
    return merged_count > 0

def main():
    if not os.path.exists(TARGET_DIR):
        print(f"Directory {TARGET_DIR} not found.")
        return

    step = 1
    while True:
        print(f"\n--- Merge Step {step} ---")
        changed = analyze_and_merge_step()
        if not changed:
            print("No more files to merge.")
            break
        step += 1
    
    print("\nMerge process completed.")
    print("Please run 'ruff check ./extracted --select F401,I --fix' to clean up imports.")

if __name__ == "__main__":
    main()
