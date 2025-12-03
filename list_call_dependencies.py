import os
import ast
import sys
from collections import defaultdict

def get_definitions(file_path):
    """Parses a python file and returns a list of function/class names defined in it."""
    defs = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
                defs.append(node.name)
    except Exception:
        pass
    return defs

def get_calls(file_path):
    """Parses a python file and returns a set of function/class names called/used in it."""
    calls = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
    except Exception:
        pass
    return calls

def visualize_graph(directory):
    print(f"Building dependency graph for {directory}...\n")
    
    files = [f for f in os.listdir(directory) if f.endswith('.py')]
    module_map = {f[:-3]: f for f in files}
    
    # 1. Map symbols to defining modules
    symbol_to_module = {}
    for module_name, filename in module_map.items():
        file_path = os.path.join(directory, filename)
        defs = get_definitions(file_path)
        for d in defs:
            symbol_to_module[d] = module_name

    # 2. Find calls and print edges
    edges = []
    for module_name, filename in module_map.items():
        file_path = os.path.join(directory, filename)
        calls = get_calls(file_path)
        
        for call in calls:
            if call in symbol_to_module:
                target_module = symbol_to_module[call]
                if target_module != module_name:
                    edges.append((module_name, target_module, call))

    # Sort for readable output
    edges.sort()

    print(f"Found {len(edges)} dependencies:\n")
    print("Source Module -> Target Module [via Symbol]")
    print("-" * 60)
    
    for source, target, symbol in edges:
        print(f"{source} -> {target} [{symbol}]")

if __name__ == "__main__":
    target_dir = os.path.join(os.getcwd(), "extracted")
    if not os.path.exists(target_dir):
        if os.path.basename(os.getcwd()) == "extracted":
             target_dir = os.getcwd()
        else:
             print(f"Directory '{target_dir}' not found.")
             sys.exit(1)
             
    visualize_graph(target_dir)
