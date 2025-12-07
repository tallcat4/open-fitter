import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
from blender_utils.apply_modifiers_keep_shapekeys_with_temp import (
    apply_modifiers_keep_shapekeys_with_temp,
)
from blender_utils.armature_modifier_utils import (
    restore_armature_modifier,
    set_armature_modifier_visibility,
    store_armature_modifier_settings,
)
from blender_utils.is_left_side_bone import is_left_side_bone
from blender_utils.is_right_side_bone import is_right_side_bone


def duplicate_mesh_with_partial_weights(base_mesh: bpy.types.Object, base_avatar_data: dict) -> tuple:
    """
    素体メッシュを複製し左右の半身ウェイトを分離したものを作成
    Returns: (右半身のみのメッシュ, 左半身のメッシュ)
    """
    # 左右のボーンを分類
    left_bones, right_bones = set(), set()
    
    # 左右で別のグループにする脚・足・足指・胸のボーン
    leg_foot_chest_bones = {
        "LeftUpperLeg", "RightUpperLeg", "LeftLowerLeg", "RightLowerLeg",
        "LeftFoot", "RightFoot", "LeftToes", "RightToes", "LeftBreast", "RightBreast",
        "LeftFootThumbProximal", "LeftFootThumbIntermediate", "LeftFootThumbDistal",
        "LeftFootIndexProximal", "LeftFootIndexIntermediate", "LeftFootIndexDistal",
        "LeftFootMiddleProximal", "LeftFootMiddleIntermediate", "LeftFootMiddleDistal",
        "LeftFootRingProximal", "LeftFootRingIntermediate", "LeftFootRingDistal",
        "LeftFootLittleProximal", "LeftFootLittleIntermediate", "LeftFootLittleDistal",
        "RightFootThumbProximal", "RightFootThumbIntermediate", "RightFootThumbDistal",
        "RightFootIndexProximal", "RightFootIndexIntermediate", "RightFootIndexDistal",
        "RightFootMiddleProximal", "RightFootMiddleIntermediate", "RightFootMiddleDistal",
        "RightFootRingProximal", "RightFootRingIntermediate", "RightFootRingDistal",
        "RightFootLittleProximal", "RightFootLittleIntermediate", "RightFootLittleDistal"
    }
    
    # 右側グループに入れる指ボーン
    right_group_fingers = {
        "LeftThumbProximal", "LeftThumbIntermediate", "LeftThumbDistal",
        "LeftMiddleProximal", "LeftMiddleIntermediate", "LeftMiddleDistal",
        "LeftLittleProximal", "LeftLittleIntermediate", "LeftLittleDistal",
        "RightThumbProximal", "RightThumbIntermediate", "RightThumbDistal",
        "RightMiddleProximal", "RightMiddleIntermediate", "RightMiddleDistal",
        "RightLittleProximal", "RightLittleIntermediate", "RightLittleDistal"
    }
    
    # 左側グループに入れる指ボーン
    left_group_fingers = {
        "LeftIndexProximal", "LeftIndexIntermediate", "LeftIndexDistal",
        "LeftRingProximal", "LeftRingIntermediate", "LeftRingDistal",
        "RightIndexProximal", "RightIndexIntermediate", "RightIndexDistal",
        "RightRingProximal", "RightRingIntermediate", "RightRingDistal"
    }
    
    # 分離しない肩・腕・手のボーン
    excluded_bones = {
        "LeftShoulder", "RightShoulder", "LeftUpperArm", "RightUpperArm",
        "LeftLowerArm", "RightLowerArm", "LeftHand", "RightHand"
    }
   
    for bone_map in base_avatar_data.get("humanoidBones", []):
        bone_name = bone_map["boneName"]
        humanoid_name = bone_map["humanoidBoneName"]
       
        if humanoid_name in excluded_bones:
            # 分離しない
            continue
        elif humanoid_name in leg_foot_chest_bones:
            # 脚・足・足指・胸は従来通り左右で分ける
            if any(k in humanoid_name for k in ["Left", "left"]):
                left_bones.add(bone_name)
            elif any(k in humanoid_name for k in ["Right", "right"]):
                right_bones.add(bone_name)
        elif humanoid_name in right_group_fingers:
            # 右側グループに入れる指ボーン
            right_bones.add(bone_name)
        elif humanoid_name in left_group_fingers:
            # 左側グループに入れる指ボーン
            left_bones.add(bone_name)
   
    for aux_set in base_avatar_data.get("auxiliaryBones", []):
        humanoid_name = aux_set["humanoidBoneName"]
        for aux_bone in aux_set["auxiliaryBones"]:
            if humanoid_name in excluded_bones:
                # 分離しない
                continue
            elif humanoid_name in leg_foot_chest_bones:
                # 脚・足・足指・胸は従来通り左右で分ける
                if is_left_side_bone(aux_bone, humanoid_name):
                    left_bones.add(aux_bone)
                elif is_right_side_bone(aux_bone, humanoid_name):
                    right_bones.add(aux_bone)
            elif humanoid_name in right_group_fingers:
                # 右側グループに入れる指ボーン
                right_bones.add(aux_bone)
            elif humanoid_name in left_group_fingers:
                # 左側グループに入れる指ボーン
                left_bones.add(aux_bone)

    # メッシュを複製 (通常版)
    right_mesh = base_mesh.copy()
    right_mesh.data = base_mesh.data.copy()
    right_mesh.name = base_mesh.name + ".RightOnly"
    bpy.context.scene.collection.objects.link(right_mesh)
   
    left_mesh = base_mesh.copy()
    left_mesh.data = base_mesh.data.copy()
    left_mesh.name = base_mesh.name + ".LeftOnly" 
    bpy.context.scene.collection.objects.link(left_mesh)

    left_base_mesh_armature_settings = store_armature_modifier_settings(left_mesh)
    right_base_mesh_armature_settings = store_armature_modifier_settings(right_mesh)
    apply_modifiers_keep_shapekeys_with_temp(left_mesh)
    apply_modifiers_keep_shapekeys_with_temp(right_mesh)
    restore_armature_modifier(left_mesh, left_base_mesh_armature_settings)
    restore_armature_modifier(right_mesh, right_base_mesh_armature_settings)
    set_armature_modifier_visibility(left_mesh, False, False)
    set_armature_modifier_visibility(right_mesh, False, False)

    print(f"left_bones: {left_bones}")
    print(f"right_bones: {right_bones}")
   
    # 通常版の処理
    # 左右の頂点グループを削除
    for bone_name in left_bones:
        if bone_name in right_mesh.vertex_groups:
            right_mesh.vertex_groups.remove(right_mesh.vertex_groups[bone_name])
           
    for bone_name in right_bones:
        if bone_name in left_mesh.vertex_groups:
            left_mesh.vertex_groups.remove(left_mesh.vertex_groups[bone_name])

    return right_mesh, left_mesh
