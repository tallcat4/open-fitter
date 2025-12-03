import os
import ast
import sys
from collections import defaultdict

# --- 既存の解析ロジックを利用 ---

def get_definitions_and_lines(file_path):
    """関数/クラス定義と、その行数（複雑度推定用）を取得"""
    defs = {} # name -> line_count
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
            tree = ast.parse(source, filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                # Python 3.8+ for end_lineno
                start = node.lineno
                end = getattr(node, 'end_lineno', start)
                defs[node.name] = end - start + 1
    except Exception:
        pass
    return defs

def get_calls(file_path):
    """呼び出し関係を取得"""
    calls = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # func(args)
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                # self.method(args) や obj.method(args) も拾うならここを拡張
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
    except Exception:
        pass
    return calls

def calculate_levels(graph, nodes):
    """
    再帰的にレベルを計算する (メモ化付き)
    Level 0 = 依存なし
    Level N = 1 + max(Level of children)
    """
    levels = {}
    
    def get_level(node, path=set()):
        if node in levels:
            return levels[node]
        
        children = graph.get(node, set())
        # 自分自身への再帰呼び出しはレベル計算において無視する（無限ループ防止）
        real_children = [c for c in children if c != node and c in nodes]
        
        if not real_children:
            levels[node] = 0
            return 0
        
        # 循環参照検知用（DAGと分かっているなら本来不要だが念のため）
        if node in path:
            return float('inf') 

        path.add(node)
        child_levels = [get_level(child, path) for child in real_children]
        path.remove(node)
        
        my_level = 1 + max(child_levels)
        levels[node] = my_level
        return my_level

    for node in nodes:
        get_level(node)
        
    return levels

def main():
    target_dir = os.path.join(os.getcwd(), "extracted")
    if not os.path.exists(target_dir):
         # extractionを行わず単一ファイルを解析したい場合、そのファイルを指定するロジックに変更も可能
         print(f"Directory '{target_dir}' not found.")
         return

    files = []
    for root, _, filenames in os.walk(target_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))

    module_map = {}
    for path in files:
        rel_path = os.path.relpath(path, target_dir)
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        module_map[module_name] = path
    
    # 1. 定義と行数を収集
    symbol_info = {} # symbol -> {'file': file, 'lines': n}
    symbol_to_module = {} # symbol -> module_name
    
    print("Parsing files...")
    for module_name, path in module_map.items():
        defs = get_definitions_and_lines(path)
        
        # ファイル自体が1つの関数/クラスを表している場合（splitterの仕様による）
        # ファイル内のトップレベル定義だけでなく、モジュール名そのものもシンボルとして扱う
        rel_display = os.path.relpath(path, target_dir)
        symbol_info[module_name] = {'file': rel_display, 'lines': sum(defs.values()) if defs else 0}
        symbol_to_module[module_name] = module_name
        
        for d, lines in defs.items():
            symbol_info[d] = {'file': rel_display, 'lines': lines}
            symbol_to_module[d] = module_name

    # 2. 依存グラフ構築
    graph = defaultdict(set)
    
    for module_name, path in module_map.items():
        calls = get_calls(path)
        
        for call in calls:
            # 内部定義されているシンボルへの呼び出しのみをエッジとする
            if call in symbol_to_module:
                target_mod = symbol_to_module[call]
                if target_mod != module_name: # 自分自身への呼び出しは除外
                    graph[module_name].add(target_mod)

    # 3. レベル計算
    # 全モジュールを対象にする
    all_modules = list(module_map.keys())
    levels = calculate_levels(graph, all_modules)

    # 4. レポート出力
    sorted_nodes = sorted(levels.items(), key=lambda x: (x[1], x[0]))
    
    # レベルごとにグルーピング
    level_groups = defaultdict(list)
    for node, level in sorted_nodes:
        if level == float('inf'):
            level_groups["Circular / Error"].append(node)
        else:
            level_groups[level].append(node)

    print("\n" + "="*60)
    print("REFACTORING STRATEGY REPORT (By Level)")
    print("="*60)
    
    total_levels = max(k for k in level_groups.keys() if isinstance(k, int))
    
    for lvl in range(total_levels + 1):
        nodes = level_groups[lvl]
        print(f"\n[ Level {lvl} ] - {len(nodes)} items")
        print(f"  (Functions that only depend on Level {lvl-1} or lower)")
        print("-" * 60)
        
        # 行数順などでソートして表示（軽いものから倒すため）
        nodes_with_info = []
        for node in nodes:
            info = symbol_info.get(node, {'lines': '?'})
            nodes_with_info.append((node, info['lines']))
        
        # 行数が少ない順に表示
        nodes_with_info.sort(key=lambda x: x[1] if isinstance(x[1], int) else 99999)
        
        for node, lines in nodes_with_info:
            # 依存先を表示（確認用）
            deps = graph.get(node, [])
            deps_str = ", ".join(list(deps)[:3]) + ("..." if len(deps)>3 else "")
            print(f"  - {node:<40} | Lines: {lines:<5} | Depends on: [{deps_str}]")

if __name__ == "__main__":
    main()