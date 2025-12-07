"""AssetLoadingStage: ファイル読み込みとFBXインポートに専念するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from blender_utils.process_clothing_avatar import process_clothing_avatar
from common_utils.rename_shape_keys_from_mappings import rename_shape_keys_from_mappings
from common_utils.truncate_long_shape_key_names import truncate_long_shape_key_names
from io_utils.io_utils import load_base_file
from io_utils.io_utils import load_cloth_metadata
from io_utils.io_utils import load_mesh_material_data
from process_base_avatar import process_base_avatar


class AssetLoadingStage:
    """ファイル読み込みとFBXインポートを担当するステージ
    
    責務:
        - ベースBlendファイルの読み込み
        - ベースアバターFBXのインポートと処理
        - 衣装アバターFBXのインポートと処理
        - メタデータ（Cloth, Material）の読み込み
    
    成果物:
        - base_mesh, base_armature, base_avatar_data
        - clothing_meshes, clothing_armature, clothing_avatar_data
        - cloth_metadata, vertex_index_mapping
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module
        is_final_pair = (p.pair_index == p.total_pairs - 1)

        # ベースBlendファイル読み込み
        print("Status: ベースファイル読み込み中")
        print(f"Progress: {(p.pair_index + 0.05) / p.total_pairs * 0.9:.3f}")
        load_base_file(p.args.base)
        base_load_time = time.time()
        print(f"ベースファイル読み込み: {base_load_time - p.start_time:.2f}秒")

        # ベースアバター処理（最終pairのみFBXをロード、中間pairはavatar_dataのみ）
        print("Status: ベースアバター処理中")
        print(f"Progress: {(p.pair_index + 0.1) / p.total_pairs * 0.9:.3f}")
        if is_final_pair:
            (
                p.base_mesh,
                p.base_armature,
                p.base_avatar_data,
            ) = process_base_avatar(
                p.config_pair['base_fbx'],
                p.config_pair['base_avatar_data'],
            )
        else:
            # 中間pair: avatar_dataのみロード、FBXはスキップ
            print("=== PoC: 中間pairのためbase_fbxロードをスキップ ===")
            from io_utils.io_utils import load_avatar_data
            p.base_avatar_data = load_avatar_data(p.config_pair['base_avatar_data'])
            p.base_mesh = None
            p.base_armature = None

        # 衣装アバター処理
        print("Status: 衣装データ処理中")
        print(f"Progress: {(p.pair_index + 0.15) / p.total_pairs * 0.9:.3f}")
        (
            p.clothing_meshes,
            p.clothing_armature,
            p.clothing_avatar_data,
        ) = process_clothing_avatar(
            p.config_pair['input_clothing_fbx_path'],
            p.config_pair['clothing_avatar_data'],
            p.config_pair['hips_position'],
            p.config_pair['target_meshes'],
            p.config_pair['mesh_renderers'],
        )

        # シェイプキーのリネーム（マッピングがある場合）
        if p.config_pair.get('blend_shape_mappings'):
            rename_shape_keys_from_mappings(
                p.clothing_meshes, p.config_pair['blend_shape_mappings']
            )

        # 長いシェイプキー名を短縮
        truncate_long_shape_key_names(p.clothing_meshes, p.clothing_avatar_data)

        clothing_process_time = time.time()
        print(f"衣装データ処理: {clothing_process_time - base_load_time:.2f}秒")

        # メタデータ読み込み
        print("Status: クロスメタデータ読み込み中")
        print(f"Progress: {(p.pair_index + 0.2) / p.total_pairs * 0.9:.3f}")
        (
            p.cloth_metadata,
            p.vertex_index_mapping,
        ) = load_cloth_metadata(p.args.cloth_metadata)
        metadata_load_time = time.time()
        print(f"クロスメタデータ読み込み: {metadata_load_time - clothing_process_time:.2f}秒")

        # マテリアルデータ読み込み（最初のペアのみ）
        if p.pair_index == 0:
            print("Status: メッシュマテリアルデータ読み込み中")
            print(f"Progress: {(p.pair_index + 0.22) / p.total_pairs * 0.9:.3f}")
            load_mesh_material_data(p.args.mesh_material_data)
            material_load_time = time.time()
            print(f"メッシュマテリアルデータ読み込み: {material_load_time - metadata_load_time:.2f}秒")
