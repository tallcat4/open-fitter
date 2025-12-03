import os
import ast
import collections

TARGET_DIR = './extracted'
# 削除してはいけないエントリーポイントや重要なファイル
KEEP_FILES = {'retarget_script2_7', 'main', 'globals'}


def resolve_import(name, module_names, short_name_map):
    matches = set()
    if not name:
        return matches

    normalized = name.replace('/', '.').strip('. ')
    if not normalized:
        return matches

    if normalized in module_names:
        matches.add(normalized)

    short = normalized.split('.')[-1]
    if short in short_name_map:
        matches.update(short_name_map[short])

    return matches

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

def main():
    if not os.path.exists(TARGET_DIR):
        print(f"Directory {TARGET_DIR} not found.")
        return

    # 初期ファイルリスト取得（サブディレクトリ含む）
    files = []
    for root, _, filenames in os.walk(TARGET_DIR):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))

    module_map = {}
    short_name_map = collections.defaultdict(set)
    for path in files:
        rel_path = os.path.relpath(path, TARGET_DIR)
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        module_map[module_name] = path
        short = os.path.splitext(os.path.basename(rel_path))[0]
        short_name_map[short].add(module_name)

    all_modules = set(module_map.keys())
    
    # ファイルごとの依存先をキャッシュ (ファイル読み込みは最初の一回だけ)
    # dependencies[caller] = set(callees)
    file_dependencies = {}
    print(f"Analyzing dependencies for {len(files)} files...")
    
    for mod_name, path in module_map.items():
        deps = get_imports(path, all_modules, short_name_map)
        file_dependencies[mod_name] = deps

    def is_keep_module(mod_name):
        basename = mod_name.split('.')[-1]
        return mod_name in KEEP_FILES or basename in KEEP_FILES

    # シミュレーションループ
    # 実際に削除するのではなく、セットから除外していくことで連鎖的なOrphanを検出する
    current_modules = set(all_modules)
    total_orphans = []
    
    iteration = 1
    while True:
        referenced_by = collections.defaultdict(int)
        
        # 現在有効なモジュール間の参照のみをカウント
        for caller in current_modules:
            deps = file_dependencies.get(caller, set())
            for callee in deps:
                # calleeも現在有効なモジュールである場合のみカウント
                if callee in current_modules and callee != caller:
                    referenced_by[callee] += 1
        
        # Orphanの特定
        current_orphans = []
        for mod in current_modules:
            if is_keep_module(mod):
                continue
            
            if referenced_by[mod] == 0:
                current_orphans.append(mod)
        
        if not current_orphans:
            break
            
        print(f"Iteration {iteration}: Found {len(current_orphans)} orphans.")
        total_orphans.extend(current_orphans)
        
        # 次のイテレーションのためにモジュールリストから削除
        for mod in current_orphans:
            current_modules.remove(mod)
            
        iteration += 1

    print("\n" + "="*60)
    print("Orphan Modules (Recursive detection)")
    print("="*60)
    
    if not total_orphans:
        print("No orphan modules found.")
        return

    total_orphans_sorted = sorted(list(set(total_orphans)))
    for mod in total_orphans_sorted:
        print(f"{mod}")

    print("\n" + "="*60)
    print(f"Found {len(total_orphans_sorted)} orphan modules in total.")
    print(f"Excluded from deletion: {', '.join(KEEP_FILES)}")
    
    confirm = input("Do you want to DELETE these files? (y/N): ")
    if confirm.lower() == 'y':
        count = 0
        for mod in total_orphans_sorted:
            file_path = module_map.get(mod)
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                    count += 1
                else:
                    print(f"File not found (already deleted?): {file_path or mod}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        print(f"\nDeleted {count} files.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    main()
