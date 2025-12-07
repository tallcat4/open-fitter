import os
import sys

# Add the parent directory (extracted/) to sys.path to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import bpy
from apply_distance_normal_based_smoothing import apply_distance_normal_based_smoothing

def run_distance_normal_smoothing(context):
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
    humanoid_to_bone = {bone_map["humanoidBoneName"]: bone_map["boneName"] for bone_map in context.base_avatar_data["humanoidBones"]}
    for humanoid_bone in target_humanoid_bones:
        if humanoid_bone in humanoid_to_bone:
            target_vertex_groups.append(humanoid_to_bone[humanoid_bone])
    for aux_set in context.base_avatar_data.get("auxiliaryBones", []):
        if aux_set["humanoidBoneName"] in target_humanoid_bones:
            target_vertex_groups.extend(aux_set["auxiliaryBones"])
    for humanoid_bone in smoothing_mask_humanoid_bones:
        if humanoid_bone in humanoid_to_bone:
            smoothing_mask_groups.append(humanoid_to_bone[humanoid_bone])
    for aux_set in context.base_avatar_data.get("auxiliaryBones", []):
        if aux_set["humanoidBoneName"] in smoothing_mask_humanoid_bones:
            smoothing_mask_groups.extend(aux_set["auxiliaryBones"])

    body_obj = bpy.data.objects.get("Body.BaseAvatar")
    breast_bone_groups = []
    breast_humanoid_bones = ["Hips", "LeftBreast", "RightBreast", "Neck", "Head", "LeftHand", "RightHand"]
    for humanoid_bone in breast_humanoid_bones:
        if humanoid_bone in humanoid_to_bone:
            breast_bone_groups.append(humanoid_to_bone[humanoid_bone])
    for aux_set in context.base_avatar_data.get("auxiliaryBones", []):
        if aux_set["humanoidBoneName"] in breast_humanoid_bones:
            breast_bone_groups.extend(aux_set["auxiliaryBones"])

    has_breast_weights = False
    if breast_bone_groups:
        for group_name in breast_bone_groups:
            if group_name in context.target_obj.vertex_groups:
                group = context.target_obj.vertex_groups[group_name]
                for vert in context.target_obj.data.vertices:
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
            cloth_obj=context.target_obj,
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
