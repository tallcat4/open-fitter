import os
import ast
import networkx as nx

TARGET_DIR = './extracted'


def resolve_import(name, module_names, short_name_map):
    """Resolve an import path into known module names."""
    matches = set()
    if not name:
        return matches

    normalized = name.replace('/', '.').strip('. ')
    if normalized in module_names:
        matches.add(normalized)

    suffix = normalized.split('.')[-1]
    if suffix in short_name_map:
        matches.update(short_name_map[suffix])

    return matches


def get_imports(file_path, module_names, short_name_map):
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
        print("extracted フォルダが見つかりません")
        return

    files = []
    for root, _, filenames in os.walk(TARGET_DIR):
        for filename in filenames:
            if filename.endswith('.py'):
                files.append(os.path.join(root, filename))

    module_map = {}
    short_name_map = {}
    for path in files:
        rel_path = os.path.relpath(path, TARGET_DIR)
        module_name = os.path.splitext(rel_path)[0].replace(os.sep, '.')
        module_map[module_name] = path
        short = os.path.splitext(os.path.basename(rel_path))[0]
        short_name_map.setdefault(short, set()).add(module_name)
    
    # グラフ構築
    G = nx.DiGraph()
    for mod in module_map:
        G.add_node(mod)
        
    module_names = set(module_map.keys())
    for mod, path in module_map.items():
        deps = get_imports(path, module_names, short_name_map)
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