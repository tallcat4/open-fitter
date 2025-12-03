import os
import shutil
import re

# 設定
EXTRACTED_DIR = './extracted'

# 先ほどの分類ロジックと同じもの
def get_category(filename):
    name = filename.lower()
    if filename == "main.py": return "ROOT" # main.pyは移動させない
    
    if any(x in name for x in ['save_', 'load_', 'import_', 'export_', 'store_', 'restore_', 'json']): return "IO_Data"
    if any(x in name for x in ['bone', 'armature', 'skeleton', 'joint', 'finger', 'hips']): return "Skeleton"
    if any(x in name for x in ['weight', 'vertex_group', 'mask', 'filter']): return "Weights"
    if any(x in name for x in ['shape', 'blendshape', 'morph']): return "Morphs"
    if any(x in name for x in ['calculate', 'calc_', 'math', 'matrix', 'cross2d', 'intersect', 'area', 'point_in', 'is_']): return "Math_Geometry"
    if any(x in name for x in ['mesh', 'face', 'edge', 'vertex', 'vertices', 'subdivide', 'triangulate']): return "Mesh_Ops"
    if any(x in name for x in ['process_', 'apply_', 'execute_', 'update_']): return "Core_Logic" # mainを除外したので単純化
    return "Utils_Others"

def main():
    files = [f for f in os.listdir(EXTRACTED_DIR) if f.endswith('.py')]
    
    # 1. 配置計画を作成 (filename -> category)
    file_map = {}
    for f in files:
        file_map[f[:-3]] = get_category(f) # 拡張子なしでマッピング

    # 2. ファイルごとの処理
    print(f"Reorganizing {len(files)} files...")
    
    for f in files:
        module_name = f[:-3]
        my_category = file_map[module_name]
        file_path = os.path.join(EXTRACTED_DIR, f)
        
        with open(file_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
            
        # --- Import文の書き換えロジック ---
        # from .target_mod import ... を探して書き換える
        def replace_import(match):
            target_mod = match.group(1)
            
            # 知らないモジュール（標準ライブラリ等）はスルー
            if target_mod not in file_map:
                return match.group(0)
            
            target_category = file_map[target_mod]
            
            # ケースA: 自分がROOT (main.py)
            if my_category == "ROOT":
                if target_category == "ROOT":
                    return f"from .{target_mod}"
                else:
                    return f"from .{target_category}.{target_mod}"
            
            # ケースB: 相手も同じカテゴリ (兄弟)
            elif my_category == target_category:
                return f"from .{target_mod}"
                
            # ケースC: 違うカテゴリ (従兄弟) -> 一旦親に戻る
            else:
                if target_category == "ROOT":
                    return f"from ..{target_mod}"
                else:
                    return f"from ..{target_category}.{target_mod}"

        # 正規表現で置換実行
        # pattern: from .xxx import ...
        new_content = re.sub(r'from \.([a-zA-Z0-9_]+)', replace_import, content)
        
        # ファイルを書き戻す（まだ移動しない）
        with open(file_path, 'w', encoding='utf-8') as handle:
            handle.write(new_content)

    # 3. フォルダ作成と移動
    categories = set(file_map.values())
    for cat in categories:
        if cat == "ROOT": continue
        
        dir_path = os.path.join(EXTRACTED_DIR, cat)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            # __init__.py 作成
            with open(os.path.join(dir_path, '__init__.py'), 'w') as f:
                f.write("")
    
    # ルート用の __init__.py も一応作っておく（パッケージとして認識させるため）
    with open(os.path.join(EXTRACTED_DIR, '__init__.py'), 'w') as f:
        f.write("")

    for f in files:
        category = file_map[f[:-3]]
        if category == "ROOT": continue
        
        src = os.path.join(EXTRACTED_DIR, f)
        dst = os.path.join(EXTRACTED_DIR, category, f)
        shutil.move(src, dst)
        
    print("Done! Folder structure created.")

if __name__ == "__main__":
    main()