"""BoneReplacementStage: ヒューマノイドボーン置換を担当するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from replace_humanoid_bones import replace_humanoid_bones


class BoneReplacementStage:
    """ヒューマノイドボーン置換を担当するステージ
    
    責務:
        - ベースアーマチュアから衣装アーマチュアへのヒューマノイドボーン置換
    
    前提:
        - PoseFinalizationStage が完了していること
    
    成果物:
        - ヒューマノイドボーンが置換された衣装アーマチュア
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module
        is_final_pair = (p.pair_index == p.total_pairs - 1)

        print("Status: ヒューマノイドボーン置換中")
        print(f"Progress: {(p.pair_index + 0.95) / p.total_pairs * 0.9:.3f}")

        # 中間pairではボーン置換をスキップ（base_armatureがNone）
        if not is_final_pair:
            print("=== PoC: 中間pairのためボーン置換をスキップ ===")
            p.bones_replace_time = time.time()
            return

        # ベースポーズファイルパスの取得
        base_pose_filepath = None
        if p.config_pair.get('do_not_use_base_pose', 0) == 0:
            base_pose_filepath = p.base_avatar_data.get('basePose', None)
            if base_pose_filepath:
                pose_dir = os.path.dirname(
                    os.path.abspath(p.config_pair['base_avatar_data'])
                )
                base_pose_filepath = os.path.join(pose_dir, base_pose_filepath)

        # ヒューマノイドボーン置換（最終pairのみ）
        if p.pair_index == 0:
            replace_humanoid_bones(
                p.base_armature,
                p.clothing_armature,
                p.base_avatar_data,
                p.clothing_avatar_data,
                True,
                base_pose_filepath,
                p.clothing_meshes,
                False,
            )
        else:
            replace_humanoid_bones(
                p.base_armature,
                p.clothing_armature,
                p.base_avatar_data,
                p.clothing_avatar_data,
                False,
                base_pose_filepath,
                p.clothing_meshes,
                True,
            )

        bones_replace_time = time.time()
        print(f"ヒューマノイドボーン置換: {bones_replace_time - p.propagated_end_time:.2f}秒")

        p.bones_replace_time = bones_replace_time
