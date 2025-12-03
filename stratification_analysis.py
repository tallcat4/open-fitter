import os
import ast
import collections

TARGET_DIR = './extracted'

def get_internal_dependencies(file_path, all_modules):
    """
    ファイルを解析し、抽出済みモジュール(all_modules)への依存のみを返す。
    標準ライブラリや外部ライブラリへの依存は無視する。
    """
    dependencies = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except Exception:
        return set()

    for node in ast.walk(tree):
        # import module_name
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split('.')[0]
                if name in all_modules:
                    dependencies.add(name)
        # from module_name import ...
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # from . import module のような相対インポートも考慮
                module_name = node.module.lstrip('.') 
                if module_name in all_modules:
                    dependencies.add(module_name)
                # from module import func の func がモジュール名である可能性（splitterの仕様による）
                for name in node.names:
                    if name.name in all_modules:
                        dependencies.add(name.name)
    
    return dependencies

def analyze_stratification():
    if not os.path.exists(TARGET_DIR):
        print(f"Directory {TARGET_DIR} not found.")
        return

    # 1. 全モジュールのリストアップ
    files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.py') and f != "__init__.py"]
    module_map = {f[:-3]: os.path.join(TARGET_DIR, f) for f in files}
    all_modules = set(module_map.keys())

    # 2. 依存関係の構築 (Dependency Graph)
    graph = {} # module -> set(dependencies)
    for mod, path in module_map.items():
        deps = get_internal_dependencies(path, all_modules)
        # 自分自身への依存は除外（再帰呼び出しなど）
        if mod in deps:
            deps.remove(mod)
        graph[mod] = deps

    # 3. レベル計算 (Iterative approach)
    levels = {} # module -> level (int)
    
    # ループ検知用安全装置
    max_iterations = len(all_modules) + 10
    iteration = 0
    
    while len(levels) < len(all_modules):
        progress = False
        iteration += 1
        
        remaining_modules = all_modules - set(levels.keys())
        
        for mod in remaining_modules:
            dependencies = graph[mod]
            
            # 依存先がすべてレベル確定済みかチェック
            if all(dep in levels for dep in dependencies):
                if not dependencies:
                    # 依存なし -> Level 0
                    levels[mod] = 0
                else:
                    # 依存あり -> 最大レベル + 1
                    levels[mod] = max(levels[dep] for dep in dependencies) + 1
                progress = True
        
        if not progress:
            print("\nWarning: Could not resolve levels for some modules (Cycle detected?).")
            print(f"Unresolved modules: {remaining_modules}")
            break
        
        if iteration > max_iterations:
             print("Error: Max iterations reached.")
             break

    # 4. 結果表示
    print(f"--- Stratification Analysis (Total: {len(levels)} modules) ---\n")
    
    # レベルごとにグループ化
    level_groups = collections.defaultdict(list)
    for mod, lvl in levels.items():
        level_groups[lvl].append(mod)
    
    sorted_levels = sorted(level_groups.keys())
    
    for lvl in sorted_levels:
        mods = level_groups[lvl]
        mods.sort()
        print(f"=== Level {lvl} ({len(mods)} files) ===")
        print(f"  Definition: Only depends on Level 0-{lvl-1}")
        
        # 数が多い場合は省略表示
        if len(mods) > 20:
            print(f"  modules: {', '.join(mods[:20])} ... and {len(mods)-20} more")
        else:
            print(f"  modules: {', '.join(mods)}")
        print("")

    # 統計情報の表示
    if sorted_levels:
        max_lvl = sorted_levels[-1]
        print(f"Max Depth: {max_lvl}")
        print("Suggestion:")
        print("  - Level 0 modules can be safely moved to 'utils' or 'common' libraries.")
        print("  - Level 1-2 modules are good candidates for specific logic components.")
        print(f"  - Level {max_lvl} modules are likely the main controllers or entry points.")

if __name__ == "__main__":
    analyze_stratification()