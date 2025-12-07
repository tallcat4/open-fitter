import os
import sys

# Add the parent directory (extracted/) to sys.path to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math

import bpy
import mathutils
from blender_utils.reset_bone_weights import reset_bone_weights
from io_utils.restore_weights import restore_weights
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state
from io_utils.store_weights import store_weights
from stages.attempt_weight_transfer import attempt_weight_transfer


def process_mf_group(context, group_name, temp_shape_name, rotation_deg, humanoid_label_left, humanoid_label_right):
    target_group = context.target_obj.vertex_groups.get(group_name)
    should_process = False
    if target_group:
        for vert in context.target_obj.data.vertices:
            for g in vert.groups:
                if g.group == target_group.index and g.weight > 0.001:
                    should_process = True
                    break
            if should_process:
                break

    if not should_process:
        print(f"  {group_name}グループが存在しないか、有効なウェイトがないため処理をスキップ")
        return

    if not (context.armature and context.armature.type == "ARMATURE"):
        print(f"  {group_name}グループが存在しないか、アーマチュアが存在しないため処理をスキップ")
        return

    print(f"  {group_name}グループが存在し、有効なウェイトを持つため処理を実行")
    base_humanoid_weights = store_weights(context.target_obj, context.bone_groups)
    reset_bone_weights(context.target_obj, context.bone_groups)
    restore_weights(context.target_obj, context.all_weights)

    print(f"  {humanoid_label_left}と{humanoid_label_right}ボーンにY軸回転を適用")
    bpy.context.view_layer.objects.active = context.armature
    bpy.ops.object.mode_set(mode="POSE")

    left_bone = None
    right_bone = None
    for bone_map in context.base_avatar_data.get("humanoidBones", []):
        if bone_map.get("humanoidBoneName") == humanoid_label_left:
            left_bone = bone_map.get("boneName")
        elif bone_map.get("humanoidBoneName") == humanoid_label_right:
            right_bone = bone_map.get("boneName")

    if left_bone and left_bone in context.armature.pose.bones:
        bone = context.armature.pose.bones[left_bone]
        current_world_matrix = context.armature.matrix_world @ bone.matrix
        head_world_transformed = context.armature.matrix_world @ bone.head
        offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
        rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg * -1), 4, "Y")
        bone.matrix = context.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

    if right_bone and right_bone in context.armature.pose.bones:
        bone = context.armature.pose.bones[right_bone]
        current_world_matrix = context.armature.matrix_world @ bone.matrix
        head_world_transformed = context.armature.matrix_world @ bone.head
        offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
        rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg), 4, "Y")
        bone.matrix = context.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = context.target_obj
    bpy.context.view_layer.update()

    shape_key_state = save_shape_key_state(context.target_obj)
    for key_block in context.target_obj.data.shape_keys.key_blocks:
        key_block.value = 0.0

    if context.target_obj.data.shape_keys and temp_shape_name in context.target_obj.data.shape_keys.key_blocks:
        temp_shape_key = context.target_obj.data.shape_keys.key_blocks[temp_shape_name]
        temp_shape_key.value = 1.0
    else:
        temp_shape_key = None

    reset_bone_weights(context.target_obj, context.bone_groups)
    print("  ウェイト転送開始")
    attempt_weight_transfer(context, bpy.data.objects["Body.BaseAvatar"], "BothSideWeights")

    restore_shape_key_state(context.target_obj, shape_key_state)
    if temp_shape_key:
        temp_shape_key.value = 0.0

    print(f"  {humanoid_label_left}と{humanoid_label_right}ボーンにY軸逆回転を適用")
    bpy.context.view_layer.objects.active = context.armature
    bpy.ops.object.mode_set(mode="POSE")

    if left_bone and left_bone in context.armature.pose.bones:
        bone = context.armature.pose.bones[left_bone]
        current_world_matrix = context.armature.matrix_world @ bone.matrix
        head_world_transformed = context.armature.matrix_world @ bone.head
        offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
        rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg), 4, "Y")
        bone.matrix = context.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

    if right_bone and right_bone in context.armature.pose.bones:
        bone = context.armature.pose.bones[right_bone]
        current_world_matrix = context.armature.matrix_world @ bone.matrix
        head_world_transformed = context.armature.matrix_world @ bone.head
        offset_matrix = mathutils.Matrix.Translation(head_world_transformed * -1.0)
        rotation_matrix = mathutils.Matrix.Rotation(math.radians(rotation_deg * -1), 4, "Y")
        bone.matrix = context.armature.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = context.target_obj
    bpy.context.view_layer.update()

    target_group = context.target_obj.vertex_groups.get(group_name)
    if target_group and base_humanoid_weights:
        print("  ウェイト合成処理開始")
        for vert in context.target_obj.data.vertices:
            vert_idx = vert.index
            target_weight = 0.0
            for g in vert.groups:
                if g.group == target_group.index:
                    target_weight = g.weight
                    break
            current_factor = target_weight
            base_factor = 1.0 - target_weight
            for group_name in context.bone_groups:
                if group_name in context.target_obj.vertex_groups:
                    group = context.target_obj.vertex_groups[group_name]
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
