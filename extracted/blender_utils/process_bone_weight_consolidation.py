import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
from algo_utils.vertex_group_utils import merge_vertex_group_weights
from blender_utils.bone_utils import get_bone_name_from_humanoid


def process_bone_weight_consolidation(mesh_obj: bpy.types.Object, avatar_data: dict) -> None:
    """
    指定されたルールに従ってボーンウェイトを統合する
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        avatar_data: アバターデータ
    """
    # UpperChest -> Chest への統合
    upper_chest_bone = get_bone_name_from_humanoid(avatar_data, "UpperChest")
    chest_bone = get_bone_name_from_humanoid(avatar_data, "Chest")
    
    if upper_chest_bone and chest_bone and upper_chest_bone in mesh_obj.vertex_groups:
        # Chestグループが存在しない場合は作成
        if chest_bone not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=chest_bone)
        merge_vertex_group_weights(mesh_obj, upper_chest_bone, chest_bone)
        print(f"Merged {upper_chest_bone} weights to {chest_bone} in {mesh_obj.name}")
    
    # 胸ボーン -> Chest への統合
    breasts_humanoid_bones = [
        "LeftBreasts",
        "RightBreasts"
    ]
    
    if chest_bone:
        # Chestグループが存在しない場合は作成
        if chest_bone not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=chest_bone)
            
        for breasts_humanoid in breasts_humanoid_bones:
            breasts_bone = get_bone_name_from_humanoid(avatar_data, breasts_humanoid)
            if breasts_bone and breasts_bone in mesh_obj.vertex_groups:
                merge_vertex_group_weights(mesh_obj, breasts_bone, chest_bone)
                print(f"Merged {breasts_bone} weights to {chest_bone} in {mesh_obj.name}")
    
    # Left足指系ボーン -> LeftFoot への統合
    left_foot_bone = get_bone_name_from_humanoid(avatar_data, "LeftFoot")
    left_toe_humanoid_bones = [
        "LeftToes",
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
        "LeftFootLittleDistal"
    ]
    
    if left_foot_bone:
        # LeftFootグループが存在しない場合は作成
        if left_foot_bone not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=left_foot_bone)
            
        for toe_humanoid in left_toe_humanoid_bones:
            toe_bone = get_bone_name_from_humanoid(avatar_data, toe_humanoid)
            if toe_bone and toe_bone in mesh_obj.vertex_groups:
                merge_vertex_group_weights(mesh_obj, toe_bone, left_foot_bone)
                print(f"Merged {toe_bone} weights to {left_foot_bone} in {mesh_obj.name}")
    
    # Right足指系ボーン -> RightFoot への統合
    right_foot_bone = get_bone_name_from_humanoid(avatar_data, "RightFoot")
    right_toe_humanoid_bones = [
        "RightToes",
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
        "RightFootLittleDistal"
    ]
    
    if right_foot_bone:
        # RightFootグループが存在しない場合は作成
        if right_foot_bone not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=right_foot_bone)
            
        for toe_humanoid in right_toe_humanoid_bones:
            toe_bone = get_bone_name_from_humanoid(avatar_data, toe_humanoid)
            if toe_bone and toe_bone in mesh_obj.vertex_groups:
                merge_vertex_group_weights(mesh_obj, toe_bone, right_foot_bone)
                print(f"Merged {toe_bone} weights to {right_foot_bone} in {mesh_obj.name}")
