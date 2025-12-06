import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import json
import math

import bpy
import mathutils
from processing_context import ProcessingContext
from add_clothing_pose_from_json import add_clothing_pose_from_json
from add_pose_from_json import add_pose_from_json
from algo_utils.create_hinge_bone_group import create_hinge_bone_group
from algo_utils.find_containing_objects import find_containing_objects
from algo_utils.find_vertices_near_faces import find_vertices_near_faces
from algo_utils.process_humanoid_vertex_groups import process_humanoid_vertex_groups
from algo_utils.remove_empty_vertex_groups import remove_empty_vertex_groups
from apply_blendshape_deformation_fields import apply_blendshape_deformation_fields
from blender_utils.apply_all_transforms import apply_all_transforms
from blender_utils.apply_bone_field_delta import apply_bone_field_delta
from blender_utils.apply_bone_name_conversion import apply_bone_name_conversion
from blender_utils.apply_pose_as_rest import apply_pose_as_rest
from blender_utils.create_deformation_mask import create_deformation_mask
from blender_utils.create_overlapping_vertices_attributes import (
    create_overlapping_vertices_attributes,
)
from blender_utils.merge_and_clean_generated_shapekeys import (
    merge_and_clean_generated_shapekeys,
)
from blender_utils.merge_auxiliary_to_humanoid_weights import (
    merge_auxiliary_to_humanoid_weights,
)
from blender_utils.process_bone_weight_consolidation import (
    process_bone_weight_consolidation,
)
from blender_utils.process_clothing_avatar import process_clothing_avatar
from blender_utils.process_missing_bone_weights import process_missing_bone_weights
from blender_utils.propagate_bone_weights import propagate_bone_weights
from blender_utils.remove_propagated_weights import remove_propagated_weights
from blender_utils.reset_shape_keys import reset_shape_keys
from blender_utils.round_bone_coordinates import round_bone_coordinates
from blender_utils.set_armature_modifier_target_armature import (
    set_armature_modifier_target_armature,
)
from blender_utils.set_armature_modifier_visibility import (
    set_armature_modifier_visibility,
)
from blender_utils.set_highheel_shapekey_values import set_highheel_shapekey_values
from blender_utils.setup_weight_transfer import setup_weight_transfer
from blender_utils.subdivide_breast_faces import subdivide_breast_faces
from blender_utils.subdivide_long_edges import subdivide_long_edges
from blender_utils.transfer_weights_from_nearest_vertex import (
    transfer_weights_from_nearest_vertex,
)
from blender_utils.triangulate_mesh import triangulate_mesh
from common_utils.rename_shape_keys_from_mappings import rename_shape_keys_from_mappings
from common_utils.truncate_long_shape_key_names import truncate_long_shape_key_names
from duplicate_mesh_with_partial_weights import duplicate_mesh_with_partial_weights
from generate_temp_shapekeys_for_weight_transfer import (
    generate_temp_shapekeys_for_weight_transfer,
)
from io_utils.export_fbx import export_fbx
from io_utils.import_base_fbx import import_base_fbx
from io_utils.load_base_file import load_base_file
from io_utils.load_cloth_metadata import load_cloth_metadata
from io_utils.load_mesh_material_data import load_mesh_material_data
from io_utils.load_vertex_group import load_vertex_group
from io_utils.restore_armature_modifier import restore_armature_modifier
from io_utils.restore_vertex_weights import restore_vertex_weights
from io_utils.save_vertex_weights import save_vertex_weights
from io_utils.store_armature_modifier_settings import store_armature_modifier_settings
from is_A_pose import is_A_pose
from math_utils.normalize_bone_weights import normalize_bone_weights
from math_utils.normalize_clothing_bone_names import normalize_clothing_bone_names
from math_utils.normalize_overlapping_vertices_weights import (
    normalize_overlapping_vertices_weights,
)
from math_utils.normalize_vertex_weights import normalize_vertex_weights
from misc_utils.update_cloth_metadata import update_cloth_metadata
from process_base_avatar import process_base_avatar
from process_mesh_with_connected_components_inline import (
    process_mesh_with_connected_components_inline,
)
from process_weight_transfer_with_component_normalization import (
    process_weight_transfer_with_component_normalization,
)
from replace_humanoid_bones import replace_humanoid_bones
from temporarily_merge_for_weight_transfer import temporarily_merge_for_weight_transfer
from update_base_avatar_weights import update_base_avatar_weights
from stages.asset_preparation import AssetPreparationStage


class TemplateAdjustmentStage:
    """Applies Template-specific corrections before further processing."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            clothing_name = self.clothing_avatar_data.get("name", None)
            if clothing_name != "Template":
                return True

            print(f"Templateからの変換 股下の頂点グループを作成")
            current_active_object = bpy.context.view_layer.objects.active
            template_fbx_path = self.clothing_avatar_data.get("defaultFBXPath", None)
            clothing_avatar_data_path = self.config_pair['clothing_avatar_data']
            if template_fbx_path and not os.path.isabs(template_fbx_path):
                relative_parts = template_fbx_path.split(os.sep)
                if relative_parts:
                    top_dir = relative_parts[0]
                    clothing_path_parts = clothing_avatar_data_path.split(os.sep)
                    found_index = -1
                    for i in range(len(clothing_path_parts) - 1, -1, -1):
                        if clothing_path_parts[i] == top_dir:
                            found_index = i
                            break
                    if found_index != -1:
                        base_path = os.sep.join(clothing_path_parts[:found_index])
                        template_fbx_path = os.path.join(base_path, template_fbx_path)
                        template_fbx_path = os.path.normpath(template_fbx_path)
            print(f"template_fbx_path: {template_fbx_path}")
            import_base_fbx(template_fbx_path)
            template_obj = bpy.data.objects.get(
                self.clothing_avatar_data.get("meshName", None)
            )
            template_armature = None
            for modifier in template_obj.modifiers:
                if modifier.type == 'ARMATURE':
                    template_armature = modifier.object
                    break
            if template_armature is None:
                print(f"Warning: Armatureモディファイアが見つかりません")
                return False

            crotch_vertex_group_filepath = os.path.join(
                os.path.dirname(template_fbx_path), "vertex_group_weights_crotch.json"
            )
            crotch_group_name = load_vertex_group(
                template_obj, crotch_vertex_group_filepath
            )
            if crotch_group_name:
                print("  LeftUpperLegとRightUpperLegボーンにY軸回転を適用")
                bpy.context.view_layer.objects.active = template_armature
                bpy.ops.object.mode_set(mode='POSE')

                left_upper_leg_bone = None
                right_upper_leg_bone = None

                for bone_map in self.clothing_avatar_data.get("humanoidBones", []):
                    if bone_map.get("humanoidBoneName") == "LeftUpperLeg":
                        left_upper_leg_bone = bone_map.get("boneName")
                    elif bone_map.get("humanoidBoneName") == "RightUpperLeg":
                        right_upper_leg_bone = bone_map.get("boneName")

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.context.view_layer.update()

                for obj in self.clothing_meshes:
                    find_vertices_near_faces(
                        template_obj,
                        obj,
                        crotch_group_name,
                        0.01,
                        use_all_faces=True,
                        smooth_repeat=3,
                    )

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                bpy.context.view_layer.update()

            blur_vertex_group_filepath = os.path.join(
                os.path.dirname(template_fbx_path), "vertex_group_weights_blur.json"
            )
            blur_group_name = load_vertex_group(
                template_obj, blur_vertex_group_filepath
            )
            if blur_group_name:
                for obj in self.clothing_meshes:
                    transfer_weights_from_nearest_vertex(
                        template_obj, obj, blur_group_name
                    )
            inpaint_vertex_group_filepath = os.path.join(
                os.path.dirname(template_fbx_path), "vertex_group_weights_inpaint.json"
            )
            inpaint_group_name = load_vertex_group(
                template_obj, inpaint_vertex_group_filepath
            )
            if inpaint_group_name:
                for obj in self.clothing_meshes:
                    transfer_weights_from_nearest_vertex(
                        template_obj, obj, inpaint_group_name
                    )
            bpy.data.objects.remove(bpy.data.objects["Body.Template"], do_unlink=True)
            bpy.data.objects.remove(
                bpy.data.objects["Body.Template.Eyes"], do_unlink=True
            )
            bpy.data.objects.remove(
                bpy.data.objects["Body.Template.Head"], do_unlink=True
            )
            bpy.data.objects.remove(
                bpy.data.objects["Armature.Template"], do_unlink=True
            )
            print(f"Templateからの変換 股下の頂点グループ作成完了")
            bpy.context.view_layer.objects.active = current_active_object
            return True

        return _run(self.processor)


class MeshPreparationStage:
    """Executes mesh preparation (cycle 1) responsibilities."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            time = self.time_module

            print(f"Status: BlendShape用 Deformation Field適用中")
            print(
                f"Progress: {(self.pair_index + 0.33) / self.total_pairs * 0.9:.3f}"
            )
            self.blend_shape_labels = (
                self.config_pair['blend_shapes'].split(',')
                if self.config_pair['blend_shapes']
                else None
            )
            if self.blend_shape_labels:
                for obj in self.clothing_meshes:
                    reset_shape_keys(obj)
                    remove_empty_vertex_groups(obj)
                    normalize_vertex_weights(obj)
                    apply_blendshape_deformation_fields(
                        obj,
                        self.config_pair['field_data'],
                        self.blend_shape_labels,
                        self.clothing_avatar_data,
                        self.config_pair['blend_shape_values'],
                    )
            blendshape_time = time.time()
            print(
                f"BlendShape用 Deformation Field適用: {blendshape_time - self.base_weights_time:.2f}秒"
            )

            print(f"Status: ポーズ適用中")
            print(
                f"Progress: {(self.pair_index + 0.35) / self.total_pairs * 0.9:.3f}"
            )
            add_clothing_pose_from_json(
                self.clothing_armature,
                self.config_pair['pose_data'],
                self.config_pair['init_pose'],
                self.config_pair['clothing_avatar_data'],
                self.config_pair['base_avatar_data'],
            )
            pose_time = time.time()
            print(f"ポーズ適用: {pose_time - blendshape_time:.2f}秒")

            print(f"Status: 重複頂点属性設定中")
            print(
                f"Progress: {(self.pair_index + 0.4) / self.total_pairs * 0.9:.3f}"
            )
            create_overlapping_vertices_attributes(
                self.clothing_meshes, self.base_avatar_data
            )
            vertices_attributes_time = time.time()
            print(
                f"重複頂点属性設定: {vertices_attributes_time - pose_time:.2f}秒"
            )

            for obj in self.clothing_meshes:
                create_hinge_bone_group(
                    obj, self.clothing_armature, self.clothing_avatar_data
                )

            print(f"Status: メッシュ変形処理中")
            print(
                f"Progress: {(self.pair_index + 0.45) / self.total_pairs * 0.9:.3f}"
            )
            self.propagated_groups_map = {}
            field_distance_groups = {}
            cycle1_start = time.time()
            for obj in self.clothing_meshes:
                obj_start = time.time()
                print("cycle1 " + obj.name)

                reset_shape_keys(obj)
                remove_empty_vertex_groups(obj)
                normalize_vertex_weights(obj)
                merge_auxiliary_to_humanoid_weights(
                    obj, self.clothing_avatar_data
                )

                temp_group_name = propagate_bone_weights(obj)
                if temp_group_name:
                    self.propagated_groups_map[obj.name] = temp_group_name

                cleanup_weights_time_start = time.time()
                for vert in obj.data.vertices:
                    groups_to_remove = []
                    for g in vert.groups:
                        if g.weight < 0.0005:
                            groups_to_remove.append(g.group)
                    for group_idx in groups_to_remove:
                        try:
                            obj.vertex_groups[group_idx].remove([vert.index])
                        except RuntimeError:
                            continue
                cleanup_weights_time = time.time() - cleanup_weights_time_start
                print(f"  微小ウェイト除外: {cleanup_weights_time:.2f}秒")

                create_deformation_mask(obj, self.clothing_avatar_data)

                if (
                    self.pair_index == 0
                    and self.use_subdivision
                    and obj.name not in self.cloth_metadata
                ):
                    subdivide_long_edges(obj)
                    subdivide_breast_faces(obj, self.clothing_avatar_data)

                if (
                    self.use_triangulation
                    and not self.use_subdivision
                    and obj.name not in self.cloth_metadata
                    and self.pair_index == self.total_pairs - 1
                ):
                    triangulate_mesh(obj)

                original_weights = save_vertex_weights(obj)

                process_bone_weight_consolidation(
                    obj, self.clothing_avatar_data
                )

                process_mesh_with_connected_components_inline(
                    obj,
                    self.config_pair['field_data'],
                    self.blend_shape_labels,
                    self.clothing_avatar_data,
                    self.base_avatar_data,
                    self.clothing_armature,
                    self.cloth_metadata,
                    subdivision=self.use_subdivision,
                    skip_blend_shape_generation=self.config_pair[
                        'skip_blend_shape_generation'
                    ],
                    config_data=self.config_pair['config_data'],
                )

                restore_vertex_weights(obj, original_weights)

                if obj.data.shape_keys:
                    generated_shape_keys = []
                    for shape_key in obj.data.shape_keys.key_blocks:
                        if shape_key.name.endswith("_generated"):
                            generated_shape_keys.append(shape_key.name)

                    for generated_name in generated_shape_keys:
                        base_name = generated_name[:-10]
                        generated_key = obj.data.shape_keys.key_blocks.get(
                            generated_name
                        )
                        base_key = obj.data.shape_keys.key_blocks.get(base_name)

                        if generated_key and base_key:
                            for i, point in enumerate(generated_key.data):
                                base_key.data[i].co = point.co
                            print(
                                f"Merged {generated_name} into {base_name} for {obj.name}"
                            )
                            obj.shape_key_remove(generated_key)
                            print(
                                f"Removed generated shape key: {generated_name} from {obj.name}"
                            )

                print(f"  {obj.name}の処理: {time.time() - obj_start:.2f}秒")

            cycle1_end = time.time()
            self.cycle1_end_time = cycle1_end
            print(f"サイクル1全体: {cycle1_end - cycle1_start:.2f}秒")

            for obj in self.clothing_meshes:
                if obj.data.shape_keys:
                    for key_block in obj.data.shape_keys.key_blocks:
                        print(
                            f"Shape key: {key_block.name} / {key_block.value} found on {obj.name}"
                        )

        _run(self.processor)


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


class SceneFinalizationStage:
    """Executes the final scene prep and FBX export."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            time = self.time_module

            print(f"Status: ポーズ適用中")
            print(
                f"Progress: {(self.pair_index + 0.7) / self.total_pairs * 0.9:.3f}"
            )
            apply_pose_as_rest(self.clothing_armature)
            pose_rest_time = time.time()
            print(
                f"ポーズをレストポーズとして適用: {pose_rest_time - self.cycle2_post_end:.2f}秒"
            )

            print(f"Status: ボーンフィールドデルタ適用中")
            print(
                f"Progress: {(self.pair_index + 0.75) / self.total_pairs * 0.9:.3f}"
            )
            apply_bone_field_delta(
                self.clothing_armature,
                self.config_pair['field_data'],
                self.clothing_avatar_data,
            )
            bone_delta_time = time.time()
            print(f"ボーンフィールドデルタ適用: {bone_delta_time - pose_rest_time:.2f}秒")

            print(f"Status: ポーズ適用中")
            print(
                f"Progress: {(self.pair_index + 0.85) / self.total_pairs * 0.9:.3f}"
            )
            apply_pose_as_rest(self.clothing_armature)
            second_pose_rest_time = time.time()
            print(
                f"2回目のポーズをレストポーズとして適用: {second_pose_rest_time - bone_delta_time:.2f}秒"
            )

            print(f"Status: すべての変換を適用中")
            print(
                f"Progress: {(self.pair_index + 0.9) / self.total_pairs * 0.9:.3f}"
            )
            apply_all_transforms()
            transforms_time = time.time()
            print(f"すべての変換を適用: {transforms_time - second_pose_rest_time:.2f}秒")

            print(f"Status: 伝播ウェイト削除中")
            print(
                f"Progress: {(self.pair_index + 0.95) / self.total_pairs * 0.9:.3f}"
            )
            propagated_start = time.time()
            for obj in self.clothing_meshes:
                if obj.name in self.propagated_groups_map:
                    remove_propagated_weights(
                        obj, self.propagated_groups_map[obj.name]
                    )
            propagated_end = time.time()
            print(f"伝播ウェイト削除: {propagated_end - propagated_start:.2f}秒")

            if (
                self.original_humanoid_bones is not None
                or self.original_auxiliary_bones is not None
            ):
                print("元のhumanoidBonesとauxiliaryBonesを復元中...")
                if self.original_humanoid_bones is not None:
                    self.base_avatar_data['humanoidBones'] = (
                        self.original_humanoid_bones
                    )
                if self.original_auxiliary_bones is not None:
                    self.base_avatar_data['auxiliaryBones'] = (
                        self.original_auxiliary_bones
                    )
                print("元のボーンデータの復元完了")

            print(f"Status: ヒューマノイドボーン置換中")
            print(
                f"Progress: {(self.pair_index + 0.95) / self.total_pairs * 0.9:.3f}"
            )
            base_pose_filepath = None
            if self.config_pair.get('do_not_use_base_pose', 0) == 0:
                base_pose_filepath = self.base_avatar_data.get('basePose', None)
                if base_pose_filepath:
                    pose_dir = os.path.dirname(
                        os.path.abspath(self.config_pair['base_avatar_data'])
                    )
                    base_pose_filepath = os.path.join(pose_dir, base_pose_filepath)
            if self.pair_index == 0:
                replace_humanoid_bones(
                    self.base_armature,
                    self.clothing_armature,
                    self.base_avatar_data,
                    self.clothing_avatar_data,
                    True,
                    base_pose_filepath,
                    self.clothing_meshes,
                    False,
                )
            else:
                replace_humanoid_bones(
                    self.base_armature,
                    self.clothing_armature,
                    self.base_avatar_data,
                    self.clothing_avatar_data,
                    False,
                    base_pose_filepath,
                    self.clothing_meshes,
                    True,
                )
            bones_replace_time = time.time()
            print(f"ヒューマノイドボーン置換: {bones_replace_time - propagated_end:.2f}秒")

            print(f"Status: ブレンドシェイプ設定中")
            print(
                f"Progress: {(self.pair_index + 0.96) / self.total_pairs * 0.9:.3f}"
            )
            blendshape_start = time.time()
            if "clothingBlendShapeSettings" in self.config_pair['config_data']:
                blend_shape_settings = self.config_pair['config_data'][
                    "clothingBlendShapeSettings"
                ]

                for setting in blend_shape_settings:
                    label = setting.get("label")
                    if label in self.blend_shape_labels:
                        blendshapes = setting.get("blendshapes", [])
                        for bs in blendshapes:
                            shape_key_name = bs.get("name")
                            value = bs.get("value", 0)
                            for obj in self.clothing_meshes:
                                if (
                                    obj.data.shape_keys
                                    and shape_key_name in obj.data.shape_keys.key_blocks
                                ):
                                    obj.data.shape_keys.key_blocks[
                                        shape_key_name
                                    ].value = value / 100.0
                                    print(
                                        f"Set blendshape '{shape_key_name}' on {obj.name} to {value/100.0}"
                                    )
            blendshape_end = time.time()
            print(f"ブレンドシェイプ設定: {blendshape_end - blendshape_start:.2f}秒")

            print(f"Status: クロスメタデータ更新中")
            print(
                f"Progress: {(self.pair_index + 0.97) / self.total_pairs * 0.9:.3f}"
            )
            metadata_update_start = time.time()
            if self.args.cloth_metadata and os.path.exists(self.args.cloth_metadata):
                try:
                    with open(self.args.cloth_metadata, 'r', encoding='utf-8') as f:
                        metadata_dict = json.load(f)
                    update_cloth_metadata(
                        metadata_dict,
                        self.args.cloth_metadata,
                        self.vertex_index_mapping,
                    )

                except Exception as e:
                    print(f"Error processing cloth metadata: {e}")
                    import traceback

                    traceback.print_exc()
            metadata_update_end = time.time()
            print(
                f"クロスメタデータ更新: {metadata_update_end - metadata_update_start:.2f}秒"
            )

            print(f"Status: FBXエクスポート前処理中")
            print(
                f"Progress: {(self.pair_index + 0.975) / self.total_pairs * 0.9:.3f}"
            )
            preprocess_start = time.time()

            self.blend_shape_labels = []
            if self.args.blend_shapes:
                self.blend_shape_labels = [
                    label for label in self.args.blend_shapes.split(',')
                ]

            for obj in self.clothing_meshes:
                if obj.data.shape_keys:
                    for key_block in obj.data.shape_keys.key_blocks:
                        print(
                            f"Shape key: {key_block.name} / {key_block.value} found on {obj.name}"
                        )

            merge_and_clean_generated_shapekeys(
                self.clothing_meshes, self.blend_shape_labels
            )
            if self.clothing_avatar_data.get("name", None) == "Template":
                import re

                pattern = re.compile(r'___\d+$')
                for obj in self.clothing_meshes:
                    if obj.data.shape_keys:
                        keys_to_remove = []
                        for key_block in obj.data.shape_keys.key_blocks:
                            if pattern.search(key_block.name):
                                keys_to_remove.append(key_block.name)
                        for key_name in keys_to_remove:
                            key_block = obj.data.shape_keys.key_blocks.get(key_name)
                            if key_block:
                                obj.shape_key_remove(key_block)
                                print(f"Removed shape key: {key_name} from {obj.name}")

            if self.pair_index > 0:
                bpy.ops.object.mode_set(mode='OBJECT')
                clothing_blend_shape_labels = []
                for blend_shape_field in self.clothing_avatar_data[
                    'blendShapeFields'
                ]:
                    clothing_blend_shape_labels.append(blend_shape_field['label'])
                base_blend_shape_labels = []
                for blend_shape_field in self.base_avatar_data['blendShapeFields']:
                    base_blend_shape_labels.append(blend_shape_field['label'])
                for obj in self.clothing_meshes:
                    if obj.data.shape_keys:
                        for key_block in obj.data.shape_keys.key_blocks:
                            if (
                                key_block.name in clothing_blend_shape_labels
                                and key_block.name not in base_blend_shape_labels
                            ):
                                prev_shape_key = obj.data.shape_keys.key_blocks.get(
                                    key_block.name
                                )
                                obj.shape_key_remove(prev_shape_key)
                                print(
                                    f"Removed shape key: {key_block.name} from {obj.name}"
                                )

            set_highheel_shapekey_values(
                self.clothing_meshes,
                self.blend_shape_labels,
                self.base_avatar_data,
            )

            preprocess_end = time.time()
            print(f"FBXエクスポート前処理: {preprocess_end - preprocess_start:.2f}秒")

            bpy.ops.object.select_all(action='DESELECT')
            for obj in bpy.data.objects:
                if obj.name not in [
                    "Body.BaseAvatar",
                    "Armature.BaseAvatar",
                    "Body.BaseAvatar.RightOnly",
                    "Body.BaseAvatar.LeftOnly",
                ]:
                    obj.select_set(True)

            round_bone_coordinates(self.clothing_armature, decimal_places=6)

            print(f"Status: FBXエクスポート中")
            print(
                f"Progress: {(self.pair_index + 0.98) / self.total_pairs * 0.9:.3f}"
            )
            export_start = time.time()
            export_fbx(self.args.output)
            export_end = time.time()
            print(f"FBXエクスポート: {export_end - export_start:.2f}秒")

        _run(self.processor)






class SingleConfigProcessor:
    def __init__(self, args, config_pair, pair_index, total_pairs, overall_start_time):
        self.args = args
        self.config_pair = config_pair
        self.pair_index = pair_index
        self.total_pairs = total_pairs
        self.overall_start_time = overall_start_time
        self.ctx = ProcessingContext()

    @property
    def base_mesh(self):
        return self.ctx.base_mesh

    @base_mesh.setter
    def base_mesh(self, value):
        self.ctx.base_mesh = value

    @property
    def base_armature(self):
        return self.ctx.base_armature

    @base_armature.setter
    def base_armature(self, value):
        self.ctx.base_armature = value

    @property
    def base_avatar_data(self):
        return self.ctx.base_avatar_data

    @base_avatar_data.setter
    def base_avatar_data(self, value):
        self.ctx.base_avatar_data = value

    @property
    def clothing_meshes(self):
        return self.ctx.clothing_meshes

    @clothing_meshes.setter
    def clothing_meshes(self, value):
        self.ctx.clothing_meshes = value

    @property
    def clothing_armature(self):
        return self.ctx.clothing_armature

    @clothing_armature.setter
    def clothing_armature(self, value):
        self.ctx.clothing_armature = value

    @property
    def clothing_avatar_data(self):
        return self.ctx.clothing_avatar_data

    @clothing_avatar_data.setter
    def clothing_avatar_data(self, value):
        self.ctx.clothing_avatar_data = value

    @property
    def cloth_metadata(self):
        return self.ctx.cloth_metadata

    @cloth_metadata.setter
    def cloth_metadata(self, value):
        self.ctx.cloth_metadata = value

    @property
    def vertex_index_mapping(self):
        return self.ctx.vertex_index_mapping

    @vertex_index_mapping.setter
    def vertex_index_mapping(self, value):
        self.ctx.vertex_index_mapping = value

    @property
    def use_subdivision(self):
        return self.ctx.use_subdivision

    @use_subdivision.setter
    def use_subdivision(self, value):
        self.ctx.use_subdivision = value

    @property
    def use_triangulation(self):
        return self.ctx.use_triangulation

    @use_triangulation.setter
    def use_triangulation(self, value):
        self.ctx.use_triangulation = value

    @property
    def propagated_groups_map(self):
        return self.ctx.propagated_groups_map

    @propagated_groups_map.setter
    def propagated_groups_map(self, value):
        self.ctx.propagated_groups_map = value

    @property
    def original_humanoid_bones(self):
        return self.ctx.original_humanoid_bones

    @original_humanoid_bones.setter
    def original_humanoid_bones(self, value):
        self.ctx.original_humanoid_bones = value

    @property
    def original_auxiliary_bones(self):
        return self.ctx.original_auxiliary_bones

    @original_auxiliary_bones.setter
    def original_auxiliary_bones(self, value):
        self.ctx.original_auxiliary_bones = value

    @property
    def is_A_pose(self):
        return self.ctx.is_A_pose

    @is_A_pose.setter
    def is_A_pose(self, value):
        self.ctx.is_A_pose = value

    @property
    def blend_shape_labels(self):
        return self.ctx.blend_shape_labels

    @blend_shape_labels.setter
    def blend_shape_labels(self, value):
        self.ctx.blend_shape_labels = value

    @property
    def base_weights_time(self):
        return self.ctx.base_weights_time

    @base_weights_time.setter
    def base_weights_time(self, value):
        self.ctx.base_weights_time = value

    @property
    def cycle1_end_time(self):
        return self.ctx.cycle1_end_time

    @cycle1_end_time.setter
    def cycle1_end_time(self, value):
        self.ctx.cycle1_end_time = value

    @property
    def cycle2_post_end(self):
        return self.ctx.cycle2_post_end

    @cycle2_post_end.setter
    def cycle2_post_end(self, value):
        self.ctx.cycle2_post_end = value

    @property
    def time_module(self):
        return self.ctx.time_module

    @time_module.setter
    def time_module(self, value):
        self.ctx.time_module = value

    @property
    def start_time(self):
        return self.ctx.start_time

    @start_time.setter
    def start_time(self, value):
        self.ctx.start_time = value

    def execute(self):
        try:
            import time

            self.time_module = time
            self.start_time = time.time()

            self.use_subdivision = not self.args.no_subdivision
            if self.pair_index != 0:
                self.use_subdivision = False

            self.use_triangulation = not self.args.no_triangle

            bpy.ops.object.mode_set(mode='OBJECT')

            self._load_and_prepare_assets()  # ベース・衣装データの読み込みと初期準備
            if not self._apply_template_specific_adjustments():  # Template専用の調整処理
                return None
            self._execute_mesh_preparation_cycle()  # サイクル1: メッシュ前処理と形状調整
            self._perform_weight_transfer_cycle()  # サイクル2: ウェイト転送と後処理
            self._finalize_scene_and_export()  # 最終仕上げとFBXエクスポート

            total_time = time.time() - self.start_time
            print(f"Progress: {(self.pair_index + 1.0) / self.total_pairs * 0.9:.3f}")
            print(f"処理完了: 合計 {total_time:.2f}秒")
            return True

        except Exception as e:
            import traceback

            print("============= Error Details =============")
            print(f"Error message: {str(e)}")
            print("\n============= Full Stack Trace =============")
            print(traceback.format_exc())
            print("==========================================")

            output_blend = self.args.output.rsplit('.', 1)[0] + '.blend'
            bpy.ops.wm.save_as_mainfile(filepath=output_blend)

            return False

    def _load_and_prepare_assets(self):
        AssetPreparationStage(self).run()

    def _apply_template_specific_adjustments(self):
        return TemplateAdjustmentStage(self).run()

    def _execute_mesh_preparation_cycle(self):
        MeshPreparationStage(self).run()

    def _perform_weight_transfer_cycle(self):
        WeightTransferStage(self).run()

    def _finalize_scene_and_export(self):
        SceneFinalizationStage(self).run()


def process_single_config(args, config_pair, pair_index, total_pairs, overall_start_time):
    processor = SingleConfigProcessor(args, config_pair, pair_index, total_pairs, overall_start_time)
    return processor.execute()