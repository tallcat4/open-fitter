import os
import ast
import sys
from collections import defaultdict

# --- Graph Building Logic (Same as before) ---

def get_definitions(file_path):
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

def build_graph(directory):
    files = [f for f in os.listdir(directory) if f.endswith('.py')]
    module_map = {f[:-3]: f for f in files}
    
    symbol_to_module = {}
    for module_name, filename in module_map.items():
        file_path = os.path.join(directory, filename)
        defs = get_definitions(file_path)
        for d in defs:
            symbol_to_module[d] = module_name

    graph = defaultdict(set)
    for module_name, filename in module_map.items():
        file_path = os.path.join(directory, filename)
        calls = get_calls(file_path)
        for call in calls:
            if call in symbol_to_module:
                target_module = symbol_to_module[call]
                if target_module != module_name:
                    graph[module_name].add(target_module)
    return graph

# --- Optimization Logic ---

def transitive_reduction(graph):
    """
    Removes edge u -> v if there is another path from u to v.
    This simplifies the graph without changing reachability.
    """
    reduced_graph = defaultdict(set)
    for u, neighbors in graph.items():
        reduced_graph[u] = set(neighbors)

    def has_path(start, end, graph_to_search):
        # BFS to check if end is reachable from start
        queue = [start]
        visited = {start}
        while queue:
            curr = queue.pop(0)
            if curr == end:
                return True
            for neighbor in graph_to_search.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    # Iterate over all edges and check if they are redundant
    # We iterate over a copy of keys to avoid modification issues
    nodes = list(reduced_graph.keys())
    for u in nodes:
        neighbors = list(reduced_graph[u])
        for v in neighbors:
            # Temporarily remove edge u -> v
            reduced_graph[u].remove(v)
            # Check if v is still reachable from u
            if not has_path(u, v, reduced_graph):
                # If not reachable, put it back (it was essential)
                reduced_graph[u].add(v)
            # Else: it was redundant, leave it removed
            
    return reduced_graph

def group_nodes(nodes):
    """Groups nodes by their prefix."""
    groups = defaultdict(list)
    prefixes = [
        "apply_", "calculate_", "create_", "find_", "get_", 
        "process_", "restore_", "save_", "store_", "load_", 
        "check_", "normalize_", "merge_", "is_"
    ]
    
    for node in nodes:
        matched = False
        for prefix in prefixes:
            if node.startswith(prefix):
                groups[prefix.strip('_')].append(node)
                matched = True
                break
        if not matched:
            groups["others"].append(node)
    return groups

def generate_mermaid(graph, output_file):
    # 1. Reduce the graph
    reduced_graph = transitive_reduction(graph)
    
    # 2. Collect all active nodes (those involved in edges)
    active_nodes = set(reduced_graph.keys())
    for neighbors in reduced_graph.values():
        active_nodes.update(neighbors)
    
    # 3. Group nodes
    groups = group_nodes(active_nodes)
    
    # 4. Generate Mermaid Syntax
    lines = ["graph TD"]
    
    # Add Subgraphs
    for group_name, nodes in groups.items():
        if not nodes: continue
        # Skip "others" group for cleaner look, or include it if you want
        if group_name == "others":
            # Just list nodes without subgraph, or put in a general box
            pass 
        else:
            lines.append(f"    subgraph {group_name.upper()}")
            for node in nodes:
                lines.append(f"        {node}")
            lines.append("    end")
            
    # Add Edges
    edge_count = 0
    for u, neighbors in reduced_graph.items():
        for v in neighbors:
            lines.append(f"    {u} --> {v}")
            edge_count += 1
            
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
        
    print(f"Mermaid graph generated: {output_file}")
    print(f"Nodes: {len(active_nodes)}")
    print(f"Edges (Reduced): {edge_count}")

if __name__ == "__main__":
    target_dir = os.path.join(os.getcwd(), "extracted")
    if not os.path.exists(target_dir):
        if os.path.basename(os.getcwd()) == "extracted":
             target_dir = os.getcwd()
        else:
             print(f"Directory '{target_dir}' not found.")
             sys.exit(1)
             
    raw_graph = build_graph(target_dir)
    generate_mermaid(raw_graph, "dependency_graph.mmd")
