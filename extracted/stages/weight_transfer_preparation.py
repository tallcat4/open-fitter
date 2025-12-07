"""WeightTransferPreparationStage: ウェイト転送の準備処理を担当するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from algo_utils.find_containing_objects import find_containing_objects
from algo_utils.mesh_topology_utils import find_vertices_near_faces
from algo_utils.process_humanoid_vertex_groups import process_humanoid_vertex_groups
from blender_utils.armature_utils import (
    restore_armature_modifier,
    set_armature_modifier_target_armature,
    set_armature_modifier_visibility,
    store_armature_modifier_settings,
)
from blender_utils.weight_processing_utils import process_missing_bone_weights
from blender_utils.transfer_weights_from_nearest_vertex import (
    transfer_weights_from_nearest_vertex,
)
from duplicate_mesh_with_partial_weights import duplicate_mesh_with_partial_weights
from generate_temp_shapekeys_for_weight_transfer import (
    generate_temp_shapekeys_for_weight_transfer,
)
from io_utils.load_vertex_group import load_vertex_group


class WeightTransferPreparationStage:
    """ウェイト転送の準備処理を担当するステージ
    
    責務:
        - ベースメッシュの左右複製
        - メッシュ間の包含関係検出
        - subHumanoidBones/subAuxiliaryBones の適用
        - Template固有の頂点グループ処理
        - 各メッシュの前処理（一時シェイプキー、欠損ボーンウェイト等）
    
    前提:
        - MeshDeformationStage が完了していること
    
    成果物:
        - containing_objects（包含関係マップ）
        - armature_settings_dict（アーマチュア設定保存）
        - original_humanoid_bones, original_auxiliary_bones
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module

        # ベースメッシュ複製
        right_base_mesh, left_base_mesh = duplicate_mesh_with_partial_weights(
            p.base_mesh, p.base_avatar_data
        )
        duplicate_time = time.time()
        print(f"ベースメッシュ複製: {duplicate_time - p.cycle1_end_time:.2f}秒")

        # 包含関係検出
        print("Status: メッシュの包含関係検出中")
        print(f"Progress: {(p.pair_index + 0.5) / p.total_pairs * 0.9:.3f}")
        p.containing_objects = find_containing_objects(p.clothing_meshes, threshold=0.04)
        print(
            f"Found {sum(len(contained) for contained in p.containing_objects.values())} objects that are contained within others"
        )
        containing_time = time.time()
        print(f"包含関係検出: {containing_time - duplicate_time:.2f}秒")

        # 前処理開始
        print("Status: サイクル2前処理中")
        print(f"Progress: {(p.pair_index + 0.55) / p.total_pairs * 0.9:.3f}")
        cycle2_pre_start = time.time()

        # ボーンデータ準備
        self._apply_sub_bone_data(p)

        # Template固有の頂点グループ処理
        self._apply_template_vertex_groups(p)

        # 各メッシュの前処理
        p.armature_settings_dict = {}
        for obj in p.clothing_meshes:
            self._preprocess_mesh(obj, p, time)

        cycle2_pre_end = time.time()
        print(f"サイクル2前処理全体: {cycle2_pre_end - cycle2_pre_start:.2f}秒")

        print(
            f"config_pair.get('next_blendshape_settings', []): {p.config_pair.get('next_blendshape_settings', [])}"
        )

    def _apply_sub_bone_data(self, p):
        """subHumanoidBones/subAuxiliaryBones を適用"""
        p.original_humanoid_bones = None
        p.original_auxiliary_bones = None

        if not (
            p.base_avatar_data.get('subHumanoidBones')
            or p.base_avatar_data.get('subAuxiliaryBones')
        ):
            return

        print("subHumanoidBonesとsubAuxiliaryBonesを適用中...")

        # 元のボーンデータを保存
        if p.base_avatar_data.get('humanoidBones'):
            p.original_humanoid_bones = p.base_avatar_data['humanoidBones'].copy()
        else:
            p.original_humanoid_bones = []

        if p.base_avatar_data.get('auxiliaryBones'):
            p.original_auxiliary_bones = p.base_avatar_data['auxiliaryBones'].copy()
        else:
            p.original_auxiliary_bones = []

        # subHumanoidBones の適用
        if p.base_avatar_data.get('subHumanoidBones'):
            sub_humanoid_bones = p.base_avatar_data['subHumanoidBones']
            humanoid_bones = p.base_avatar_data.get('humanoidBones', [])

            for sub_bone in sub_humanoid_bones:
                sub_humanoid_name = sub_bone.get('humanoidBoneName')
                if sub_humanoid_name:
                    for i, existing_bone in enumerate(humanoid_bones):
                        if existing_bone.get('humanoidBoneName') == sub_humanoid_name:
                            humanoid_bones[i] = sub_bone.copy()
                            break
                    else:
                        humanoid_bones.append(sub_bone.copy())

        # subAuxiliaryBones の適用
        if p.base_avatar_data.get('subAuxiliaryBones'):
            sub_auxiliary_bones = p.base_avatar_data['subAuxiliaryBones']
            auxiliary_bones = p.base_avatar_data.get('auxiliaryBones', [])

            for sub_aux in sub_auxiliary_bones:
                sub_humanoid_name = sub_aux.get('humanoidBoneName')
                if sub_humanoid_name:
                    for i, existing_aux in enumerate(auxiliary_bones):
                        if existing_aux.get('humanoidBoneName') == sub_humanoid_name:
                            auxiliary_bones[i] = sub_aux.copy()
                            break
                    else:
                        auxiliary_bones.append(sub_aux.copy())

        print("subHumanoidBonesとsubAuxiliaryBonesの適用完了")

    def _apply_template_vertex_groups(self, p):
        """Template固有の頂点グループ処理"""
        # 脇の頂点グループ（AポーズかつbasePoseAがある場合のみ）
        if (
            p.base_avatar_data.get("name", None) == "Template"
            and p.is_A_pose
            and p.base_avatar_data.get('basePoseA', None)
        ):
            armpit_vertex_group_filepath = os.path.join(
                os.path.dirname(p.config_pair['base_fbx']),
                "vertex_group_weights_armpit.json",
            )
            armpit_group_name = load_vertex_group(p.base_mesh, armpit_vertex_group_filepath)
            if armpit_group_name:
                for obj in p.clothing_meshes:
                    find_vertices_near_faces(p.base_mesh, obj, armpit_group_name, 0.1, 45.0)

        # その他のTemplate固有頂点グループ
        if p.base_avatar_data.get("name", None) != "Template":
            return

        base_fbx_dir = os.path.dirname(p.config_pair['base_fbx'])

        # 股下グループ
        crotch_filepath = os.path.join(base_fbx_dir, "vertex_group_weights_crotch2.json")
        crotch_group_name = load_vertex_group(p.base_mesh, crotch_filepath)
        if crotch_group_name:
            for obj in p.clothing_meshes:
                find_vertices_near_faces(p.base_mesh, obj, crotch_group_name, 0.01, smooth_repeat=3)

        # ぼかしグループ
        blur_filepath = os.path.join(base_fbx_dir, "vertex_group_weights_blur.json")
        blur_group_name = load_vertex_group(p.base_mesh, blur_filepath)
        if blur_group_name:
            for obj in p.clothing_meshes:
                transfer_weights_from_nearest_vertex(p.base_mesh, obj, blur_group_name)

        # インペイントグループ
        inpaint_filepath = os.path.join(base_fbx_dir, "vertex_group_weights_inpaint.json")
        inpaint_group_name = load_vertex_group(p.base_mesh, inpaint_filepath)
        if inpaint_group_name:
            for obj in p.clothing_meshes:
                transfer_weights_from_nearest_vertex(p.base_mesh, obj, inpaint_group_name)

    def _preprocess_mesh(self, obj, p, time):
        """単一メッシュの前処理"""
        obj_start = time.time()
        print("cycle2 (pre-weight transfer) " + obj.name)

        # アーマチュア設定を保存
        armature_settings = store_armature_modifier_settings(obj)
        p.armature_settings_dict[obj] = armature_settings

        # 一時シェイプキー生成
        generate_temp_shapekeys_for_weight_transfer(
            obj, p.clothing_armature, p.clothing_avatar_data, p.is_A_pose
        )

        # 欠損ボーンウェイト処理
        process_missing_bone_weights(
            obj,
            p.base_armature,
            p.clothing_avatar_data,
            p.base_avatar_data,
            preserve_optional_humanoid_bones=False,
        )

        # ヒューマノイド頂点グループ処理
        process_humanoid_vertex_groups(
            obj,
            p.clothing_armature,
            p.base_avatar_data,
            p.clothing_avatar_data,
        )

        # アーマチュア設定復元・切り替え
        restore_armature_modifier(obj, p.armature_settings_dict[obj])
        set_armature_modifier_visibility(obj, False, False)
        set_armature_modifier_target_armature(obj, p.base_armature)

        print(f"  {obj.name}の前処理: {time.time() - obj_start:.2f}秒")
