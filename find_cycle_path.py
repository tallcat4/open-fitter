import os
import ast
import networkx as nx

TARGET_DIR = './extracted'

def get_imports(file_path, all_modules):
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
                if module_name in all_modules:
                    imports.add(module_name)
    return imports

def main():
    if not os.path.exists(TARGET_DIR):
        print("extracted フォルダが見つかりません")
        return

    files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.py')]
    module_map = {f[:-3]: os.path.join(TARGET_DIR, f) for f in files}
    
    # グラフ構築
    G = nx.DiGraph()
    for mod in module_map:
        G.add_node(mod)
        
    for mod, path in module_map.items():
        deps = get_imports(path, module_map.keys())
        for dep in deps:
            if mod != dep:
                G.add_edge(mod, dep)

    print(f"Analyzing {len(G.nodes)} modules for cycles...")
    
    try:
        cycles = list(nx.simple_cycles(G))
    except ImportError:
        print("Error: NetworkX library needed. (pip install networkx)")
        return

    if not cycles:
        print("No cycles found! (Are you sure?)")
        return

    print(f"\nFound {len(cycles)} circular dependencies:\n")
    
    # 特に怪しいモジュールを含むサイクルを優先表示
    suspects = {'process_single_config', 'update_base_avatar_weights', 'process_missing_bone_weights'}
    
    found_suspect = False
    for cycle in cycles:
        # サイクル内のモジュールに怪しいやつが含まれているか？
        if any(node in suspects for node in cycle):
            found_suspect = True
            print(f"!!! CRITICAL CYCLE DETECTED !!!")
            print(" -> ".join(cycle) + " -> " + cycle[0])
            print("-" * 30)
            
    if not found_suspect:
        print("Other cycles found (unrelated to the main warning?):")
        for cycle in cycles:
            print(" -> ".join(cycle) + " -> " + cycle[0])

if __name__ == "__main__":
    try:
        import networkx
        main()
    except ImportError:
        print("このスクリプトの実行には networkx が必要です。")
        print("インストール: pip install networkx")
        # networkxがない場合の簡易版ロジック（DFS）が必要ならおっしゃってください