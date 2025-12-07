import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import math

import bpy
import mathutils
import numpy as np
from blender_utils.apply_modifiers_keep_shapekeys_with_temp import (
    apply_modifiers_keep_shapekeys_with_temp,
)
from blender_utils.armature_modifier_utils import set_armature_modifier_visibility
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state


def generate_temp_shapekeys_for_weight_transfer(obj: bpy.types.Object, armature_obj: bpy.types.Object, avatar_data: dict, is_A_pose: bool) -> None:
    """
    Generate temp shapekeys for weight transfer.
    """
    if obj.type != 'MESH':
        return

    set_armature_modifier_visibility(obj, True, True)

    for sk in obj.data.shape_keys.key_blocks:
        if sk.name != "Basis":
            if sk.name == "SymmetricDeformed":
                sk.value = 1.0
            else:
                sk.value = 0.0

    A_pose_shape_verts = None
    crotch_shape_verts = None

    original_shape_key_state = save_shape_key_state(obj)
    
    if is_A_pose:
        restore_shape_key_state(obj, original_shape_key_state)

        # 左右の腕全体のボーンにY軸回転を適用
        print("  左右の腕全体のボーンにY軸回転を適用")
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='POSE')
        
        # humanoidBonesから左右の腕全体のboneNameを取得
        left_arm_humanoid_names = [
            "LeftUpperArm", "LeftLowerArm", "LeftHand",
            "LeftThumbProximal", "LeftThumbIntermediate", "LeftThumbDistal",
            "LeftIndexProximal", "LeftIndexIntermediate", "LeftIndexDistal",
            "LeftMiddleProximal", "LeftMiddleIntermediate", "LeftMiddleDistal",
            "LeftRingProximal", "LeftRingIntermediate", "LeftRingDistal",
            "LeftLittleProximal", "LeftLittleIntermediate", "LeftLittleDistal"
        ]
        
        right_arm_humanoid_names = [
            "RightUpperArm", "RightLowerArm", "RightHand",
            "RightThumbProximal", "RightThumbIntermediate", "RightThumbDistal",
            "RightIndexProximal", "RightIndexIntermediate", "RightIndexDistal",
            "RightMiddleProximal", "RightMiddleIntermediate", "RightMiddleDistal",
            "RightRingProximal", "RightRingIntermediate", "RightRingDistal",
            "RightLittleProximal", "RightLittleIntermediate", "RightLittleDistal"
        ]
        
        left_arm_bones = []
        right_arm_bones = []
        left_upper_arm_bone = None
        right_upper_arm_bone = None
        
        # ヒューマノイドボーンを取得
        for bone_map in avatar_data.get("humanoidBones", []):
            humanoid_name = bone_map.get("humanoidBoneName")
            bone_name = bone_map.get("boneName")
            if humanoid_name == "LeftUpperArm":
                left_upper_arm_bone = bone_name
            elif humanoid_name == "RightUpperArm":
                right_upper_arm_bone = bone_name
            
            if humanoid_name in left_arm_humanoid_names:
                left_arm_bones.append(bone_name)
            elif humanoid_name in right_arm_humanoid_names:
                right_arm_bones.append(bone_name)
        
        # LeftUpperArmのheadを起点として取得
        left_pivot_point = None
        if left_upper_arm_bone and left_upper_arm_bone in armature_obj.pose.bones:
            left_pivot_point = armature_obj.matrix_world @ armature_obj.pose.bones[left_upper_arm_bone].head
        
        # RightUpperArmのheadを起点として取得
        right_pivot_point = None
        if right_upper_arm_bone and right_upper_arm_bone in armature_obj.pose.bones:
            right_pivot_point = armature_obj.matrix_world @ armature_obj.pose.bones[right_upper_arm_bone].head
        
        # 左腕全体に-45度のY軸回転を適用（LeftUpperArmのheadを起点）
        if left_pivot_point:
            for bone_name in left_arm_bones:
                if bone_name and bone_name in armature_obj.pose.bones:
                    bone = armature_obj.pose.bones[bone_name]
                    current_world_matrix = armature_obj.matrix_world @ bone.matrix
                    # グローバル座標系での-45度Y軸回転を適用（LeftUpperArmのheadを起点）
                    offset_matrix = mathutils.Matrix.Translation(left_pivot_point * -1.0)
                    rotation_matrix = mathutils.Matrix.Rotation(math.radians(-45), 4, 'Y')
                    bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
        
        # 右腕全体に45度のY軸回転を適用（RightUpperArmのheadを起点）
        if right_pivot_point:
            for bone_name in right_arm_bones:
                if bone_name and bone_name in armature_obj.pose.bones:
                    bone = armature_obj.pose.bones[bone_name]
                    current_world_matrix = armature_obj.matrix_world @ bone.matrix
                    # グローバル座標系での45度Y軸回転を適用（RightUpperArmのheadを起点）
                    offset_matrix = mathutils.Matrix.Translation(right_pivot_point * -1.0)
                    rotation_matrix = mathutils.Matrix.Rotation(math.radians(45), 4, 'Y')
                    bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
        
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active = obj
        bpy.context.view_layer.update()

        #現在の評価済みメッシュを取得、アーマチュア変形後の状態を保存
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        A_pose_shape_verts = np.array([v.co.copy() for v in eval_mesh.vertices])

        # 左腕全体に45度のY軸回転を適用(戻す)（LeftUpperArmのheadを起点）
        if left_pivot_point:
            for bone_name in left_arm_bones:
                if bone_name and bone_name in armature_obj.pose.bones:
                    bone = armature_obj.pose.bones[bone_name]
                    current_world_matrix = armature_obj.matrix_world @ bone.matrix
                    # グローバル座標系での45度Y軸回転を適用（LeftUpperArmのheadを起点）
                    offset_matrix = mathutils.Matrix.Translation(left_pivot_point * -1.0)
                    rotation_matrix = mathutils.Matrix.Rotation(math.radians(45), 4, 'Y')
                    bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
        
        # 右腕全体に-45度のY軸回転を適用(戻す)（RightUpperArmのheadを起点）
        if right_pivot_point:
            for bone_name in right_arm_bones:
                if bone_name and bone_name in armature_obj.pose.bones:
                    bone = armature_obj.pose.bones[bone_name]
                    current_world_matrix = armature_obj.matrix_world @ bone.matrix
                    # グローバル座標系での-45度Y軸回転を適用（RightUpperArmのheadを起点）
                    offset_matrix = mathutils.Matrix.Translation(right_pivot_point * -1.0)
                    rotation_matrix = mathutils.Matrix.Rotation(math.radians(-45), 4, 'Y')
                    bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
    
    restore_shape_key_state(obj, original_shape_key_state)

    # 左右の足全体のボーンにY軸回転を適用
    print("  左右の足全体のボーンにY軸回転を適用")
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')
    
    # humanoidBonesから左右の足全体のboneNameを取得
    left_leg_humanoid_names = [
        "LeftUpperLeg", "LeftLowerLeg", "LeftFoot"
    ]
    
    right_leg_humanoid_names = [
        "RightUpperLeg", "RightLowerLeg", "RightFoot"
    ]
    
    left_leg_bones = []
    right_leg_bones = []
    left_upper_leg_bone = None
    right_upper_leg_bone = None
    
    # ヒューマノイドボーンを取得
    for bone_map in avatar_data.get("humanoidBones", []):
        humanoid_name = bone_map.get("humanoidBoneName")
        bone_name = bone_map.get("boneName")
        if humanoid_name == "LeftUpperLeg":
            left_upper_leg_bone = bone_name
        elif humanoid_name == "RightUpperLeg":
            right_upper_leg_bone = bone_name
        
        if humanoid_name in left_leg_humanoid_names:
            left_leg_bones.append(bone_name)
        elif humanoid_name in right_leg_humanoid_names:
            right_leg_bones.append(bone_name)
    
    # LeftUpperLegのheadを起点として取得
    left_leg_pivot_point = None
    if left_upper_leg_bone and left_upper_leg_bone in armature_obj.pose.bones:
        left_leg_pivot_point = armature_obj.matrix_world @ armature_obj.pose.bones[left_upper_leg_bone].head
    
    # RightUpperLegのheadを起点として取得
    right_leg_pivot_point = None
    if right_upper_leg_bone and right_upper_leg_bone in armature_obj.pose.bones:
        right_leg_pivot_point = armature_obj.matrix_world @ armature_obj.pose.bones[right_upper_leg_bone].head
    
    # 左足全体に-70度のY軸回転を適用（LeftUpperLegのheadを起点）
    if left_leg_pivot_point:
        for bone_name in left_leg_bones:
            if bone_name and bone_name in armature_obj.pose.bones:
                bone = armature_obj.pose.bones[bone_name]
                current_world_matrix = armature_obj.matrix_world @ bone.matrix
                # グローバル座標系での-70度Y軸回転を適用（LeftUpperLegのheadを起点）
                offset_matrix = mathutils.Matrix.Translation(left_leg_pivot_point * -1.0)
                rotation_matrix = mathutils.Matrix.Rotation(math.radians(-70), 4, 'Y')
                bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
    
    # 右足全体に70度のY軸回転を適用（RightUpperLegのheadを起点）
    if right_leg_pivot_point:
        for bone_name in right_leg_bones:
            if bone_name and bone_name in armature_obj.pose.bones:
                bone = armature_obj.pose.bones[bone_name]
                current_world_matrix = armature_obj.matrix_world @ bone.matrix
                # グローバル座標系での70度Y軸回転を適用（RightUpperLegのheadを起点）
                offset_matrix = mathutils.Matrix.Translation(right_leg_pivot_point * -1.0)
                rotation_matrix = mathutils.Matrix.Rotation(math.radians(70), 4, 'Y')
                bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
    
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()

    #現在の評価済みメッシュを取得、アーマチュア変形後の状態を保存
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.data
    crotch_shape_verts = np.array([v.co.copy() for v in eval_mesh.vertices])

    # 左足全体に70度のY軸回転を適用(戻す)（LeftUpperLegのheadを起点）
    if left_leg_pivot_point:
        for bone_name in left_leg_bones:
            if bone_name and bone_name in armature_obj.pose.bones:
                bone = armature_obj.pose.bones[bone_name]
                current_world_matrix = armature_obj.matrix_world @ bone.matrix
                # グローバル座標系での70度Y軸回転を適用（LeftUpperLegのheadを起点）
                offset_matrix = mathutils.Matrix.Translation(left_leg_pivot_point * -1.0)
                rotation_matrix = mathutils.Matrix.Rotation(math.radians(70), 4, 'Y')
                bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix
    
    # 右足全体に-70度のY軸回転を適用(戻す)（RightUpperLegのheadを起点）
    if right_leg_pivot_point:
        for bone_name in right_leg_bones:
            if bone_name and bone_name in armature_obj.pose.bones:
                bone = armature_obj.pose.bones[bone_name]
                current_world_matrix = armature_obj.matrix_world @ bone.matrix
                # グローバル座標系での-70度Y軸回転を適用（RightUpperLegのheadを起点）
                offset_matrix = mathutils.Matrix.Translation(right_leg_pivot_point * -1.0)
                rotation_matrix = mathutils.Matrix.Rotation(math.radians(-70), 4, 'Y')
                bone.matrix = armature_obj.matrix_world.inverted() @ offset_matrix.inverted() @ rotation_matrix @ offset_matrix @ current_world_matrix

    apply_modifiers_keep_shapekeys_with_temp(obj)

    if obj.data.shape_keys is None:
        obj.shape_key_add(name='Basis')
    
    if is_A_pose:
        # 一時シェイプキーを作成
        shape_key_forA = obj.shape_key_add(name="WT_shape_forA.MFTemp")
        shape_key_forA.value = 0.0

        for i in range(len(A_pose_shape_verts)):
            shape_key_forA.data[i].co = A_pose_shape_verts[i]
    
    # 一時シェイプキーを作成
    shape_key_forCrotch = obj.shape_key_add(name="WT_shape_forCrotch.MFTemp")
    shape_key_forCrotch.value = 0.0
    
    for i in range(len(crotch_shape_verts)):
        shape_key_forCrotch.data[i].co = crotch_shape_verts[i]
    
    restore_shape_key_state(obj, original_shape_key_state)
