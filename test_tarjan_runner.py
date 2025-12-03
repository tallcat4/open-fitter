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
                # We could also check for attributes, but for flat scripts, direct calls are most relevant.
                # Adding attributes might increase false positives if method names are common (e.g. 'append', 'get')
    except Exception:
        pass
    return calls

def build_implicit_dependency_graph(directory):
    """Builds a dependency graph based on function/class definitions and calls."""
    files = [f for f in os.listdir(directory) if f.endswith('.py')]
    module_map = {f[:-3]: f for f in files} # module_name -> filename
    
    # Map function/class names to the file they are defined in
    symbol_to_file = {}
    
    # First pass: Collect definitions
    for module_name, filename in module_map.items():
        file_path = os.path.join(directory, filename)
        defs = get_definitions(file_path)
        for d in defs:
            symbol_to_file[d] = module_name
            
    graph = defaultdict(set)
    # Initialize nodes
    for module_name in module_map:
        graph[module_name] = set()
        
    # Second pass: Collect calls and build edges
    total_calls = 0
    resolved_calls = 0
    for module_name, filename in module_map.items():
        file_path = os.path.join(directory, filename)
        calls = get_calls(file_path)
        total_calls += len(calls)
        
        for call in calls:
            if call in symbol_to_file:
                target_module = symbol_to_file[call]
                if target_module != module_name:
                    graph[module_name].add(target_module)
                    resolved_calls += 1
    
    print(f"  - Definitions found: {len(symbol_to_file)}")
    print(f"  - Function calls found: {total_calls}")
    print(f"  - Inter-module dependencies resolved: {resolved_calls}")
                    
    return graph, module_map

def tarjan_scc(graph):
    """Finds SCCs using Tarjan's algorithm."""
    index_counter = [0]
    stack = []
    lowlink = {}
    index = {}
    result = []
    
    def strongconnect(node):
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        
        successors = graph.get(node, [])
        for successor in successors:
            if successor not in index:
                strongconnect(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif successor in stack:
                lowlink[node] = min(lowlink[node], index[successor])

        if lowlink[node] == index[node]:
            connected_component = []
            while True:
                successor = stack.pop()
                connected_component.append(successor)
                if successor == node:
                    break
            result.append(connected_component)
    
    for node in graph:
        if node not in index:
            strongconnect(node)
            
    return result

def analyze_circular_dependencies(directory):
    print(f"Analyzing implicit dependencies (calls -> definitions) in {directory}...")
    graph, module_map = build_implicit_dependency_graph(directory)
    
    sccs = tarjan_scc(graph)
    
    # Filter for actual cycles (size > 1 or self-loop)
    cycles = []
    for scc in sccs:
        if len(scc) > 1:
            cycles.append(scc)
        elif len(scc) == 1:
            node = scc[0]
            if node in graph and node in graph[node]:
                cycles.append(scc)
    
    print(f"\nTotal files scanned: {len(module_map)}")
    print(f"Total SCCs found: {len(sccs)}")
    print(f"Circular Dependencies (SCC size > 1 or self-loop): {len(cycles)}")
    
    if not cycles:
        print("No circular dependencies found.")
        return

    # Sort cycles by size (descending)
    cycles.sort(key=len, reverse=True)
    
    print("\n--- Circular Dependency Report ---")
    for i, cycle in enumerate(cycles, 1):
        print(f"\nCycle {i} (Size: {len(cycle)}):")
        # Print first few elements if cycle is huge
        if len(cycle) > 20:
             print(", ".join(cycle[:20]) + " ... and more")
        else:
             print(", ".join(cycle))
        
    # Quantitative Evaluation
    max_size = max(len(c) for c in cycles) if cycles else 0
    avg_size = sum(len(c) for c in cycles) / len(cycles) if cycles else 0
    
    print("\n--- Quantitative Evaluation ---")
    print(f"Max Cycle Size: {max_size}")
    print(f"Average Cycle Size: {avg_size:.2f}")
    
    # Severity Score (Heuristic: sum of squares of cycle sizes)
    severity = sum(len(c)**2 for c in cycles)
    print(f"Severity Score (Sum of Squares): {severity}")

if __name__ == "__main__":
    # Modified to point to test_circular directory
    target_dir = os.path.join(os.getcwd(), "test_circular")
    if not os.path.exists(target_dir):
         print(f"Directory '{target_dir}' not found.")
         sys.exit(1)
             
    analyze_circular_dependencies(target_dir)
