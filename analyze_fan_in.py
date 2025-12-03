import os
import ast
import collections

TARGET_DIR = './extracted'

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
                # (splitterの仕様で 関数名=ファイル名 になっている場合が多い)
                for alias in node.names:
                     if alias.name in all_modules:
                         imports.add(alias.name)

    return imports

def main():
    if not os.path.exists(TARGET_DIR):
        print("Directory not found.")
        return

    files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.py')]
    module_names = {f[:-3] for f in files} # 拡張子なし
    
    # 逆参照マップ (誰が誰に呼ばれているか)
    # referenced_by[callee] = [caller1, caller2, ...]
    referenced_by = collections.defaultdict(list)
    
    print(f"Analyzing usage for {len(files)} files...")

    # 全ファイルを走査して、「誰が誰を呼んでいるか」を調べる
    for caller_file in files:
        caller_name = caller_file[:-3]
        path = os.path.join(TARGET_DIR, caller_file)
        
        dependencies = get_imports(path, module_names)
        
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