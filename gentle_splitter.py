import ast
import os

# 設定
TARGET_FILE = 'retarget_script2_7.py'      # 元のファイル名（適宜変更してください）
OUTPUT_DIR = './gentle_split'    # 出力先

# カテゴリ分けロジック（前回のものを再利用）
def get_category(node_name):
    name = node_name.lower()
    if any(x in name for x in ['save_', 'load_', 'import_', 'export_', 'store_', 'restore_', 'json']): return "io_data"
    if any(x in name for x in ['bone', 'armature', 'skeleton', 'joint', 'finger', 'hips']): return "skeleton"
    if any(x in name for x in ['weight', 'vertex_group', 'mask', 'filter']): return "weights"
    if any(x in name for x in ['shape', 'blendshape', 'morph']): return "morphs"
    if any(x in name for x in ['calculate', 'calc_', 'math', 'matrix', 'cross2d', 'intersect', 'area', 'point_in', 'is_']): return "math_geometry"
    if any(x in name for x in ['mesh', 'face', 'edge', 'vertex', 'vertices', 'subdivide', 'triangulate']): return "mesh_ops"
    # process系は依存が多いので、mainに近いところに置くか迷いますが、一旦ロジックへ
    if any(x in name for x in ['process_', 'apply_', 'execute_', 'update_']): return "core_logic"
    return "utils"

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 1. ファイル読み込み
    try:
        with open(TARGET_FILE, 'r', encoding='utf-8-sig') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: {TARGET_FILE} が見つかりません。ファイル名を変更してください。")
        return

    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    # 2. 共有コンテキスト（Import文と定数）の抽出
    shared_lines = []
    # 完全に安全策として、標準ライブラリ系とBlender系は決め打ちで入れておく
    shared_lines.append("import sys\nimport os\nimport math\nimport json\n")
    shared_lines.append("try:\n    import bpy\n    import mathutils\nexcept ImportError:\n    pass\n\n")

    # ASTからImport文と、大文字の定数代入(CONST = 1)を抽出
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(source, node)
            if seg: shared_lines.append(seg + "\n")
        
        # 定数らしきもの（全て大文字の変数への代入）
        elif isinstance(node, ast.Assign):
            is_const = False
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    is_const = True
            if is_const:
                seg = ast.get_source_segment(source, node)
                if seg: shared_lines.append(seg + "\n")

    # _shared_context.py 書き出し
    with open(os.path.join(OUTPUT_DIR, '_shared_context.py'), 'w', encoding='utf-8') as f:
        f.write("# --- Common Imports and Constants ---\n")
        f.writelines(shared_lines)
    
    print(f"Created: _shared_context.py")

    # 3. クラス/関数の振り分け
    # バッファ: { 'skeleton': ["def ...", "def ..."], 'math': ... }
    category_buffers = {
        "io_data": [], "skeleton": [], "weights": [], "morphs": [],
        "math_geometry": [], "mesh_ops": [], "core_logic": [], "utils": []
    }
    
    # ノードを走査
    handled_nodes = set()
    
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            # エントリーポイントっぽいものはmainに残す
            if node.name == "main" or node.name.startswith("register") or node.name.startswith("unregister"):
                continue

            cat = get_category(node.name)
            seg = ast.get_source_segment(source, node)
            if seg:
                category_buffers[cat].append(seg + "\n\n")
                handled_nodes.add(node)

    # 4. サブモジュールファイルの作成
    created_modules = []
    for cat, contents in category_buffers.items():
        if not contents:
            continue
            
        filename = f"sub_{cat}.py"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # マジックインポート: 共有コンテキストをすべて読み込む
            # これにより、定数やimportが欠落するリスクを最小化する
            f.write("from ._shared_context import *\n")
            
            # 同一フォルダ内の別モジュールも互いに見えるようにしておく（循環参照リスクはあるが、まずは動かすため）
            # ここは必要に応じてコメントアウトしてください
            f.write("# Local sub-modules\n")
            for other_cat in category_buffers.keys():
                if other_cat != cat and category_buffers[other_cat]:
                    f.write(f"from .sub_{other_cat} import *\n")
            
            f.write("\n\n")
            f.writelines(contents)
        
        created_modules.append(filename[:-3]) # .pyなし
        print(f"Created: {filename} ({len(contents)} items)")

    # 5. 新しい main.py の作成
    # 処理済みの関数定義以外（つまりトップレベルの実行コードやmain関数）を集める
    main_lines = ["from ._shared_context import *\n"]
    for mod in created_modules:
        main_lines.append(f"from .{mod} import *\n")
    main_lines.append("\n\n")

    # 元のファイルから、切り出していない部分（実行ロジック）を抽出する
    # 簡易的に、tree.bodyを順に見て、handled_nodesに含まれないものを追記
    last_end_line = 0
    
    # ノードベースだとコメントや空行が抜けるので、
    # 割り切って「main関数」と「if __name__」ブロックなどをASTから探して書く
    
    remaining_nodes = []
    for node in tree.body:
        # Importや抽出済み関数はスキップ
        if isinstance(node, (ast.Import, ast.ImportFrom)): continue
        if isinstance(node, ast.Assign) and ast.get_source_segment(source, node) in shared_lines: continue # sharedに移した定数もスキップ
        
        if node in handled_nodes: continue
        
        # 残ったもの（main関数、実行文、変なグローバル変数など）
        remaining_nodes.append(node)

    for node in remaining_nodes:
        seg = ast.get_source_segment(source, node)
        if seg:
            main_lines.append(seg + "\n\n")

    with open(os.path.join(OUTPUT_DIR, 'main.py'), 'w', encoding='utf-8') as f:
        f.writelines(main_lines)
    
    # パッケージ用
    with open(os.path.join(OUTPUT_DIR, '__init__.py'), 'w') as f:
        f.write("")

    print(f"Created: main.py (Entry point)")

if __name__ == "__main__":
    main()