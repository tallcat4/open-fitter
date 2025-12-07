"""PoseFinalizationStage: ポーズ適用・ボーン調整・変換適用・ウェイトクリーンアップを担当するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from blender_utils.mesh_utils import apply_all_transforms
from blender_utils.apply_bone_field_delta import apply_bone_field_delta
from blender_utils.armature_utils import apply_pose_as_rest
from blender_utils.weight_processing_utils import remove_propagated_weights


class PoseFinalizationStage:
    """ポーズ適用・ボーン調整・変換適用・ウェイトクリーンアップを担当するステージ
    
    責務:
        - ポーズをレストポーズとして適用（2回）
        - ボーンフィールドデルタ適用
        - すべての変換を適用
        - 伝播ウェイト削除
        - 元のボーンデータ復元
    
    前提:
        - WeightTransferPostProcessStage が完了していること
    
    成果物:
        - レストポーズが適用された衣装アーマチュア
        - クリーンアップされたウェイト
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module

        # ポーズをレストポーズとして適用（1回目）
        print("Status: ポーズ適用中")
        print(f"Progress: {(p.pair_index + 0.7) / p.total_pairs * 0.9:.3f}")
        apply_pose_as_rest(p.clothing_armature)
        pose_rest_time = time.time()
        print(f"ポーズをレストポーズとして適用: {pose_rest_time - p.cycle2_post_end:.2f}秒")

        # ボーンフィールドデルタ適用
        print("Status: ボーンフィールドデルタ適用中")
        print(f"Progress: {(p.pair_index + 0.75) / p.total_pairs * 0.9:.3f}")
        apply_bone_field_delta(
            p.clothing_armature,
            p.config_pair['field_data'],
            p.clothing_avatar_data,
        )
        bone_delta_time = time.time()
        print(f"ボーンフィールドデルタ適用: {bone_delta_time - pose_rest_time:.2f}秒")

        # ポーズをレストポーズとして適用（2回目）
        print("Status: ポーズ適用中")
        print(f"Progress: {(p.pair_index + 0.85) / p.total_pairs * 0.9:.3f}")
        apply_pose_as_rest(p.clothing_armature)
        second_pose_rest_time = time.time()
        print(f"2回目のポーズをレストポーズとして適用: {second_pose_rest_time - bone_delta_time:.2f}秒")

        # すべての変換を適用
        print("Status: すべての変換を適用中")
        print(f"Progress: {(p.pair_index + 0.9) / p.total_pairs * 0.9:.3f}")
        apply_all_transforms()
        transforms_time = time.time()
        print(f"すべての変換を適用: {transforms_time - second_pose_rest_time:.2f}秒")

        # 伝播ウェイト削除
        print("Status: 伝播ウェイト削除中")
        print(f"Progress: {(p.pair_index + 0.95) / p.total_pairs * 0.9:.3f}")
        propagated_start = time.time()
        for obj in p.clothing_meshes:
            if obj.name in p.propagated_groups_map:
                remove_propagated_weights(obj, p.propagated_groups_map[obj.name])
        propagated_end = time.time()
        print(f"伝播ウェイト削除: {propagated_end - propagated_start:.2f}秒")

        # 元のボーンデータ復元
        if p.original_humanoid_bones is not None or p.original_auxiliary_bones is not None:
            print("元のhumanoidBonesとauxiliaryBonesを復元中...")
            if p.original_humanoid_bones is not None:
                p.base_avatar_data['humanoidBones'] = p.original_humanoid_bones
            if p.original_auxiliary_bones is not None:
                p.base_avatar_data['auxiliaryBones'] = p.original_auxiliary_bones
            print("元のボーンデータの復元完了")

        p.propagated_end_time = propagated_end
