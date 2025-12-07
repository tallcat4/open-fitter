import os
import sys

from algo_utils.vertex_group_utils import merge_vertex_group_weights
from blender_utils.bone_utils import get_bone_name_from_humanoid
from blender_utils.bone_utils import get_bone_parent_map
from mathutils import Vector
from typing import Optional
import bmesh
import bpy
import numpy as np
import os
import sys


# Merged from merge_weights_to_parent.py

def merge_weights_to_parent(mesh_obj: bpy.types.Object, source_bone: str, target_bone: str) -> None:
    """
    Merge weights from source bone to target bone and remove source bone vertex group.
    
    Parameters:
        mesh_obj: Mesh object to process
        source_bone: Name of the source bone (whose weights will be moved)
        target_bone: Name of the target bone (that will receive the weights)
    """
    source_group = mesh_obj.vertex_groups.get(source_bone)
    target_group = mesh_obj.vertex_groups.get(target_bone)
    
    if not source_group:
        return
        
    if not target_group:
        # Create target group if it doesn't exist
        target_group = mesh_obj.vertex_groups.new(name=target_bone)
    
    # Transfer weights
    for vert in mesh_obj.data.vertices:
        source_weight = 0
        for group in vert.groups:
            if group.group == source_group.index:
                source_weight = group.weight
                break
                
        if source_weight > 0:
            target_group.add([vert.index], source_weight, 'ADD')
    
    # Remove source group
    mesh_obj.vertex_groups.remove(source_group)
    print(f"Merged weights from {source_bone} to {target_bone} in {mesh_obj.name}")

# Merged from remove_propagated_weights.py

def remove_propagated_weights(mesh_obj: bpy.types.Object, temp_group_name: str) -> None:
    """
    伝播させたウェイトを削除する
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        temp_group_name: 伝播頂点を記録した頂点グループの名前
    """
    # 一時頂点グループが存在することを確認
    temp_group = mesh_obj.vertex_groups.get(temp_group_name)
    if not temp_group:
        return
    
    # アーマチュアモディファイアからアーマチュアを取得
    armature_obj = None
    for modifier in mesh_obj.modifiers:
        if modifier.type == 'ARMATURE':
            armature_obj = modifier.object
            break
    
    if not armature_obj:
        print(f"Warning: No armature modifier found in {mesh_obj.name}")
        return
    
    # アーマチュアのすべてのボーン名を取得
    deform_groups = {bone.name for bone in armature_obj.data.bones}
    
    # 伝播させた頂点のウェイトを削除
    for vert in mesh_obj.data.vertices:
        # 一時グループのウェイトを取得
        weight = 0.0
        for g in vert.groups:
            if g.group == temp_group.index:
                weight = g.weight
                break
        
        # ウェイトが0より大きい場合（伝播された頂点の場合）
        if weight > 0:
            for group in mesh_obj.vertex_groups:
                try:
                    group.remove([vert.index])
                except RuntimeError:
                    continue
    
    # 一時頂点グループを削除
    mesh_obj.vertex_groups.remove(temp_group)

# Merged from merge_auxiliary_to_humanoid_weights.py

def merge_auxiliary_to_humanoid_weights(mesh_obj: bpy.types.Object, avatar_data: dict) -> None:
    """Create missing Humanoid bone vertex groups and merge auxiliary weights."""
    # Map auxiliary bones to their Humanoid bones
    aux_to_humanoid = {}
    for aux_set in avatar_data.get("auxiliaryBones", []):
        humanoid_bone = aux_set["humanoidBoneName"]
        bone_name = None
        # Get the actual bone name for the Humanoid bone
        for bone_map in avatar_data.get("humanoidBones", []):
            if bone_map["humanoidBoneName"] == humanoid_bone:
                bone_name = bone_map["boneName"]
                break
        if bone_name:
            for aux_bone in aux_set["auxiliaryBones"]:
                aux_to_humanoid[aux_bone] = bone_name

    # Check each auxiliary bone vertex group
    for aux_bone in aux_to_humanoid:
        if aux_bone in mesh_obj.vertex_groups:
            humanoid_bone = aux_to_humanoid[aux_bone]
            # Create Humanoid bone group if it doesn't exist
            if humanoid_bone not in mesh_obj.vertex_groups:
                print(f"Creating missing Humanoid bone group {humanoid_bone} for {mesh_obj.name}")
                mesh_obj.vertex_groups.new(name=humanoid_bone)

            # Get the vertex groups
            aux_group = mesh_obj.vertex_groups[aux_bone]
            humanoid_group = mesh_obj.vertex_groups[humanoid_bone]

            # Transfer weights from auxiliary to humanoid group
            for vert in mesh_obj.data.vertices:
                aux_weight = 0
                for group in vert.groups:
                    if group.group == aux_group.index:
                        aux_weight = group.weight
                        break
                
                if aux_weight > 0:
                    # Add weight to humanoid bone group
                    humanoid_group.add([vert.index], aux_weight, 'ADD')

            # Remove auxiliary bone vertex group
            mesh_obj.vertex_groups.remove(aux_group)
            print(f"Merged weights from {aux_bone} to {humanoid_bone} in {mesh_obj.name}")

# Merged from propagate_weights_to_side_vertices.py

def propagate_weights_to_side_vertices(
    target_obj,
    bone_groups,
    original_humanoid_weights,
    clothing_armature,
    max_iterations=100
):
    """
    側面ウェイトを持つがボーンウェイトを持たない頂点にウェイトを伝播する。
    
    Args:
        target_obj: 対象のBlenderオブジェクト
        bone_groups: ボーングループ名のセット
        original_humanoid_weights: 元のヒューマノイドウェイト辞書
        clothing_armature: 衣装アーマチュア（省略可）
        max_iterations: 最大反復回数
    """
    bm = bmesh.new()
    bm.from_mesh(target_obj.data)
    bm.verts.ensure_lookup_table()

    left_group = target_obj.vertex_groups.get("LeftSideWeights")
    right_group = target_obj.vertex_groups.get("RightSideWeights")

    all_deform_groups = set(bone_groups)
    if clothing_armature:
        all_deform_groups.update(bone.name for bone in clothing_armature.data.bones)

    def get_side_weight(vert_idx, group):
        if not group:
            return 0.0
        try:
            for g in target_obj.data.vertices[vert_idx].groups:
                if g.group == group.index:
                    return g.weight
        except Exception:
            return 0.0
        return 0.0

    def has_bone_weights(vert_idx):
        for g in target_obj.data.vertices[vert_idx].groups:
            if target_obj.vertex_groups[g.group].name in all_deform_groups:
                return True
        return False

    vertices_to_process = set()
    for vert in target_obj.data.vertices:
        if (get_side_weight(vert.index, left_group) > 0 or get_side_weight(vert.index, right_group) > 0) and not has_bone_weights(vert.index):
            vertices_to_process.add(vert.index)

    if not vertices_to_process:
        bm.free()
        return

    print(f"Found {len(vertices_to_process)} vertices without bone weights but with side weights")

    iteration = 0
    while vertices_to_process and iteration < max_iterations:
        propagated_this_iteration = set()
        for vert_idx in vertices_to_process:
            vert = bm.verts[vert_idx]
            neighbors_with_weights = []
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if has_bone_weights(other.index):
                    distance = (vert.co - other.co).length
                    neighbors_with_weights.append((other.index, distance))
            if neighbors_with_weights:
                closest_vert_idx = min(neighbors_with_weights, key=lambda x: x[1])[0]
                for group in target_obj.vertex_groups:
                    if group.name in all_deform_groups:
                        weight = 0.0
                        for g in target_obj.data.vertices[closest_vert_idx].groups:
                            if g.group == group.index:
                                weight = g.weight
                                break
                        if weight > 0:
                            group.add([vert_idx], weight, "REPLACE")
                propagated_this_iteration.add(vert_idx)

        if not propagated_this_iteration:
            break

        print(f"Iteration {iteration + 1}: Propagated weights to {len(propagated_this_iteration)} vertices")
        vertices_to_process -= propagated_this_iteration
        iteration += 1

    if vertices_to_process:
        print(f"Restoring original weights for {len(vertices_to_process)} remaining vertices")
        for vert_idx in vertices_to_process:
            if vert_idx in original_humanoid_weights:
                for group in target_obj.vertex_groups:
                    if group.name in all_deform_groups:
                        try:
                            group.remove([vert_idx])
                        except RuntimeError:
                            continue
                for group_name, weight in original_humanoid_weights[vert_idx].items():
                    if group_name in target_obj.vertex_groups:
                        target_obj.vertex_groups[group_name].add([vert_idx], weight, "REPLACE")

    bm.free()

# Merged from process_bone_weight_consolidation.py

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

# Merged from propagate_bone_weights.py

def propagate_bone_weights(mesh_obj: bpy.types.Object, temp_group_name: str = "PropagatedWeightsTemp", max_iterations: int = 500) -> Optional[str]:
    """
    ボーン変形に関わるボーンウェイトを持たない頂点にウェイトを伝播させる。
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        max_iterations: 最大反復回数
        
    Returns:
        Optional[str]: 伝播させた頂点を記録した頂点グループの名前。伝播が不要な場合はNone
    """
    # アーマチュアモディファイアからアーマチュアを取得
    armature_obj = None
    for modifier in mesh_obj.modifiers:
        if modifier.type == 'ARMATURE':
            armature_obj = modifier.object
            break
    
    if not armature_obj:
        print(f"Warning: No armature modifier found in {mesh_obj.name}")
        return None
    
    # アーマチュアのすべてのボーン名を取得
    deform_groups = {bone.name for bone in armature_obj.data.bones}
    
    # BMeshを作成
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    # 頂点ごとのウェイト情報を取得
    vertex_weights = {}
    vertices_without_weights = set()
    
    for vert in mesh_obj.data.vertices:
        has_weight = False
        weights = {}
        
        for group in mesh_obj.vertex_groups:
            if group.name in deform_groups:
                try:
                    weight = 0.0
                    for g in vert.groups:
                        if g.group == group.index:
                            weight = g.weight
                            has_weight = True
                            break
                    if weight > 0:
                        weights[group.name] = weight
                except RuntimeError:
                    continue
                    
        vertex_weights[vert.index] = weights
        if not weights:
            vertices_without_weights.add(vert.index)
    
    # ウェイトを持たない頂点がない場合は処理を終了
    if not vertices_without_weights:
        return None
    
    print(f"Found {len(vertices_without_weights)} vertices without weights in {mesh_obj.name}")
    
    # 一時的な頂点グループを作成（既存の同名グループがあれば削除）
    if temp_group_name in mesh_obj.vertex_groups:
        mesh_obj.vertex_groups.remove(mesh_obj.vertex_groups[temp_group_name])
    temp_group = mesh_obj.vertex_groups.new(name=temp_group_name)
    
    # 反復処理
    total_propagated = 0
    iteration = 0
    while iteration < max_iterations and vertices_without_weights:
        propagated_this_iteration = 0
        remaining_vertices = set()
        
        # 各ウェイトなし頂点について処理
        for vert_idx in vertices_without_weights:
            vert = bm.verts[vert_idx]
            # 隣接頂点を取得
            neighbors = set()
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if vertex_weights[other.index]:
                    neighbors.add(other)
            
            if neighbors:
                # 最も近い頂点を見つける
                closest_vert = min(neighbors, 
                                 key=lambda v: (v.co - vert.co).length)
                
                # ウェイトをコピー
                vertex_weights[vert_idx] = vertex_weights[closest_vert.index].copy()
                temp_group.add([vert_idx], 1.0, 'REPLACE')  # 伝播頂点を記録
                propagated_this_iteration += 1
            else:
                remaining_vertices.add(vert_idx)
        
        if propagated_this_iteration == 0:
            break
        
        print(f"Iteration {iteration + 1}: Propagated weights to {propagated_this_iteration} vertices in {mesh_obj.name}")
        total_propagated += propagated_this_iteration
        vertices_without_weights = remaining_vertices
        iteration += 1
    
    # 残りのウェイトなし頂点に平均ウェイトを割り当て
    if vertices_without_weights:
        total_weights = {}
        weight_count = 0
        
        # まず平均ウェイトを計算
        for vert_idx, weights in vertex_weights.items():
            if weights:
                weight_count += 1
                for group_name, weight in weights.items():
                    if group_name not in total_weights:
                        total_weights[group_name] = 0.0
                    total_weights[group_name] += weight
        
        if weight_count > 0:
            average_weights = {
                group_name: weight / weight_count
                for group_name, weight in total_weights.items()
            }
            
            # 残りの頂点に平均ウェイトを適用
            num_averaged = len(vertices_without_weights)
            print(f"Applying average weights to remaining {num_averaged} vertices in {mesh_obj.name}")
            
            for vert_idx in vertices_without_weights:
                vertex_weights[vert_idx] = average_weights.copy()
                temp_group.add([vert_idx], 1.0, 'REPLACE')  # 伝播頂点を記録
            total_propagated += num_averaged
    
    # 新しいウェイトを適用
    for vert_idx, weights in vertex_weights.items():
        for group_name, weight in weights.items():
            if group_name in mesh_obj.vertex_groups:
                mesh_obj.vertex_groups[group_name].add([vert_idx], weight, 'REPLACE')
    
    print(f"Total: Propagated weights to {total_propagated} vertices in {mesh_obj.name}")
    
    bm.free()
    return temp_group_name

# Merged from process_missing_bone_weights.py

def process_missing_bone_weights(base_mesh: bpy.types.Object, clothing_armature: bpy.types.Object, 
                               base_avatar_data: dict, clothing_avatar_data: dict, preserve_optional_humanoid_bones: bool) -> None:
    """
    Process weights for humanoid bones that exist in base avatar but not in clothing.
    """
    # Get bone names from clothing armature
    clothing_bone_names = set(bone.name for bone in clothing_armature.data.bones)

    # Create mappings for base avatar
    base_humanoid_to_bone = {}
    base_bone_to_humanoid = {}
    for bone_map in base_avatar_data.get("humanoidBones", []):
        if "humanoidBoneName" in bone_map and "boneName" in bone_map:
            base_humanoid_to_bone[bone_map["humanoidBoneName"]] = bone_map["boneName"]
            base_bone_to_humanoid[bone_map["boneName"]] = bone_map["humanoidBoneName"]

    # Create mappings for clothing
    clothing_humanoid_to_bone = {}
    for bone_map in clothing_avatar_data.get("humanoidBones", []):
        if "humanoidBoneName" in bone_map and "boneName" in bone_map:
            clothing_humanoid_to_bone[bone_map["humanoidBoneName"]] = bone_map["boneName"]

    # Create auxiliary bones mapping
    aux_bones_map = {}
    for aux_set in base_avatar_data.get("auxiliaryBones", []):
        humanoid_bone = aux_set["humanoidBoneName"]
        bone_name = base_humanoid_to_bone.get(humanoid_bone)
        if bone_name:
            aux_bones_map[bone_name] = aux_set["auxiliaryBones"]

    # Create parent map from bone hierarchy
    parent_map = get_bone_parent_map(base_avatar_data["boneHierarchy"])

    # Process each humanoid bone from base avatar
    for humanoid_name, bone_name in base_humanoid_to_bone.items():
        # Skip if bone exists in clothing armature
        if clothing_humanoid_to_bone.get(humanoid_name) in clothing_bone_names:
            continue

        # Check if this bone should be preserved when preserve_optional_humanoid_bones is True
        if preserve_optional_humanoid_bones:
            should_preserve = False
            
            # Condition 1: Chest exists in clothing, UpperChest missing in clothing but exists in base
            if (humanoid_name == "UpperChest" and 
                "Chest" in clothing_humanoid_to_bone and 
                clothing_humanoid_to_bone["Chest"] in clothing_bone_names and
                "UpperChest" not in clothing_humanoid_to_bone and
                "UpperChest" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving UpperChest bone weights due to Chest condition")
            
            # Condition 2: LeftLowerLeg exists in clothing, LeftFoot missing in clothing but exists in base
            elif (humanoid_name == "LeftFoot" and 
                  "LeftLowerLeg" in clothing_humanoid_to_bone and 
                  clothing_humanoid_to_bone["LeftLowerLeg"] in clothing_bone_names and
                  "LeftFoot" not in clothing_humanoid_to_bone and
                  "LeftFoot" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving LeftFoot bone weights due to LeftLowerLeg condition")
            
            # Condition 2: RightLowerLeg exists in clothing, RightFoot missing in clothing but exists in base
            elif (humanoid_name == "RightFoot" and 
                  "RightLowerLeg" in clothing_humanoid_to_bone and 
                  clothing_humanoid_to_bone["RightLowerLeg"] in clothing_bone_names and
                  "RightFoot" not in clothing_humanoid_to_bone and
                  "RightFoot" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving RightFoot bone weights due to RightLowerLeg condition")
            
            # Condition 3: LeftLowerLeg or LeftFoot exists in clothing, LeftToe missing in clothing but exists in base
            elif (humanoid_name == "LeftToe" and 
                  (("LeftLowerLeg" in clothing_humanoid_to_bone and clothing_humanoid_to_bone["LeftLowerLeg"] in clothing_bone_names) or
                   ("LeftFoot" in clothing_humanoid_to_bone and clothing_humanoid_to_bone["LeftFoot"] in clothing_bone_names)) and
                  "LeftToe" not in clothing_humanoid_to_bone and
                  "LeftToe" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving LeftToe bone weights due to LeftLowerLeg/LeftFoot condition")
            
            # Condition 3: RightLowerLeg or RightFoot exists in clothing, RightToe missing in clothing but exists in base
            elif (humanoid_name == "RightToe" and 
                  (("RightLowerLeg" in clothing_humanoid_to_bone and clothing_humanoid_to_bone["RightLowerLeg"] in clothing_bone_names) or
                   ("RightFoot" in clothing_humanoid_to_bone and clothing_humanoid_to_bone["RightFoot"] in clothing_bone_names)) and
                  "RightToe" not in clothing_humanoid_to_bone and
                  "RightToe" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving RightToe bone weights due to RightLowerLeg/RightFoot condition")

            elif (humanoid_name == "LeftBreast" and 
                  "LeftBreast" not in clothing_humanoid_to_bone and
                  ("Chest" in clothing_humanoid_to_bone or "UpperChest" in clothing_humanoid_to_bone) and 
                  (clothing_humanoid_to_bone["Chest"] in clothing_bone_names or clothing_humanoid_to_bone["UpperChest"] in clothing_bone_names) and
                  "LeftBreast" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving LeftBreast bone weights due to Chest condition")
            
            elif (humanoid_name == "RightBreast" and 
                  "RightBreast" not in clothing_humanoid_to_bone and
                  ("Chest" in clothing_humanoid_to_bone or "UpperChest" in clothing_humanoid_to_bone) and 
                  (clothing_humanoid_to_bone["Chest"] in clothing_bone_names or clothing_humanoid_to_bone["UpperChest"] in clothing_bone_names) and
                  "RightBreast" in base_humanoid_to_bone):
                should_preserve = True
                print(f"Preserving RightBreast bone weights due to Chest condition")
            
            if should_preserve:
                print(f"Skipping processing for preserved bone: {humanoid_name} ({bone_name})")
                continue

        print(f"Processing missing humanoid bone: {humanoid_name} ({bone_name})")
        
        # Find parent that exists in clothing armature
        current_bone = bone_name
        target_bone = None

        while current_bone and not target_bone:
            parent_bone = parent_map.get(current_bone)
            if not parent_bone:
                break

            parent_humanoid = base_bone_to_humanoid.get(parent_bone)
            if parent_humanoid and clothing_humanoid_to_bone.get(parent_humanoid) in clothing_bone_names:
                target_bone = base_humanoid_to_bone[parent_humanoid]
                break

            current_bone = parent_bone

        if target_bone:
            # Transfer main bone weights
            source_group = base_mesh.vertex_groups.get(bone_name)
            if source_group:
                merge_weights_to_parent(base_mesh, bone_name, target_bone)

                # Transfer auxiliary bone weights
                for aux_bone in aux_bones_map.get(bone_name, []):
                    if aux_bone in base_mesh.vertex_groups:
                        merge_weights_to_parent(base_mesh, aux_bone, target_bone)

                # Remove source groups
                if bone_name in base_mesh.vertex_groups:
                    base_mesh.vertex_groups.remove(base_mesh.vertex_groups[bone_name])
                for aux_bone in aux_bones_map.get(bone_name, []):
                    if aux_bone in base_mesh.vertex_groups:
                        base_mesh.vertex_groups.remove(base_mesh.vertex_groups[aux_bone])

# Merged from adjust_hand_weights.py

def adjust_hand_weights(target_obj, armature, base_avatar_data):

    def get_bone_name(humanoid_bone_name):
        """Humanoidボーン名から実際のボーン名を取得"""
        for bone_data in base_avatar_data.get("humanoidBones", []):
            if bone_data.get("humanoidBoneName") == humanoid_bone_name:
                return bone_data.get("boneName")
        return None

    def get_finger_bones(side_prefix):
        """指のボーン名を取得（足の指は除外）"""
        finger_bones = []
        finger_types = ["Thumb", "Index", "Middle", "Ring", "Little"]
        positions = ["Proximal", "Intermediate", "Distal"]
        
        for finger in finger_types:
            for pos in positions:
                humanoid_name = f"{side_prefix}{finger}{pos}"
                # "Foot"を含まないHumanoidボーン名のみを処理
                if "Foot" not in humanoid_name:
                    bone_name = get_bone_name(humanoid_name)
                    if bone_name:
                        finger_bones.append(bone_name)
        
        return finger_bones

    def get_bone_head_world(bone_name):
        """ボーンのhead位置をワールド座標で取得"""
        bone = armature.pose.bones[bone_name]
        return armature.matrix_world @ bone.head

    def get_lowerarm_and_auxiliary_bones(side_prefix):
        """LowerArmとその補助ボーンを取得"""
        lower_arm_bones = []
        
        # LowerArmボーンを追加
        lower_arm_name = get_bone_name(f"{side_prefix}LowerArm")
        if lower_arm_name:
            lower_arm_bones.append(lower_arm_name)
        
        # 補助ボーンを追加
        for aux_set in base_avatar_data.get("auxiliaryBones", []):
            if aux_set["humanoidBoneName"] == f"{side_prefix}LowerArm":
                lower_arm_bones.extend(aux_set["auxiliaryBones"])
                
        return lower_arm_bones

    def find_closest_lower_arm_bone(hand_head_pos, lower_arm_bones):
        """手のボーンのHeadに最も近いLowerArmまたは補助ボーンを見つける"""
        closest_bone = None
        min_distance = float('inf')
        
        for bone_name in lower_arm_bones:
            if bone_name in armature.pose.bones:
                bone_head = get_bone_head_world(bone_name)
                distance = (Vector(bone_head) - hand_head_pos).length
                if distance < min_distance:
                    min_distance = distance
                    closest_bone = bone_name
                    
        return closest_bone

    def process_hand(is_right):
        # 手の種類に応じてHumanoidボーン名を設定
        side = "Right" if is_right else "Left"
        hand_bone_name = get_bone_name(f"{side}Hand")
        lower_arm_bone_name = get_bone_name(f"{side}LowerArm")

        if not hand_bone_name or not lower_arm_bone_name:
            return

        # 手と指のボーン名を収集
        vertex_groups = [hand_bone_name] + get_finger_bones(side)

        # ボーンの位置をワールド座標で取得
        hand_head = Vector(get_bone_head_world(hand_bone_name))
        lower_arm_head = Vector(get_bone_head_world(lower_arm_bone_name))

        # 先端方向ベクトルを計算
        tip_direction = (hand_head - lower_arm_head).normalized()

        # 最小角度を探す
        min_angle = float('inf')
        has_weight = False

        # 各頂点について処理
        for v in target_obj.data.vertices:
            has_vertex_weight = False
            for group_name in vertex_groups:
                if group_name not in target_obj.vertex_groups:
                    continue
                weight = 0
                try:
                    for g in v.groups:
                        if g.group == target_obj.vertex_groups[group_name].index:
                            weight = g.weight
                            break
                    if weight > 0:
                        has_weight = True
                        has_vertex_weight = True
                except RuntimeError:
                    continue
            
            # この頂点が手または指のウェイトを持っている場合
            if has_vertex_weight:
                # 頂点のワールド座標を計算
                vertex_world = target_obj.matrix_world @ Vector(v.co)
                # 頂点からhandボーンへのベクトル
                vertex_vector = (vertex_world - hand_head).normalized()
                # 角度を計算 (0-180度の範囲に収める)
                # dot productを使用して角度を計算
                dot_product = vertex_vector.dot(tip_direction)
                # -1.0から1.0の範囲にクランプ
                dot_product = max(min(dot_product, 1.0), -1.0)
                angle = np.degrees(np.arccos(dot_product))
                min_angle = min(min_angle, angle)

        if not has_weight:
            return

        # 70度以上の場合の処理
        if min_angle >= 70:
            print(f"- Minimum angle exceeds 70 degrees ({min_angle} degrees), transferring weights for {side} hand")
            
            # LowerArmとその補助ボーンを取得
            lower_arm_bones = get_lowerarm_and_auxiliary_bones(side)
            
            # 手のボーンのHeadに最も近いLowerArmボーンを見つける
            closest_bone = find_closest_lower_arm_bone(hand_head, lower_arm_bones)
            
            if closest_bone:
                print(f"- Transferring weights to {closest_bone}")
                
                # 各頂点について処理
                for v in target_obj.data.vertices:
                    total_weight = 0.0
                    
                    # 手と指のボーンのウェイトを合計
                    for group_name in vertex_groups:
                        if group_name in target_obj.vertex_groups:
                            group = target_obj.vertex_groups[group_name]
                            try:
                                for g in v.groups:
                                    if g.group == group.index:
                                        total_weight += g.weight
                                        break
                            except RuntimeError:
                                continue
                    
                    # ウェイトを最も近いLowerArmボーンに転送
                    if total_weight > 0:
                        if closest_bone not in target_obj.vertex_groups:
                            target_obj.vertex_groups.new(name=closest_bone)
                        target_obj.vertex_groups[closest_bone].add([v.index], total_weight, 'ADD')
                    
                    # 元のウェイトを削除
                    for group_name in vertex_groups:
                        if group_name in target_obj.vertex_groups:
                            try:
                                target_obj.vertex_groups[group_name].remove([v.index])
                            except RuntimeError:
                                continue
            else:
                print(f"Warning: No suitable LowerArm bone found for {side} hand")
        else:
            print(f"- Minimum angle is within acceptable range ({min_angle} degrees), keeping weights for {side} hand")

    # 両手の処理を実行
    process_hand(is_right=True)
    process_hand(is_right=False)