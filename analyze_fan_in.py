import os
import ast
import collections

TARGET_DIR = './extracted'

def get_imports(file_path, module_names, short_name_map):
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
                imports.update(resolve_import(alias.name, module_names, short_name_map))
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module.lstrip('.') if node.module else ''

            if module_name:
                imports.update(resolve_import(module_name, module_names, short_name_map))

            for alias in node.names:
                combined = f"{module_name}.{alias.name}" if module_name else alias.name
                imports.update(resolve_import(combined, module_names, short_name_map))

    return imports

def resolve_import(name, module_names, short_name_map):
    """Resolve import string to known module names (full dotted path)."""
    candidates = set()
    if not name:
        return candidates

    normalized = name.replace('/', '.').strip('. ')
    if normalized in module_names:
        candidates.add(normalized)

    short = normalized.split('.')[-1]
    if short in short_name_map:
        candidates.update(short_name_map[short])

    return candidates


def main():
    if not os.path.exists(TARGET_DIR):
        print("Directory not found.")
        return

    files = []
    for root, _, filenames in os.walk(TARGET_DIR):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))

    module_names = set()
    short_name_map = collections.defaultdict(set)
    for path in files:
        rel_path = os.path.relpath(path, TARGET_DIR)
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        module_names.add(module_name)
        short = os.path.splitext(os.path.basename(rel_path))[0]
        short_name_map[short].add(module_name)
    
    # 逆参照マップ (誰が誰に呼ばれているか)
    # referenced_by[callee] = [caller1, caller2, ...]
    referenced_by = collections.defaultdict(list)
    
    print(f"Analyzing usage for {len(files)} files...")

    # 全ファイルを走査して、「誰が誰を呼んでいるか」を調べる
    for path in files:
        rel_path = os.path.relpath(path, TARGET_DIR)
        caller_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        
        dependencies = get_imports(path, module_names, short_name_map)
        
        for callee in dependencies:
            if callee != caller_name: # 自分自身への再帰はカウントしない
                referenced_by[callee].append(caller_name)

    # 結果の集計
    single_usage = [] # 1箇所からしか呼ばれていない
    orphan = []       # どこからも呼ばれていない (MainやEntry point以外なら不要コードの可能性)
    
    for mod in module_names:
        callers = referenced_by[mod]
        count = len(callers)
        
        if count == 0:
            orphan.append(mod)
        elif count == 1:
            single_usage.append((mod, callers[0]))
            
    # 出力
    print("\n" + "="*60)
    print("1-to-1 Relationship Candidates (Should be merged?)")
    print("="*60)
    print(f"{'Child Module (Callee)':<40} | {'Parent Module (Caller)'}")
    print("-" * 60)
    
    for child, parent in sorted(single_usage, key=lambda x: x[1]): # 親ごとにソートして表示
        print(f"{child:<40} <- {parent}")
        
    print("\n" + "="*60)
    print("Orphan Modules (No internal callers found)")
    print("(These might be entry points like 'main' or unused code)")
    print("="*60)
    for mod in sorted(orphan):
        print(f"{mod}")

    # 統計
    print("\n--- Summary ---")
    print(f"Total Modules: {len(module_names)}")
    print(f"1-to-1 Relationships: {len(single_usage)} (Potential merges)")
    print(f"Orphans: {len(orphan)}")

if __name__ == "__main__":
    main()