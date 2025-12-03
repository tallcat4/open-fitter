import os
import ast
import collections

# 設定
EXTRACTED_DIR = './extracted'

def get_category(filename):
    """ファイル名からカテゴリを推測する（上から順に判定）"""
    name = filename.lower()
    
    # 1. データIO・保存復元系
    if any(x in name for x in ['save_', 'load_', 'import_', 'export_', 'store_', 'restore_', 'json']):
        return "IO_Data"
    
    # 2. 骨・アーマチュア系
    if any(x in name for x in ['bone', 'armature', 'skeleton', 'joint', 'finger', 'hips']):
        return "Skeleton"
        
    # 3. ウェイト・頂点グループ系
    if any(x in name for x in ['weight', 'vertex_group', 'mask', 'filter']):
        return "Weights"
        
    # 4. シェイプキー・ブレンドシェイプ系
    if any(x in name for x in ['shape', 'blendshape', 'morph']):
        return "Morphs"
        
    # 5. 数学・幾何計算・判定系
    if any(x in name for x in ['calculate', 'calc_', 'math', 'matrix', 'cross2d', 'intersect', 'area', 'point_in', 'is_']):
        return "Math_Geometry"
        
    # 6. メッシュ操作系
    if any(x in name for x in ['mesh', 'face', 'edge', 'vertex', 'vertices', 'subdivide', 'triangulate']):
        return "Mesh_Ops"
        
    # 7. 処理実行・司令塔系
    if any(x in name for x in ['process_', 'apply_', 'execute_', 'main', 'update_']):
        return "Core_Logic"
        
    # その他
    return "Utils_Others"

def get_imports(file_path):
    """依存関係取得（簡易版）"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
    except:
        return []

    imports = []
    all_modules = {f[:-3] for f in os.listdir(EXTRACTED_DIR) if f.endswith('.py')}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # 簡易的にモジュール名だけ取得
            names = []
            if isinstance(node, ast.Import):
                names = [n.name.split('.')[0] for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split('.')[0]]
                # 相対インポート .module
                if node.level > 0 and node.module in all_modules:
                     names = [node.module]

            for name in names:
                if name in all_modules:
                    imports.append(name)
    return imports

def main():
    files = [f for f in os.listdir(EXTRACTED_DIR) if f.endswith('.py')]
    
    categories = collections.defaultdict(list)
    dependencies = []
    
    print(f"Categorizing {len(files)} files...")
    
    for f in files:
        mod_name = f[:-3]
        cat = get_category(mod_name)
        categories[cat].append(mod_name)
        
        # 依存関係も取得（グラフの線を引くため）
        # ただし、線を全部引くとスパゲッティになるので、
        # 「他カテゴリへの依存」だけ抽出するなどのフィルタも可能だが、今回は一旦全部出す
        path = os.path.join(EXTRACTED_DIR, f)
        deps = get_imports(path)
        for d in deps:
            if d != mod_name:
                dependencies.append((mod_name, d))

    # --- Mermaid出力 ---
    print("\n" + "="*50)
    print("CLUSTERED GRAPH (Copy to Mermaid Live Editor)")
    print("="*50)
    
    print("graph TD")
    
    # カテゴリごとのスタイル定義
    colors = {
        "IO_Data": "#e1f5fe",       # 青系
        "Skeleton": "#fce4ec",      # 赤系
        "Weights": "#f3e5f5",       # 紫系
        "Morphs": "#fff3e0",        # オレンジ系
        "Math_Geometry": "#e8f5e9", # 緑系
        "Mesh_Ops": "#fffde7",      # 黄系
        "Core_Logic": "#ffebee",    # 濃い赤
        "Utils_Others": "#eceff1"   # グレー
    }

    # サブグラフ（枠）の作成
    for cat, mods in categories.items():
        print(f"    subgraph {cat}")
        print(f"    style {cat} fill:{colors.get(cat, '#fff')},stroke:#333,stroke-width:2px")
        for mod in mods:
            print(f"        {mod}")
        print("    end")

    # 依存関係の線を描画（数が多すぎる場合はここをコメントアウトして確認してください）
    # 多すぎると描画エンジンが死ぬので、
    # ここでは「Core_Logic」からの出力だけに絞るなどの工夫が有効ですが
    # 一旦、重要なファイルのみピックアップするロジックなどを入れても良いでしょう
    
    # 今回は「主要な依存のみ」に絞るフィルタ例（全描画は重すぎるため）
    print("\n    %% Connections (Limited for visibility)")
    count = 0
    for src, dst in dependencies:
        # Core_LogicまたはMainからの呼び出し、あるいはカテゴリを跨ぐものだけ描画してみる
        src_cat = get_category(src)
        dst_cat = get_category(dst)
        
        # カテゴリを跨ぐ依存関係のみ線を描画（内部の細かい線は無視）
        if src_cat != dst_cat:
            print(f"    {src} --> {dst}")
            count += 1
            
    print(f"\n    %% Total inter-category connections: {count}")

if __name__ == "__main__":
    main()