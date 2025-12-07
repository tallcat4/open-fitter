import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import math
import time
from collections import deque

import bmesh
import bpy
import mathutils
import numpy as np
from algo_utils.get_humanoid_and_auxiliary_bone_groups import (
    get_humanoid_and_auxiliary_bone_groups,
)
from apply_distance_normal_based_smoothing import apply_distance_normal_based_smoothing
from blender_utils.adjust_hand_weights import adjust_hand_weights
from blender_utils.build_bone_maps import build_bone_maps
from blender_utils.create_blendshape_mask import create_blendshape_mask
from blender_utils.propagate_weights_to_side_vertices import (
    propagate_weights_to_side_vertices,
)
from blender_utils.reset_bone_weights import reset_bone_weights
from create_distance_normal_based_vertex_group import (
    create_distance_normal_based_vertex_group,
)
from create_side_weight_groups import create_side_weight_groups
from io_utils.restore_shape_key_state import restore_shape_key_state
from io_utils.restore_weights import restore_weights
from io_utils.save_shape_key_state import save_shape_key_state
from io_utils.store_weights import store_weights
from stages.compute_non_humanoid_masks import compute_non_humanoid_masks
from stages.merge_added_groups import merge_added_groups


class WeightTransferContext:
    """Stateful context to orchestrate weight transfer without changing external IO."""

    def __init__(self, target_obj, armature, base_avatar_data, clothing_avatar_data, field_path, clothing_armature, cloth_metadata=None):
        self.target_obj = target_obj
        self.armature = armature
        self.base_avatar_data = base_avatar_data
        self.clothing_avatar_data = clothing_avatar_data
        self.field_path = field_path
        self.clothing_armature = clothing_armature
        self.cloth_metadata = cloth_metadata
        self.start_time = time.time()

        self.humanoid_to_bone = {}
        self.bone_to_humanoid = {}
        self.auxiliary_bones = {}
        self.auxiliary_bones_to_humanoid = {}
        self.finger_humanoid_bones = [
            "LeftIndexProximal", "LeftIndexIntermediate", "LeftIndexDistal",
            "LeftMiddleProximal", "LeftMiddleIntermediate", "LeftMiddleDistal",
            "LeftRingProximal", "LeftRingIntermediate", "LeftRingDistal",
            "LeftLittleProximal", "LeftLittleIntermediate", "LeftLittleDistal",
            "RightIndexProximal", "RightIndexIntermediate", "RightIndexDistal",
            "RightMiddleProximal", "RightMiddleIntermediate", "RightMiddleDistal",
            "RightRingProximal", "RightRingIntermediate", "RightRingDistal",
            "RightLittleProximal", "RightLittleIntermediate", "RightLittleDistal",
            "LeftHand", "RightHand",
        ]
        self.left_foot_finger_humanoid_bones = [
            "LeftFootThumbProximal",
            "LeftFootThumbIntermediate",
            "LeftFootThumbDistal",
            "LeftFootIndexProximal",
            "LeftFootIndexIntermediate",
            "LeftFootIndexDistal",
            "LeftFootMiddleProximal",
            "LeftFootMiddleIntermediate",
            "LeftFootMiddleDistal",
            "LeftFootRingProximal",
            "LeftFootRingIntermediate",
            "LeftFootRingDistal",
            "LeftFootLittleProximal",
            "LeftFootLittleIntermediate",
            "LeftFootLittleDistal",
        ]
        self.right_foot_finger_humanoid_bones = [
            "RightFootThumbProximal",
            "RightFootThumbIntermediate",
            "RightFootThumbDistal",
            "RightFootIndexProximal",
            "RightFootIndexIntermediate",
            "RightFootIndexDistal",
            "RightFootMiddleProximal",
            "RightFootMiddleIntermediate",
            "RightFootMiddleDistal",
            "RightFootRingProximal",
            "RightFootRingIntermediate",
            "RightFootRingDistal",
            "RightFootLittleProximal",
            "RightFootLittleIntermediate",
            "RightFootLittleDistal",
        ]

        self.finger_bone_names = set()
        self.finger_vertices = set()
        self.closing_filter_mask_weights = None
        self.original_groups = set()
        self.bone_groups = set()
        self.all_deform_groups = set()
        self.original_non_humanoid_groups = set()
        self.original_humanoid_weights = {}
        self.original_non_humanoid_weights = {}
        self.all_weights = {}
        self.new_groups = set()
        self.added_groups = set()
        self.non_humanoid_parts_mask = None
        self.non_humanoid_total_weights = None
        self.non_humanoid_difference_mask = None
        self.distance_falloff_group = None
        self.distance_falloff_group2 = None
        self.non_humanoid_difference_group = None
        self.weights_a = {}
        self.weights_b = {}

    def _build_bone_maps(self):
        """ヒューマノイドボーンと補助ボーンのマッピングを構築する。"""
        (
            self.humanoid_to_bone,
            self.bone_to_humanoid,
            self.auxiliary_bones,
            self.auxiliary_bones_to_humanoid,
        ) = build_bone_maps(self.base_avatar_data)

    def detect_finger_vertices(self):
        for humanoid_bone in self.finger_humanoid_bones:
            if humanoid_bone in self.humanoid_to_bone:
                bone_name = self.humanoid_to_bone[humanoid_bone]
                self.finger_bone_names.add(bone_name)
                if humanoid_bone in self.auxiliary_bones:
                    for aux_bone in self.auxiliary_bones[humanoid_bone]:
                        self.finger_bone_names.add(aux_bone)

        print(f"finger_bone_names: {self.finger_bone_names}")

        if not self.finger_bone_names:
            return

        mesh = self.target_obj.data
        for bone_name in self.finger_bone_names:
            if bone_name in self.target_obj.vertex_groups:
                for vert in mesh.vertices:
                    weight = 0.0
                    for g in vert.groups:
                        if self.target_obj.vertex_groups[g.group].name == bone_name:
                            weight = g.weight
                            break
                    if weight > 0.001:
                        self.finger_vertices.add(vert.index)
        print(f"finger_vertices: {len(self.finger_vertices)}")

    def create_closing_filter_mask(self):
        self.closing_filter_mask_weights = create_blendshape_mask(
            self.target_obj,
            ["LeftUpperLeg", "RightUpperLeg", "Hips", "Chest", "Spine", "LeftShoulder", "RightShoulder", "LeftBreast", "RightBreast"],
            self.base_avatar_data,
        )

    def attempt_weight_transfer(self, source_obj, vertex_group, max_distance_try=0.2, max_distance_tried=0.0):
        bone_groups_tmp = get_humanoid_and_auxiliary_bone_groups(self.base_avatar_data)
        prev_weights = store_weights(self.target_obj, bone_groups_tmp)
        initial_max_distance = max_distance_try

        while max_distance_try <= 1.0:
            if max_distance_tried + 0.0001 < max_distance_try:
                create_distance_normal_based_vertex_group(
                    bpy.data.objects["Body.BaseAvatar"],
                    self.target_obj,
                    max_distance_try,
                    0.005,
                    20.0,
                    "InpaintMask",
                    normal_radius=0.003,
                    filter_mask=self.closing_filter_mask_weights,
                )

                if self.finger_vertices:
                    for vert_idx in self.finger_vertices:
                        self.target_obj.vertex_groups["InpaintMask"].add([vert_idx], 0.0, "REPLACE")

                if "MF_Inpaint" in self.target_obj.vertex_groups and "InpaintMask" in self.target_obj.vertex_groups:
                    inpaint_group = self.target_obj.vertex_groups["InpaintMask"]
                    source_group = self.target_obj.vertex_groups["MF_Inpaint"]

                    for vert in self.target_obj.data.vertices:
                        source_weight = 0.0
                        for g in vert.groups:
                            if g.group == source_group.index:
                                source_weight = g.weight
                                break
                        inpaint_weight = 0.0
                        for g in vert.groups:
                            if g.group == inpaint_group.index:
                                inpaint_weight = g.weight
                                break
                        inpaint_group.add([vert.index], source_weight * inpaint_weight, "REPLACE")

                if "InpaintMask" in self.target_obj.vertex_groups and vertex_group in self.target_obj.vertex_groups:
                    inpaint_group = self.target_obj.vertex_groups["InpaintMask"]
                    source_group = self.target_obj.vertex_groups[vertex_group]

                    for vert in self.target_obj.data.vertices:
                        source_weight = 0.0
                        for g in vert.groups:
                            if g.group == source_group.index:
                                source_weight = g.weight
                                break
                        if source_weight == 0.0:
                            inpaint_group.add([vert.index], 0.0, "REPLACE")

            try:
                bpy.context.scene.robust_weight_transfer_settings.source_object = source_obj
                bpy.context.object.robust_weight_transfer_settings.vertex_group = vertex_group
                bpy.context.scene.robust_weight_transfer_settings.inpaint_mode = "POINT"
                bpy.context.scene.robust_weight_transfer_settings.max_distance = max_distance_try
                bpy.context.scene.robust_weight_transfer_settings.use_deformed_target = True
                bpy.context.scene.robust_weight_transfer_settings.use_deformed_source = True
                bpy.context.scene.robust_weight_transfer_settings.enforce_four_bone_limit = True
                bpy.context.scene.robust_weight_transfer_settings.max_normal_angle_difference = 1.5708
                bpy.context.scene.robust_weight_transfer_settings.flip_vertex_normal = True
                bpy.context.scene.robust_weight_transfer_settings.smoothing_enable = False
                bpy.context.scene.robust_weight_transfer_settings.smoothing_repeat = 4
                bpy.context.scene.robust_weight_transfer_settings.smoothing_factor = 0.5
                bpy.context.object.robust_weight_transfer_settings.inpaint_group = "InpaintMask"
                bpy.context.object.robust_weight_transfer_settings.inpaint_threshold = 0.5
                bpy.context.object.robust_weight_transfer_settings.inpaint_group_invert = False
                bpy.context.object.robust_weight_transfer_settings.vertex_group_invert = False
                bpy.context.scene.robust_weight_transfer_settings.group_selection = "DEFORM_POSE_BONES"
                bpy.ops.object.skin_weight_transfer()
                print(f"Weight transfered with max_distance {max_distance_try}")
                return True, max_distance_try
            except RuntimeError as exc:
                print(f"Weight transfer failed with max_distance {max_distance_try}: {str(exc)}")
                restore_weights(self.target_obj, prev_weights)
                max_distance_try += 0.05
                if max_distance_try > 1.0:
                    print("Max distance exceeded 1.0, stopping weight transfer attempts")
                    return False, initial_max_distance
        return False, initial_max_distance

    def _propagate_weights_to_side_vertices(self, max_iterations=100):
        """側面ウェイトを持つがボーンウェイトを持たない頂点にウェイトを伝播する。"""
        propagate_weights_to_side_vertices(
            target_obj=self.target_obj,
            bone_groups=self.bone_groups,
            original_humanoid_weights=self.original_humanoid_weights,
            clothing_armature=self.clothing_armature,
            max_iterations=max_iterations,
        )

    def prepare_groups_and_weights(self):
        if "InpaintMask" not in self.target_obj.vertex_groups:
            self.target_obj.vertex_groups.new(name="InpaintMask")

        side_weight_time_start = time.time()
        create_side_weight_groups(self.target_obj, self.base_avatar_data, self.clothing_armature, self.clothing_avatar_data)
        side_weight_time = time.time() - side_weight_time_start
        print(f"  側面ウェイトグループ作成: {side_weight_time:.2f}秒")

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = self.target_obj

        self.original_groups = set(vg.name for vg in self.target_obj.vertex_groups)
        self.bone_groups = set(get_humanoid_and_auxiliary_bone_groups(self.base_avatar_data))

        store_weights_time_start = time.time()
        self.original_humanoid_weights = store_weights(self.target_obj, self.bone_groups)
        store_weights_time = time.time() - store_weights_time_start
        print(f"  元のウェイト保存: {store_weights_time:.2f}秒")

        self.all_deform_groups = set(self.bone_groups)
        if self.clothing_armature:
            self.all_deform_groups.update(bone.name for bone in self.clothing_armature.data.bones)

        self.original_non_humanoid_groups = self.all_deform_groups - self.bone_groups
        self.original_non_humanoid_weights = store_weights(self.target_obj, self.original_non_humanoid_groups)
        self.all_weights = store_weights(self.target_obj, self.all_deform_groups)

        reset_weights_time_start = time.time()
        reset_bone_weights(self.target_obj, self.all_deform_groups)
        reset_weights_time = time.time() - reset_weights_time_start
        print(f"  ウェイト初期化: {reset_weights_time:.2f}秒")

    def transfer_side_weights(self):
        left_transfer_time_start = time.time()
        left_transfer_success, left_distance_used = self.attempt_weight_transfer(
            bpy.data.objects["Body.BaseAvatar.LeftOnly"], "LeftSideWeights"
        )
        left_transfer_time = time.time() - left_transfer_time_start
        print(f"  左側ウェイト転送: {left_transfer_time:.2f}秒 (成功: {left_transfer_success}, 距離: {left_distance_used})")

        if not left_transfer_success:
            print("  左側ウェイト転送失敗のため処理中断")
            reset_bone_weights(self.target_obj, self.bone_groups)
            restore_weights(self.target_obj, self.all_weights)
            return False

        right_transfer_time_start = time.time()
        right_transfer_success, right_distance_used = self.attempt_weight_transfer(
            bpy.data.objects["Body.BaseAvatar.RightOnly"], "RightSideWeights", max_distance_tried=left_distance_used
        )
        right_transfer_time = time.time() - right_transfer_time_start
        print(f"  右側ウェイト転送: {right_transfer_time:.2f}秒 (成功: {right_transfer_success}, 距離: {right_distance_used})")

        if not right_transfer_success:
            print("  右側ウェイト転送失敗のため処理中断")
            reset_bone_weights(self.target_obj, self.bone_groups)
            restore_weights(self.target_obj, self.all_weights)
            return False
        return True

    def _process_mf_group(self, group_name, temp_shape_name, rotation_deg, humanoid_label_left, humanoid_label_right):
        target_group = self.target_obj.vertex_groups.get(group_name)
        should_process = False
        if target_group:
            for vert in self.target_obj.data.vertices:
                for g in vert.groups:
                    if g.group == target_group.index and g.weight > 0.001:
                        should_process = True
                        break
                if should_process:
                    break

        if not should_process:
            print(f"  {group_name}グループが存在しないか、有効なウェイトがないため処理をスキップ")
            return

        if not (self.armature and self.armature.type == "ARMATURE"):
            print(f"  {group_name}グループが存在しないか、アーマチュアが存在しないため処理をスキップ")
            return

        print(f"  {group_name}グループが存在し、有効なウェイトを持つため処理を実行")
        base_humanoid_weights = store_weights(self.target_obj, self.bone_groups)
        reset_bone_weights(self.target_obj, self.bone_groups)
        restore_weights(self.target_obj, self.all_weights)

        print(f"  {humanoid_label_left}と{humanoid_label_right}ボーンにY軸回転を適用")
        bpy.context.view_layer.objects.active = self.armature
        bpy.ops.object.mode_set(mode="POSE")

        left_bone = None
        right_bone = None
        for bone_map in self.base_avatar_data.get("humanoidBones", []):
            if bone_map.get("humanoidBoneName") == humanoid_label_left:
                left_bone = bone_map.get("boneName")
            elif bone_map.get("humanoidBoneName") == humanoid_label_right:
                right_bone = bone_map.get("boneName")

        if left_bone and left_bone in self.armature.pose.bones:
            bone = self.armature.pose.bones[left_bone]
            current_world_matrix = self.armature.matrix_world @ bone.matrix
            head_world_transformed = self.armature.matrix_world @ bone.head
            offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
            rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg * -1), 4, "Y")
            bone.matrix = self.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

        if right_bone and right_bone in self.armature.pose.bones:
            bone = self.armature.pose.bones[right_bone]
            current_world_matrix = self.armature.matrix_world @ bone.matrix
            head_world_transformed = self.armature.matrix_world @ bone.head
            offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
            rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg), 4, "Y")
            bone.matrix = self.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.objects.active = self.target_obj
        bpy.context.view_layer.update()

        shape_key_state = save_shape_key_state(self.target_obj)
        for key_block in self.target_obj.data.shape_keys.key_blocks:
            key_block.value = 0.0

        if self.target_obj.data.shape_keys and temp_shape_name in self.target_obj.data.shape_keys.key_blocks:
            temp_shape_key = self.target_obj.data.shape_keys.key_blocks[temp_shape_name]
            temp_shape_key.value = 1.0
        else:
            temp_shape_key = None

        reset_bone_weights(self.target_obj, self.bone_groups)
        print("  ウェイト転送開始")
        self.attempt_weight_transfer(bpy.data.objects["Body.BaseAvatar"], "BothSideWeights")

        restore_shape_key_state(self.target_obj, shape_key_state)
        if temp_shape_key:
            temp_shape_key.value = 0.0

        print(f"  {humanoid_label_left}と{humanoid_label_right}ボーンにY軸逆回転を適用")
        bpy.context.view_layer.objects.active = self.armature
        bpy.ops.object.mode_set(mode="POSE")

        if left_bone and left_bone in self.armature.pose.bones:
            bone = self.armature.pose.bones[left_bone]
            current_world_matrix = self.armature.matrix_world @ bone.matrix
            head_world_transformed = self.armature.matrix_world @ bone.head
            offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
            rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg), 4, "Y")
            bone.matrix = self.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

        if right_bone and right_bone in self.armature.pose.bones:
            bone = self.armature.pose.bones[right_bone]
            current_world_matrix = self.armature.matrix_world @ bone.matrix
            head_world_transformed = self.armature.matrix_world @ bone.head
            offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
            rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg * -1), 4, "Y")
            bone.matrix = self.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.objects.active = self.target_obj
        bpy.context.view_layer.update()

        target_group = self.target_obj.vertex_groups.get(group_name)
        if target_group and base_humanoid_weights:
            print("  ウェイト合成処理開始")
            for vert in self.target_obj.data.vertices:
                vert_idx = vert.index
                target_weight = 0.0
                for g in vert.groups:
                    if g.group == target_group.index:
                        target_weight = g.weight
                        break
                current_factor = target_weight
                base_factor = 1.0 - target_weight
                for group_name in self.bone_groups:
                    if group_name in self.target_obj.vertex_groups:
                        group = self.target_obj.vertex_groups[group_name]
                        current_weight = 0.0
                        for g in vert.groups:
                            if g.group == group.index:
                                current_weight = g.weight
                                break
                        base_weight = 0.0
                        if vert_idx in base_humanoid_weights and group_name in base_humanoid_weights[vert_idx]:
                            base_weight = base_humanoid_weights[vert_idx][group_name]
                        blended_weight = current_weight * current_factor + base_weight * base_factor
                        if blended_weight > 0.0001:
                            group.add([vert_idx], blended_weight, "REPLACE")
                            base_humanoid_weights[vert_idx][group_name] = blended_weight
                        else:
                            try:
                                group.remove([vert_idx])
                                base_humanoid_weights[vert_idx][group_name] = 0.0
                            except RuntimeError:
                                pass
            print("  ウェイト合成処理完了")

    def run_armpit_process(self):
        self._process_mf_group("MF_Armpit", "WT_shape_forA.MFTemp", 45, "LeftUpperArm", "RightUpperArm")

    def run_crotch_process(self):
        self._process_mf_group("MF_crotch", "WT_shape_forCrotch.MFTemp", 70, "LeftUpperLeg", "RightUpperLeg")

    def smooth_and_cleanup(self):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action="DESELECT")
        inpaint_mask_group = self.target_obj.vertex_groups.get("InpaintMask")
        if inpaint_mask_group:
            for vert in self.target_obj.data.vertices:
                for g in vert.groups:
                    if g.group == inpaint_mask_group.index and g.weight >= 0.5:
                        vert.select = True
                        break

        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
        bpy.context.object.data.use_paint_mask = False
        bpy.context.object.data.use_paint_mask_vertex = True
        for group_name in self.bone_groups:
            if group_name in self.target_obj.vertex_groups:
                self.target_obj.vertex_groups.active = self.target_obj.vertex_groups[group_name]
                bpy.ops.object.vertex_group_smooth(factor=0.5, repeat=3, expand=0.0)
        bpy.ops.object.mode_set(mode="OBJECT")

        cleanup_weights_time_start = time.time()
        for vert in self.target_obj.data.vertices:
            groups_to_remove = []
            for g in vert.groups:
                group_name = self.target_obj.vertex_groups[g.group].name
                if group_name in self.bone_groups and g.weight < 0.001:
                    groups_to_remove.append(g.group)
            for group_idx in groups_to_remove:
                try:
                    self.target_obj.vertex_groups[group_idx].remove([vert.index])
                except RuntimeError:
                    continue
        cleanup_weights_time = time.time() - cleanup_weights_time_start
        print(f"  微小ウェイト除外: {cleanup_weights_time:.2f}秒")

    def compute_non_humanoid_masks(self):
        compute_non_humanoid_masks(self)

    def merge_added_groups(self):
        merge_added_groups(self)

    def store_intermediate_results(self):
        store_result_a_time_start = time.time()
        for vert_idx in range(len(self.target_obj.data.vertices)):
            self.weights_a[vert_idx] = {}
            for group in self.target_obj.vertex_groups:
                if group.name in self.bone_groups:
                    try:
                        weight = 0.0
                        for g in self.target_obj.data.vertices[vert_idx].groups:
                            if g.group == group.index:
                                weight = g.weight
                                break
                        self.weights_a[vert_idx][group.name] = weight
                    except Exception:
                        continue
        store_result_a_time = time.time() - store_result_a_time_start
        print(f"  結果A保存: {store_result_a_time:.2f}秒")

        store_result_b_time_start = time.time()
        for vert_idx in range(len(self.target_obj.data.vertices)):
            self.weights_b[vert_idx] = {}
            for group in self.target_obj.vertex_groups:
                if group.name in self.bone_groups:
                    try:
                        weight = 0.0
                        for g in self.target_obj.data.vertices[vert_idx].groups:
                            if g.group == group.index:
                                weight = g.weight
                                break
                        self.weights_b[vert_idx][group.name] = weight
                    except Exception:
                        continue
        store_result_b_time = time.time() - store_result_b_time_start
        print(f"  結果B保存: {store_result_b_time:.2f}秒")

        sway_bones_time_start = time.time()
        for sway_bone in self.base_avatar_data.get("swayBones", []):
            parent_bone = sway_bone["parentBoneName"]
            for affected_bone in sway_bone["affectedBones"]:
                for vert_idx in self.weights_b:
                    if affected_bone in self.weights_b[vert_idx]:
                        affected_weight = self.weights_b[vert_idx][affected_bone]
                        if parent_bone not in self.weights_b[vert_idx]:
                            self.weights_b[vert_idx][parent_bone] = 0.0
                        self.weights_b[vert_idx][parent_bone] += affected_weight
                        del self.weights_b[vert_idx][affected_bone]
        sway_bones_time = time.time() - sway_bones_time_start
        print(f"  SwayBones処理: {sway_bones_time:.2f}秒")

    def blend_results(self):
        weight_blend_time_start = time.time()
        for vert_idx in range(len(self.target_obj.data.vertices)):
            falloff_weight = 0.0
            for g in self.target_obj.data.vertices[vert_idx].groups:
                if g.group == self.distance_falloff_group.index:
                    falloff_weight = g.weight
                    break
            for group_name in self.bone_groups:
                if group_name in self.target_obj.vertex_groups:
                    weight_a = self.weights_a[vert_idx].get(group_name, 0.0)
                    weight_b = self.weights_b[vert_idx].get(group_name, 0.0)
                    final_weight = (weight_a * falloff_weight) + (weight_b * (1.0 - falloff_weight))
                    group = self.target_obj.vertex_groups[group_name]
                    if final_weight > 0:
                        group.add([vert_idx], final_weight, "REPLACE")
                    else:
                        try:
                            group.remove([vert_idx])
                        except RuntimeError:
                            pass
        weight_blend_time = time.time() - weight_blend_time_start
        print(f"  ウェイト合成: {weight_blend_time:.2f}秒")

    def adjust_hands_and_propagate(self):
        hand_weights_time_start = time.time()
        adjust_hand_weights(self.target_obj, self.armature, self.base_avatar_data)
        hand_weights_time = time.time() - hand_weights_time_start
        print(f"  手のウェイト調整: {hand_weights_time:.2f}秒")

        propagate_time_start = time.time()
        self._propagate_weights_to_side_vertices()
        propagate_time = time.time() - propagate_time_start
        print(f"  側面頂点へのウェイト伝播: {propagate_time:.2f}秒")

    def compare_side_and_bone_weights(self):
        comparison_time_start = time.time()
        side_left_group = self.target_obj.vertex_groups.get("LeftSideWeights")
        side_right_group = self.target_obj.vertex_groups.get("RightSideWeights")
        failed_vertices_count = 0
        if side_left_group and side_right_group:
            for vert in self.target_obj.data.vertices:
                total_side_weight = 0.0
                for g in vert.groups:
                    if g.group == side_left_group.index or g.group == side_right_group.index:
                        total_side_weight += g.weight
                total_side_weight = min(total_side_weight, 1.0)
                total_side_weight = total_side_weight - self.non_humanoid_total_weights[vert.index]
                total_side_weight = max(total_side_weight, 0.0)

                total_bone_weight = 0.0
                for g in vert.groups:
                    group_name = self.target_obj.vertex_groups[g.group].name
                    if group_name in self.bone_groups:
                        total_bone_weight += g.weight

                if total_side_weight > total_bone_weight + 0.5:
                    for group in self.target_obj.vertex_groups:
                        if group.name in self.bone_groups:
                            try:
                                group.remove([vert.index])
                            except RuntimeError:
                                continue
                    if vert.index in self.original_humanoid_weights:
                        for group_name, weight in self.original_humanoid_weights[vert.index].items():
                            if group_name in self.target_obj.vertex_groups:
                                self.target_obj.vertex_groups[group_name].add([vert.index], weight, "REPLACE")
                    failed_vertices_count += 1
        if failed_vertices_count > 0:
            print(f"  ウェイト転送失敗: {failed_vertices_count}頂点 -> オリジナルウェイトにフォールバック")
        comparison_time = time.time() - comparison_time_start
        print(f"  サイドウェイト比較調整: {comparison_time:.2f}秒")

    def run_distance_normal_smoothing(self):
        smoothing_time_start = time.time()
        target_vertex_groups = []
        smoothing_mask_groups = []
        target_humanoid_bones = [
            "Chest",
            "LeftBreast",
            "RightBreast",
            "Neck",
            "Head",
            "LeftShoulder",
            "RightShoulder",
            "LeftUpperArm",
            "RightUpperArm",
            "LeftHand",
            "LeftThumbProximal",
            "LeftThumbIntermediate",
            "LeftThumbDistal",
            "LeftIndexProximal",
            "LeftIndexIntermediate",
            "LeftIndexDistal",
            "LeftMiddleProximal",
            "LeftMiddleIntermediate",
            "LeftMiddleDistal",
            "LeftRingProximal",
            "LeftRingIntermediate",
            "LeftRingDistal",
            "LeftLittleProximal",
            "LeftLittleIntermediate",
            "LeftLittleDistal",
            "RightHand",
            "RightThumbProximal",
            "RightThumbIntermediate",
            "RightThumbDistal",
            "RightIndexProximal",
            "RightIndexIntermediate",
            "RightIndexDistal",
            "RightMiddleProximal",
            "RightMiddleIntermediate",
            "RightMiddleDistal",
            "RightRingProximal",
            "RightRingIntermediate",
            "RightRingDistal",
            "RightLittleProximal",
            "RightLittleIntermediate",
            "RightLittleDistal",
        ]
        smoothing_mask_humanoid_bones = [
            "Chest",
            "LeftBreast",
            "RightBreast",
            "Neck",
            "Head",
            "LeftShoulder",
            "RightShoulder",
            "LeftHand",
            "LeftThumbProximal",
            "LeftThumbIntermediate",
            "LeftThumbDistal",
            "LeftIndexProximal",
            "LeftIndexIntermediate",
            "LeftIndexDistal",
            "LeftMiddleProximal",
            "LeftMiddleIntermediate",
            "LeftMiddleDistal",
            "LeftRingProximal",
            "LeftRingIntermediate",
            "LeftRingDistal",
            "LeftLittleProximal",
            "LeftLittleIntermediate",
            "LeftLittleDistal",
            "RightHand",
            "RightThumbProximal",
            "RightThumbIntermediate",
            "RightThumbDistal",
            "RightIndexProximal",
            "RightIndexIntermediate",
            "RightIndexDistal",
            "RightMiddleProximal",
            "RightMiddleIntermediate",
            "RightMiddleDistal",
            "RightRingProximal",
            "RightRingIntermediate",
            "RightRingDistal",
            "RightLittleProximal",
            "RightLittleIntermediate",
            "RightLittleDistal",
        ]
        humanoid_to_bone = {bone_map["humanoidBoneName"]: bone_map["boneName"] for bone_map in self.base_avatar_data["humanoidBones"]}
        for humanoid_bone in target_humanoid_bones:
            if humanoid_bone in humanoid_to_bone:
                target_vertex_groups.append(humanoid_to_bone[humanoid_bone])
        for aux_set in self.base_avatar_data.get("auxiliaryBones", []):
            if aux_set["humanoidBoneName"] in target_humanoid_bones:
                target_vertex_groups.extend(aux_set["auxiliaryBones"])
        for humanoid_bone in smoothing_mask_humanoid_bones:
            if humanoid_bone in humanoid_to_bone:
                smoothing_mask_groups.append(humanoid_to_bone[humanoid_bone])
        for aux_set in self.base_avatar_data.get("auxiliaryBones", []):
            if aux_set["humanoidBoneName"] in smoothing_mask_humanoid_bones:
                smoothing_mask_groups.extend(aux_set["auxiliaryBones"])

        body_obj = bpy.data.objects.get("Body.BaseAvatar")
        breast_bone_groups = []
        breast_humanoid_bones = ["Hips", "LeftBreast", "RightBreast", "Neck", "Head", "LeftHand", "RightHand"]
        for humanoid_bone in breast_humanoid_bones:
            if humanoid_bone in humanoid_to_bone:
                breast_bone_groups.append(humanoid_to_bone[humanoid_bone])
        for aux_set in self.base_avatar_data.get("auxiliaryBones", []):
            if aux_set["humanoidBoneName"] in breast_humanoid_bones:
                breast_bone_groups.extend(aux_set["auxiliaryBones"])

        has_breast_weights = False
        if breast_bone_groups:
            for group_name in breast_bone_groups:
                if group_name in self.target_obj.vertex_groups:
                    group = self.target_obj.vertex_groups[group_name]
                    for vert in self.target_obj.data.vertices:
                        try:
                            weight = 0.0
                            for g in vert.groups:
                                if g.group == group.index:
                                    weight = g.weight
                                    break
                            if weight > 0:
                                has_breast_weights = True
                                break
                        except RuntimeError:
                            continue
                    if has_breast_weights:
                        break

        if body_obj and target_vertex_groups and has_breast_weights:
            print(f"  距離・法線ベースのスムージングを実行: {len(target_vertex_groups)}個のターゲットグループ (LeftBreast/RightBreastウェイト検出)")
            apply_distance_normal_based_smoothing(
                body_obj=body_obj,
                cloth_obj=self.target_obj,
                distance_min=0.005,
                distance_max=0.015,
                angle_min=15.0,
                angle_max=30.0,
                new_group_name="SmoothMask",
                normal_radius=0.01,
                smoothing_mask_groups=smoothing_mask_groups,
                target_vertex_groups=target_vertex_groups,
                smoothing_radius=0.05,
                mask_group_name="MF_Blur",
            )
        else:
            print("  Body.BaseAvatarオブジェクトが見つからないか、ターゲットグループが空です")

        smoothing_time = time.time() - smoothing_time_start
        print(f"  距離・法線ベースのスムージング: {smoothing_time:.2f}秒")

    def apply_distance_falloff_blend(self):
        current_mode = bpy.context.object.mode
        bpy.context.view_layer.objects.active = self.target_obj
        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
        self.target_obj.vertex_groups.active_index = self.distance_falloff_group2.index
        print(f"  distance_falloff_group2: {self.distance_falloff_group2.index}")
        print(f"  distance_falloff_group2_index: {self.target_obj.vertex_groups[self.distance_falloff_group2.name].index}")

        humanoid_to_bone = {bone_map["humanoidBoneName"]: bone_map["boneName"] for bone_map in self.base_avatar_data["humanoidBones"]}
        exclude_bone_groups = []
        exclude_humanoid_bones = ["LeftBreast", "RightBreast"]
        for humanoid_bone in exclude_humanoid_bones:
            if humanoid_bone in humanoid_to_bone:
                exclude_bone_groups.append(humanoid_to_bone[humanoid_bone])
        for aux_set in self.base_avatar_data.get("auxiliaryBones", []):
            if aux_set["humanoidBoneName"] in exclude_humanoid_bones:
                exclude_bone_groups.extend(aux_set["auxiliaryBones"])

        if exclude_bone_groups:
            new_group_weights = np.zeros(len(self.target_obj.data.vertices), dtype=np.float32)
            for i, vertex in enumerate(self.target_obj.data.vertices):
                for group in vertex.groups:
                    if group.group == self.distance_falloff_group2.index:
                        new_group_weights[i] = group.weight
                        break
            total_target_weights = np.zeros(len(self.target_obj.data.vertices), dtype=np.float32)
            for target_group_name in exclude_bone_groups:
                if target_group_name in self.target_obj.vertex_groups:
                    target_group = self.target_obj.vertex_groups[target_group_name]
                    print(f"    頂点グループ '{target_group_name}' のウェイトを取得中...")
                    for i, vertex in enumerate(self.target_obj.data.vertices):
                        for group in vertex.groups:
                            if group.group == target_group.index:
                                total_target_weights[i] += group.weight
                                break
                else:
                    print(f"    警告: 頂点グループ '{target_group_name}' が見つかりません")
            masked_weights = np.maximum(new_group_weights, total_target_weights)
            for i in range(len(self.target_obj.data.vertices)):
                self.distance_falloff_group2.add([i], masked_weights[i], "REPLACE")

        for vert_idx in range(len(self.target_obj.data.vertices)):
            if vert_idx in self.original_humanoid_weights and self.non_humanoid_parts_mask[vert_idx] < 0.0001:
                falloff_weight = 0.0
                for g in self.target_obj.data.vertices[vert_idx].groups:
                    if g.group == self.distance_falloff_group2.index:
                        falloff_weight = g.weight
                        break
                for g in self.target_obj.data.vertices[vert_idx].groups:
                    if self.target_obj.vertex_groups[g.group].name in self.bone_groups:
                        weight = g.weight
                        group_name = self.target_obj.vertex_groups[g.group].name
                        self.target_obj.vertex_groups[group_name].add([vert_idx], weight * falloff_weight, "REPLACE")
                for group_name, weight in self.original_humanoid_weights[vert_idx].items():
                    if group_name in self.target_obj.vertex_groups:
                        self.target_obj.vertex_groups[group_name].add([vert_idx], weight * (1.0 - falloff_weight), "ADD")

        bpy.ops.object.mode_set(mode=current_mode)

    def restore_head_weights(self):
        head_time_start = time.time()
        head_bone_name = None
        if self.base_avatar_data and "humanoidBones" in self.base_avatar_data:
            for bone_data in self.base_avatar_data["humanoidBones"]:
                if bone_data.get("humanoidBoneName", "") == "Head":
                    head_bone_name = bone_data.get("boneName", "")
                    break

        if head_bone_name and head_bone_name in self.target_obj.vertex_groups:
            print(f"  Headボーンウェイトを処理中: {head_bone_name}")
            head_vertices_count = 0
            for vert_idx in range(len(self.target_obj.data.vertices)):
                original_head_weight = 0.0
                if vert_idx in self.original_humanoid_weights:
                    original_head_weight = self.original_humanoid_weights[vert_idx].get(head_bone_name, 0.0)
                current_head_weight = 0.0
                for g in self.target_obj.data.vertices[vert_idx].groups:
                    if g.group == self.target_obj.vertex_groups[head_bone_name].index:
                        current_head_weight = g.weight
                        break
                head_weight_diff = original_head_weight - current_head_weight
                if original_head_weight > 0.0:
                    self.target_obj.vertex_groups[head_bone_name].add([vert_idx], original_head_weight, "REPLACE")
                else:
                    try:
                        self.target_obj.vertex_groups[head_bone_name].remove([vert_idx])
                    except RuntimeError:
                        pass
                if abs(head_weight_diff) > 0.0001 and vert_idx in self.original_humanoid_weights:
                    for group in self.target_obj.vertex_groups:
                        if group.name in self.bone_groups and group.name != head_bone_name:
                            original_weight = self.original_humanoid_weights[vert_idx].get(group.name, 0.0)
                            if original_weight > 0.0:
                                current_weight = 0.0
                                for g in self.target_obj.data.vertices[vert_idx].groups:
                                    if g.group == group.index:
                                        current_weight = g.weight
                                        break
                                new_weight = current_weight + (original_weight * head_weight_diff)
                                if new_weight > 0.0:
                                    group.add([vert_idx], new_weight, "REPLACE")
                                else:
                                    try:
                                        group.remove([vert_idx])
                                    except RuntimeError:
                                        pass

                total_weight = 0.0
                for g in self.target_obj.data.vertices[vert_idx].groups:
                    group_name = self.target_obj.vertex_groups[g.group].name
                    if group_name in self.all_deform_groups:
                        total_weight += g.weight
                if total_weight < 0.9999 and vert_idx in self.original_humanoid_weights:
                    weight_shortage = 1.0 - total_weight
                    for group in self.target_obj.vertex_groups:
                        if group.name in self.bone_groups:
                            original_weight = self.original_humanoid_weights[vert_idx].get(group.name, 0.0)
                            if original_weight > 0.0:
                                current_weight = 0.0
                                for g in self.target_obj.data.vertices[vert_idx].groups:
                                    if g.group == group.index:
                                        current_weight = g.weight
                                        break
                                additional_weight = original_weight * weight_shortage
                                new_weight = current_weight + additional_weight
                                group.add([vert_idx], new_weight, "REPLACE")
                head_vertices_count += 1
            if head_vertices_count > 0:
                print(f"  Headウェイト処理完了: {head_vertices_count}頂点")
        head_time = time.time() - head_time_start
        print(f"  Headウェイト処理: {head_time:.2f}秒")

    def apply_metadata_fallback(self):
        metadata_time_start = time.time()
        if self.cloth_metadata:
            mesh_name = self.target_obj.name
            if mesh_name in self.cloth_metadata:
                vertex_max_distances = self.cloth_metadata[mesh_name]
                print(f"  メッシュのクロスメタデータを処理: {mesh_name}")
                count = 0
                for vert_idx in range(len(self.target_obj.data.vertices)):
                    max_distance = float(vertex_max_distances.get(str(vert_idx), 10.0))
                    if max_distance > 1.0:
                        if vert_idx in self.original_humanoid_weights:
                            for group in self.target_obj.vertex_groups:
                                if group.name in self.bone_groups:
                                    try:
                                        group.remove([vert_idx])
                                    except RuntimeError:
                                        continue
                            for group_name, weight in self.original_humanoid_weights[vert_idx].items():
                                if group_name in self.target_obj.vertex_groups:
                                    self.target_obj.vertex_groups[group_name].add([vert_idx], weight, "REPLACE")
                            count += 1
                print(f"  処理された頂点数: {count}")
        metadata_time = time.time() - metadata_time_start
        print(f"  クロスメタデータ処理: {metadata_time:.2f}秒")

    def run(self):
        print(f"処理開始: {self.target_obj.name}")
        self._build_bone_maps()
        self.detect_finger_vertices()
        self.create_closing_filter_mask()
        self.prepare_groups_and_weights()
        if not self.transfer_side_weights():
            return
        self.run_armpit_process()
        self.run_crotch_process()
        self.smooth_and_cleanup()
        self.compute_non_humanoid_masks()
        self.merge_added_groups()
        self.store_intermediate_results()
        self.blend_results()
        self.adjust_hands_and_propagate()
        self.compare_side_and_bone_weights()
        self.run_distance_normal_smoothing()
        self.apply_distance_falloff_blend()
        self.restore_head_weights()
        self.apply_metadata_fallback()
        total_time = time.time() - self.start_time
        print(f"処理完了: {self.target_obj.name} - 合計時間: {total_time:.2f}秒")


def process_weight_transfer(target_obj, armature, base_avatar_data, clothing_avatar_data, field_path, clothing_armature, cloth_metadata=None):
    """Orchestrator that delegates weight transfer to a stateful context."""
    context = WeightTransferContext(
        target_obj=target_obj,
        armature=armature,
        base_avatar_data=base_avatar_data,
        clothing_avatar_data=clothing_avatar_data,
        field_path=field_path,
        clothing_armature=clothing_armature,
        cloth_metadata=cloth_metadata,
    )
    context.run()
