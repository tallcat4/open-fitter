"""AssetNormalizationStage: 読み込まれたアセットの正規化と初期設定を行うステージ"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from add_pose_from_json import add_pose_from_json
from algo_utils.vertex_group_utils import remove_empty_vertex_groups
from blender_utils.bone_utils import apply_bone_name_conversion
from blender_utils.weight_transfer_utils import setup_weight_transfer
from is_A_pose import is_A_pose
from math_utils.weight_utils import normalize_bone_weights
from blender_utils.armature_utils import normalize_clothing_bone_names
from update_base_avatar_weights import update_base_avatar_weights


class AssetNormalizationStage:
    """読み込まれたアセットの正規化と初期設定を行うステージ
    
    責務:
        - Aポーズ判定とベースポーズ適用
        - ウェイト転送のセットアップ
        - ボーン名の正規化
        - ベースアバターのウェイト更新・正規化
    
    前提:
        - AssetLoadingStage が完了していること
    
    成果物:
        - is_A_pose フラグ
        - base_weights_time タイムスタンプ
        - リターゲティング計算を開始できる整った状態
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module
        stage_start_time = time.time()
        is_final_pair = (p.pair_index == p.total_pairs - 1)

        # Aポーズ判定（最初のペアのみ）
        if p.pair_index == 0:
            p.is_A_pose = is_A_pose(
                p.clothing_avatar_data,
                p.clothing_armature,
                init_pose_filepath=p.config_pair['init_pose'],
                pose_filepath=p.config_pair['pose_data'],
                clothing_avatar_data_filepath=p.config_pair['clothing_avatar_data'],
            )
            print(f"is_A_pose: {p.is_A_pose}")

        # Aポーズの場合、Aポーズ用ベースポーズを使用
        if (
            p.is_A_pose
            and p.base_avatar_data
            and p.base_avatar_data.get('basePoseA', None)
        ):
            print("AポーズのためAポーズ用ベースポーズを使用")
            p.base_avatar_data['basePose'] = p.base_avatar_data['basePoseA']

        # ベースポーズ適用（最終pairのみ - base_armatureが必要）
        if is_final_pair:
            base_pose_filepath = p.base_avatar_data.get('basePose', None)
            if (
                base_pose_filepath
                and p.config_pair.get('do_not_use_base_pose', 0) == 0
            ):
                pose_dir = os.path.dirname(
                    os.path.abspath(p.config_pair['base_avatar_data'])
                )
                base_pose_filepath = os.path.join(pose_dir, base_pose_filepath)
                print(f"Applying target avatar base pose from {base_pose_filepath}")
                add_pose_from_json(
                    p.base_armature,
                    base_pose_filepath,
                    p.base_avatar_data,
                    invert=False,
                )
        else:
            print("=== PoC: 中間pairのためベースポーズ適用をスキップ ===")
        base_pose_time = time.time()
        print(f"ベースポーズ適用: {base_pose_time - stage_start_time:.2f}秒")

        # ウェイト転送セットアップ（最終pairのみ - Body.BaseAvatarが必要）
        print("Status: ウェイト転送セットアップ中")
        print(f"Progress: {(p.pair_index + 0.25) / p.total_pairs * 0.9:.3f}")
        if is_final_pair:
            setup_weight_transfer()
        else:
            print("=== PoC: 中間pairのためウェイト転送セットアップをスキップ ===")
        setup_time = time.time()
        print(f"ウェイト転送セットアップ: {setup_time - base_pose_time:.2f}秒")

        # ベースメッシュ処理（最終pairのみ - base_meshが必要）
        print("Status: ベースアバターウェイト更新中")
        print(f"Progress: {(p.pair_index + 0.3) / p.total_pairs * 0.9:.3f}")
        if is_final_pair:
            # ベースメッシュの空頂点グループを削除
            remove_empty_vertex_groups(p.base_mesh)
        else:
            print("=== PoC: 中間pairのためベースメッシュ処理をスキップ ===")

        # ボーン名変換（最初のペアで、変換ファイルがある場合）
        if (
            p.pair_index == 0
            and hasattr(p.args, 'name_conv')
            and p.args.name_conv
        ):
            try:
                with open(p.args.name_conv, 'r', encoding='utf-8') as f:
                    name_conv_data = json.load(f)
                apply_bone_name_conversion(
                    p.clothing_armature, p.clothing_meshes, name_conv_data
                )
                print(f"ボーン名前変更処理完了: {p.args.name_conv}")
            except Exception as e:
                print(f"Warning: ボーン名前変更処理でエラーが発生しました: {e}")

        # 衣装ボーン名の正規化
        normalize_clothing_bone_names(
            p.clothing_armature,
            p.clothing_avatar_data,
            p.clothing_meshes,
        )

        # ベースアバターのウェイト更新（最終pairのみ）
        if is_final_pair:
            update_base_avatar_weights(
                p.base_mesh,
                p.clothing_armature,
                p.base_avatar_data,
                p.clothing_avatar_data,
                preserve_optional_humanoid_bones=True,
            )

            # ボーンウェイトの正規化
            normalize_bone_weights(p.base_mesh, p.base_avatar_data)
        else:
            print("=== PoC: 中間pairのためベースアバターウェイト更新をスキップ ===")

        p.base_weights_time = time.time()
        print(f"ベースアバターウェイト更新: {p.base_weights_time - setup_time:.2f}秒")
