import os
import ast
import collections

TARGET_DIR = './extracted'
# 削除してはいけないエントリーポイントや重要なファイル
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
                # 相対インポートやパッケージ名を考慮
                parts = module_name.split('.')
                name = parts[0] 
                if name in all_modules:
                    imports.add(name)
                
                # from module import func の func がファイル名(モジュール)である可能性
                for alias in node.names:
                     if alias.name in all_modules:
                         imports.add(alias.name)
    return imports

def main():
    if not os.path.exists(TARGET_DIR):
        print(f"Directory {TARGET_DIR} not found.")
        return

    # 初期ファイルリスト取得
    files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.py')]
    all_modules = {f[:-3] for f in files}
    
    # ファイルごとの依存先をキャッシュ (ファイル読み込みは最初の一回だけ)
    # dependencies[caller] = set(callees)
    file_dependencies = {}
    print(f"Analyzing dependencies for {len(files)} files...")
    
    for f in files:
        mod_name = f[:-3]
        path = os.path.join(TARGET_DIR, f)
        deps = get_imports(path, all_modules)
        file_dependencies[mod_name] = deps

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
            if mod in KEEP_FILES:
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
            file_path = os.path.join(TARGET_DIR, f"{mod}.py")
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                    count += 1
                else:
                    print(f"File not found (already deleted?): {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        print(f"\nDeleted {count} files.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    main()
