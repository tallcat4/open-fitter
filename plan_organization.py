import os
import re
from collections import defaultdict
import generate_stratification_report as analyzer

def classify_file(filename):
    name = filename.lower()
    
    # 1. Math / Geometry
    if any(x in name for x in ['calc', 'matrix', 'vec', 'transform', 'obb', 'triangle', 'normal', 'dist', 'barycentric', 'coords', 'intersect']):
        # apply_transform系はBlender操作の可能性もあるが、計算要素が強ければMathへ。
        # ただし apply_ は副作用を示唆するので blender_utils の優先度を上げる手もあるが、
        # ここでは calculate_optimal_similarity_transform などを math に入れたい。
        if 'apply_similarity_transform' in name: return 'math'
        if 'apply' in name and 'transform' in name: return 'blender_utils' # apply_all_transforms など
        return 'math'

    # 2. IO / Data
    if any(x in name for x in ['load', 'save', 'import', 'export', 'read', 'write', 'store', 'restore']):
        return 'io'

    # 3. Algorithms
    if any(x in name for x in ['find', 'search', 'cluster', 'sort', 'group', 'check', 'neighbor']):
        return 'algo'

    # 4. Blender Utils (Mesh, Object, Bone, Weights)
    if any(x in name for x in ['modifier', 'shapekey', 'blendshape', 'weight', 'vertex', 'bone', 'armature', 'mesh', 'object', 'apply', 'reset', 'clear', 'create', 'merge', 'split', 'join', 'subdivide', 'propagate', 'adjust', 'process']):
        return 'blender_utils'

    # 5. String / Misc Utils
    if any(x in name for x in ['strip', 'name', 'rename', 'label', 'util', 'common']):
        return 'utils'

    return 'misc'

def main():
    # 解析を実行してレベルを取得
    # generate_stratification_report の main ロジックの一部を再利用したいが、
    # 関数として切り出されていない部分があるため、簡易的に再実装またはimport利用
    
    target_dir = os.path.join(os.getcwd(), "extracted")
    if not os.path.exists(target_dir):
        print("Target directory not found.")
        return

    files = [f for f in os.listdir(target_dir) if f.endswith('.py')]
    module_map = {f[:-3]: f for f in files}
    
    # 依存グラフ構築 (analyzerの関数を利用)
    graph = defaultdict(set)
    symbol_to_module = {m: m for m in module_map} # 簡易マッピング
    
    # 簡易的に全ファイル走査してimport/callを調べる（analyzerのロジックだと詳細すぎるので、ここではファイル名ベースで分類プランを提示することに注力）
    # 正確なレベル分けは analyzer.main() の出力をパースするか、ロジックを借りる必要がある。
    # ここでは analyzer.get_calls 等を使ってレベル計算を再現する。
    
    print("Analyzing dependencies for classification...")
    
    # 1. 定義収集 (簡易)
    for module_name, filename in module_map.items():
        path = os.path.join(target_dir, filename)
        defs = analyzer.get_definitions_and_lines(path)
        for d in defs:
            symbol_to_module[d] = module_name

    # 2. グラフ構築
    for module_name, filename in module_map.items():
        path = os.path.join(target_dir, filename)
        calls = analyzer.get_calls(path)
        for call in calls:
            if call in symbol_to_module:
                target_mod = symbol_to_module[call]
                if target_mod != module_name:
                    graph[module_name].add(target_mod)

    # 3. レベル計算
    levels = analyzer.calculate_levels(graph, list(module_map.keys()))

    # 分類プラン作成
    plan = defaultdict(list)
    
    print("\n" + "="*60)
    print("PROPOSED FILE ORGANIZATION PLAN")
    print("="*60)

    for module, level in levels.items():
        if level > 1: # Level 2以上は移動しない（または core に入れる）
            category = "KEEP (Level 2+)"
        else:
            filename = module_map.get(module, module + ".py")
            category = classify_file(filename)
            
        plan[category].append((module, level))

    # 結果表示
    for category in sorted(plan.keys()):
        items = plan[category]
        print(f"\n[{category.upper()}] - {len(items)} files")
        print("-" * 60)
        # レベル順、名前順でソート
        for module, level in sorted(items, key=lambda x: (x[1], x[0])):
            print(f"  - {module:<40} (Level {level})")

if __name__ == "__main__":
    main()
