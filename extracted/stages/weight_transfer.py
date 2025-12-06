import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
_GRANDPARENT_DIR = os.path.dirname(_PARENT_DIR)
for _p in (_PARENT_DIR, _GRANDPARENT_DIR):
    if _p not in sys.path:
        sys.path.append(_p)

from algo_utils.find_containing_objects import find_containing_objects
from algo_utils.find_vertices_near_faces import find_vertices_near_faces
from algo_utils.process_humanoid_vertex_groups import process_humanoid_vertex_groups
from blender_utils.process_missing_bone_weights import process_missing_bone_weights
from blender_utils.set_armature_modifier_target_armature import (
    set_armature_modifier_target_armature,
)
from blender_utils.set_armature_modifier_visibility import (
    set_armature_modifier_visibility,
)
from blender_utils.transfer_weights_from_nearest_vertex import (
    transfer_weights_from_nearest_vertex,
)
from duplicate_mesh_with_partial_weights import duplicate_mesh_with_partial_weights
from generate_temp_shapekeys_for_weight_transfer import (
    generate_temp_shapekeys_for_weight_transfer,
)
from io_utils.load_vertex_group import load_vertex_group
from io_utils.restore_armature_modifier import restore_armature_modifier
from io_utils.store_armature_modifier_settings import store_armature_modifier_settings
from math_utils.normalize_overlapping_vertices_weights import (
    normalize_overlapping_vertices_weights,
)
from process_weight_transfer_with_component_normalization import (
    process_weight_transfer_with_component_normalization,
)
from temporarily_merge_for_weight_transfer import temporarily_merge_for_weight_transfer


class WeightTransferStage:
    """Executes weight transfer cycle and surrounding adjustments."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            time = self.time_module

            right_base_mesh, left_base_mesh = duplicate_mesh_with_partial_weights(
                self.base_mesh, self.base_avatar_data
            )
            duplicate_time = time.time()
            print(
                f"ベースメッシュ複製: {duplicate_time - self.cycle1_end_time:.2f}秒"
            )

            print(f"Status: メッシュの包含関係検出中")
            print(
                f"Progress: {(self.pair_index + 0.5) / self.total_pairs * 0.9:.3f}"
            )
            containing_objects = find_containing_objects(
                self.clothing_meshes, threshold=0.04
            )
            print(
                f"Found {sum(len(contained) for contained in containing_objects.values())} objects that are contained within others"
            )
            containing_time = time.time()
            print(f"包含関係検出: {containing_time - duplicate_time:.2f}秒")

            weight_transfer_processed = set()
            armature_settings_dict = {}

            print(f"Status: サイクル2前処理中")
            print(
                f"Progress: {(self.pair_index + 0.55) / self.total_pairs * 0.9:.3f}"
            )
            cycle2_pre_start = time.time()

            self.original_humanoid_bones = None
            self.original_auxiliary_bones = None

            if (
                self.base_avatar_data.get('subHumanoidBones')
                or self.base_avatar_data.get('subAuxiliaryBones')
            ):
                print("subHumanoidBonesとsubAuxiliaryBonesを適用中...")

                if self.base_avatar_data.get('humanoidBones'):
                    self.original_humanoid_bones = self.base_avatar_data[
                        'humanoidBones'
                    ].copy()
                else:
                    self.original_humanoid_bones = []

                if self.base_avatar_data.get('auxiliaryBones'):
                    self.original_auxiliary_bones = self.base_avatar_data[
                        'auxiliaryBones'
                    ].copy()
                else:
                    self.original_auxiliary_bones = []

                if self.base_avatar_data.get('subHumanoidBones'):
                    sub_humanoid_bones = self.base_avatar_data['subHumanoidBones']
                    humanoid_bones = self.base_avatar_data.get('humanoidBones', [])

                    for sub_bone in sub_humanoid_bones:
                        sub_humanoid_name = sub_bone.get('humanoidBoneName')
                        if sub_humanoid_name:
                            for i, existing_bone in enumerate(humanoid_bones):
                                if (
                                    existing_bone.get('humanoidBoneName')
                                    == sub_humanoid_name
                                ):
                                    humanoid_bones[i] = sub_bone.copy()
                                    break
                            else:
                                humanoid_bones.append(sub_bone.copy())

                if self.base_avatar_data.get('subAuxiliaryBones'):
                    sub_auxiliary_bones = self.base_avatar_data['subAuxiliaryBones']
                    auxiliary_bones = self.base_avatar_data.get(
                        'auxiliaryBones', []
                    )

                    for sub_aux in sub_auxiliary_bones:
                        sub_humanoid_name = sub_aux.get('humanoidBoneName')
                        if sub_humanoid_name:
                            for i, existing_aux in enumerate(auxiliary_bones):
                                if (
                                    existing_aux.get('humanoidBoneName')
                                    == sub_humanoid_name
                                ):
                                    auxiliary_bones[i] = sub_aux.copy()
                                    break
                            else:
                                auxiliary_bones.append(sub_aux.copy())

                print("subHumanoidBonesとsubAuxiliaryBonesの適用完了")

            if (
                self.base_avatar_data.get("name", None) == "Template"
                and self.is_A_pose
                and self.base_avatar_data.get('basePoseA', None)
            ):
                armpit_vertex_group_filepath2 = os.path.join(
                    os.path.dirname(self.config_pair['base_fbx']),
                    "vertex_group_weights_armpit.json",
                )
                armpit_group_name2 = load_vertex_group(
                    self.base_mesh, armpit_vertex_group_filepath2
                )
                if armpit_group_name2:
                    for obj in self.clothing_meshes:
                        find_vertices_near_faces(
                            self.base_mesh, obj, armpit_group_name2, 0.1, 45.0
                        )
            if self.base_avatar_data.get("name", None) == "Template":
                crotch_vertex_group_filepath2 = os.path.join(
                    os.path.dirname(self.config_pair['base_fbx']),
                    "vertex_group_weights_crotch2.json",
                )
                crotch_group_name2 = load_vertex_group(
                    self.base_mesh, crotch_vertex_group_filepath2
                )
                if crotch_group_name2:
                    for obj in self.clothing_meshes:
                        find_vertices_near_faces(
                            self.base_mesh, obj, crotch_group_name2, 0.01, smooth_repeat=3
                        )
                blur_vertex_group_filepath2 = os.path.join(
                    os.path.dirname(self.config_pair['base_fbx']),
                    "vertex_group_weights_blur.json",
                )
                blur_group_name2 = load_vertex_group(
                    self.base_mesh, blur_vertex_group_filepath2
                )
                if blur_group_name2:
                    for obj in self.clothing_meshes:
                        transfer_weights_from_nearest_vertex(
                            self.base_mesh, obj, blur_group_name2
                        )
                inpaint_vertex_group_filepath2 = os.path.join(
                    os.path.dirname(self.config_pair['base_fbx']),
                    "vertex_group_weights_inpaint.json",
                )
                inpaint_group_name2 = load_vertex_group(
                    self.base_mesh, inpaint_vertex_group_filepath2
                )
                if inpaint_group_name2:
                    for obj in self.clothing_meshes:
                        transfer_weights_from_nearest_vertex(
                            self.base_mesh, obj, inpaint_group_name2
                        )

            for obj in self.clothing_meshes:
                obj_start = time.time()
                print("cycle2 (pre-weight transfer) " + obj.name)

                armature_settings = store_armature_modifier_settings(obj)
                armature_settings_dict[obj] = armature_settings

                generate_temp_shapekeys_for_weight_transfer(
                    obj, self.clothing_armature, self.clothing_avatar_data, self.is_A_pose
                )
                process_missing_bone_weights(
                    obj,
                    self.base_armature,
                    self.clothing_avatar_data,
                    self.base_avatar_data,
                    preserve_optional_humanoid_bones=False,
                )
                process_humanoid_vertex_groups(
                    obj,
                    self.clothing_armature,
                    self.base_avatar_data,
                    self.clothing_avatar_data,
                )
                restore_armature_modifier(obj, armature_settings_dict[obj])
                set_armature_modifier_visibility(obj, False, False)
                set_armature_modifier_target_armature(obj, self.base_armature)
                print(f"  {obj.name}の前処理: {time.time() - obj_start:.2f}秒")

            cycle2_pre_end = time.time()
            print(f"サイクル2前処理全体: {cycle2_pre_end - cycle2_pre_start:.2f}秒")

            print(
                f"config_pair.get('next_blendshape_settings', []): {self.config_pair.get('next_blendshape_settings', [])}"
            )

            print(f"Status: サイクル2ウェイト転送中")
            print(
                f"Progress: {(self.pair_index + 0.6) / self.total_pairs * 0.9:.3f}"
            )
            weight_transfer_start = time.time()
            for obj in self.clothing_meshes:
                if obj in weight_transfer_processed:
                    continue

                obj_start = time.time()
                if obj in containing_objects and containing_objects[obj]:
                    contained_objects = containing_objects[obj]
                    print(
                        f"{obj.name} contains {contained_objects} other objects within distance 0.02 - applying joint weight transfer"
                    )

                    temporarily_merge_for_weight_transfer(
                        obj,
                        contained_objects,
                        self.base_armature,
                        self.base_avatar_data,
                        self.clothing_avatar_data,
                        self.config_pair['field_data'],
                        self.clothing_armature,
                        self.config_pair.get('next_blendshape_settings', []),
                        self.cloth_metadata,
                    )

                    weight_transfer_processed.add(obj)
                    weight_transfer_processed.update(contained_objects)
                print(
                    f"  {obj.name}の包含ウェイト転送: {time.time() - obj_start:.2f}秒"
                )

            for obj in self.clothing_meshes:
                if obj in weight_transfer_processed:
                    continue
                obj_start = time.time()
                print(f"Applying individual weight transfer to {obj.name}")
                process_weight_transfer_with_component_normalization(
                    obj,
                    self.base_armature,
                    self.base_avatar_data,
                    self.clothing_avatar_data,
                    self.config_pair['field_data'],
                    self.clothing_armature,
                    self.config_pair.get('next_blendshape_settings', []),
                    self.cloth_metadata,
                )

                weight_transfer_processed.add(obj)
                print(f"  {obj.name}の個別ウェイト転送: {time.time() - obj_start:.2f}秒")

            normalize_overlapping_vertices_weights(
                self.clothing_meshes, self.base_avatar_data
            )

            weight_transfer_end = time.time()
            print(
                f"ウェイト転送処理全体: {weight_transfer_end - weight_transfer_start:.2f}秒"
            )

            print(f"Status: サイクル2後処理中")
            print(
                f"Progress: {(self.pair_index + 0.65) / self.total_pairs * 0.9:.3f}"
            )
            cycle2_post_start = time.time()
            for obj in self.clothing_meshes:
                obj_start = time.time()
                print("cycle2 (post-weight transfer) " + obj.name)
                set_armature_modifier_visibility(obj, True, True)
                set_armature_modifier_target_armature(
                    obj, self.clothing_armature
                )
                print(f"  {obj.name}の後処理: {time.time() - obj_start:.2f}秒")

            cycle2_post_end = time.time()
            self.cycle2_post_end = cycle2_post_end
            print(f"サイクル2後処理全体: {cycle2_post_end - cycle2_post_start:.2f}秒")

        _run(self.processor)
