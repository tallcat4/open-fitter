import os
import sys

# Add the parent directory (extracted/) to sys.path to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import defaultdict
import bpy
import numpy as np
from scipy.spatial import cKDTree

from io_utils.store_weights import store_weights
from blender_utils.get_evaluated_mesh import get_evaluated_mesh
from math_utils.create_distance_falloff_transfer_mask import create_distance_falloff_transfer_mask

def compute_non_humanoid_masks(context):
    context.new_groups = set(vg.name for vg in context.target_obj.vertex_groups)
    context.added_groups = context.new_groups - context.original_groups

    print(f"  ボーングループ: {context.bone_groups}")
    print(f"  オリジナルグループ: {context.original_groups}")
    print(f"  新規グループ: {context.new_groups}")
    print(f"  追加グループ: {context.added_groups}")

    num_vertices = len(context.target_obj.data.vertices)
    all_transferred_weights = store_weights(context.target_obj, context.all_deform_groups)

    clothing_bone_to_humanoid = {bone_map["boneName"]: bone_map["humanoidBoneName"] for bone_map in context.clothing_avatar_data["humanoidBones"]}
    clothing_bone_to_parent_humanoid = {}
    for clothing_bone in context.clothing_armature.data.bones:
        current_bone = clothing_bone
        current_bone_name = current_bone.name
        parent_humanoid_name = None
        while current_bone:
            if current_bone.name in clothing_bone_to_humanoid:
                parent_humanoid_name = clothing_bone_to_humanoid[current_bone.name]
                break
            current_bone = current_bone.parent
        print(f"current_bone_name: {current_bone_name}, parent_humanoid_name: {parent_humanoid_name}")
        if parent_humanoid_name:
            clothing_bone_to_parent_humanoid[current_bone_name] = parent_humanoid_name

    context.non_humanoid_parts_mask = np.zeros(num_vertices)
    context.non_humanoid_total_weights = np.zeros(num_vertices)
    for vert_idx, groups in context.original_non_humanoid_weights.items():
        total_weight = sum(groups.values())
        if total_weight > 1.0:
            total_weight = 1.0
        context.non_humanoid_total_weights[vert_idx] = total_weight
        if total_weight > 0.999:
            context.non_humanoid_parts_mask[vert_idx] = 1.0

    transferred_weight_patterns = [None] * num_vertices
    for vert_idx in range(num_vertices):
        groups = all_transferred_weights.get(vert_idx, {})
        converted_weights = defaultdict(float)
        for group_name, weight in groups.items():
            if weight <= 0.0:
                continue
            if group_name in context.auxiliary_bones_to_humanoid:
                humanoid_name = context.auxiliary_bones_to_humanoid[group_name]
                if humanoid_name:
                    converted_weights[humanoid_name] += weight
            else:
                humanoid_name = context.bone_to_humanoid.get(group_name)
                if humanoid_name:
                    converted_weights[humanoid_name] += weight
                else:
                    converted_weights[group_name] += weight
        transferred_weight_patterns[vert_idx] = dict(converted_weights)

    original_non_humanoid_weight_patterns = [None] * num_vertices
    for vert_idx in range(num_vertices):
        groups = context.original_non_humanoid_weights.get(vert_idx, {})
        converted_weights = defaultdict(float)
        for group_name, weight in groups.items():
            if weight <= 0.0:
                continue
            parent_humanoid = clothing_bone_to_parent_humanoid.get(group_name)
            if parent_humanoid:
                converted_weights[parent_humanoid] += weight
            else:
                converted_weights[group_name] += weight
        original_non_humanoid_weight_patterns[vert_idx] = dict(converted_weights)

    cloth_bm = get_evaluated_mesh(context.target_obj)
    cloth_bm.verts.ensure_lookup_table()
    cloth_bm.faces.ensure_lookup_table()
    vertex_coords = np.array([v.co for v in cloth_bm.verts])

    pattern_difference_threshold = 0.2
    neighbor_search_radius = 0.005
    context.non_humanoid_difference_mask = np.zeros_like(context.non_humanoid_parts_mask)

    hinge_bone_mask = np.zeros_like(context.non_humanoid_parts_mask)
    hinge_group = context.target_obj.vertex_groups.get("HingeBone")
    if hinge_group:
        for vert_idx in range(num_vertices):
            for g in context.target_obj.data.vertices[vert_idx].groups:
                if g.group == hinge_group.index and g.weight > 0.001:
                    hinge_bone_mask[vert_idx] = 1.0
                    break

    if num_vertices > 0:
        kd_tree = cKDTree(vertex_coords)

        def calculate_pattern_difference(weights_a, weights_b):
            if not weights_a and not weights_b:
                return 0.0
            keys = set(weights_a.keys()) | set(weights_b.keys())
            difference = 0.0
            for key in keys:
                difference += abs(weights_a.get(key, 0.0) - weights_b.get(key, 0.0))
            return difference

        for vert_idx, mask_value in enumerate(context.non_humanoid_parts_mask):
            if mask_value <= 0.0:
                continue
            base_pattern = original_non_humanoid_weight_patterns[vert_idx]
            neighbor_indices = kd_tree.query_ball_point(vertex_coords[vert_idx], neighbor_search_radius)
            for neighbor_idx in neighbor_indices:
                if neighbor_idx == vert_idx:
                    continue
                if context.non_humanoid_parts_mask[neighbor_idx] > 0.001:
                    continue
                neighbor_pattern = transferred_weight_patterns[neighbor_idx]
                if not neighbor_pattern:
                    continue
                difference = calculate_pattern_difference(base_pattern, neighbor_pattern)
                if difference > pattern_difference_threshold:
                    context.non_humanoid_difference_mask[vert_idx] = 1.0 * hinge_bone_mask[vert_idx] * hinge_bone_mask[vert_idx]
                    break

    context.non_humanoid_difference_group = context.target_obj.vertex_groups.new(name="NonHumanoidDifference")
    for vert_idx, mask_value in enumerate(context.non_humanoid_difference_mask):
        if mask_value > 0.0:
            context.non_humanoid_difference_group.add([vert_idx], 1.0, "REPLACE")

    current_mode = bpy.context.object.mode
    bpy.context.view_layer.objects.active = context.target_obj
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    context.target_obj.vertex_groups.active_index = context.non_humanoid_difference_group.index
    bpy.ops.paint.vert_select_all(action="SELECT")
    bpy.ops.object.vertex_group_smooth(factor=0.5, repeat=5, expand=0.5)

    falloff_mask_time_start = time.time()
    sway_settings = context.base_avatar_data.get("commonSwaySettings", {"startDistance": 0.025, "endDistance": 0.050})
    context.distance_falloff_group = create_distance_falloff_transfer_mask(
        context.target_obj,
        context.base_avatar_data,
        "DistanceFalloffMask",
        max_distance=sway_settings["endDistance"],
        min_distance=sway_settings["startDistance"],
    )
    context.target_obj.vertex_groups.active_index = context.distance_falloff_group.index
    bpy.ops.object.vertex_group_smooth(factor=1, repeat=3, expand=0.1)
    falloff_mask_time = time.time() - falloff_mask_time_start
    print(f"  距離フォールオフマスク作成: {falloff_mask_time:.2f}秒")

    context.distance_falloff_group2 = create_distance_falloff_transfer_mask(
        context.target_obj,
        context.base_avatar_data,
        "DistanceFalloffMask2",
        max_distance=0.1,
        min_distance=0.04,
    )
    context.target_obj.vertex_groups.active_index = context.distance_falloff_group2.index
    bpy.ops.object.vertex_group_smooth(factor=1, repeat=3, expand=0.1)
    print(f"  distance_falloff_group2: {context.distance_falloff_group2.index}")

    bpy.ops.object.mode_set(mode=current_mode)

    non_humanoid_difference_weights = np.zeros(num_vertices)
    distance_falloff_weights = np.zeros(num_vertices)
    for vert_idx in range(num_vertices):
        for g in context.target_obj.data.vertices[vert_idx].groups:
            if g.group == context.non_humanoid_difference_group.index:
                non_humanoid_difference_weights[vert_idx] = g.weight
            if g.group == context.distance_falloff_group2.index:
                distance_falloff_weights[vert_idx] = g.weight

    for vert_idx, groups in context.original_non_humanoid_weights.items():
        for group_name, weight in groups.items():
            if group_name in context.target_obj.vertex_groups:
                result_weight = weight * (1.0 - non_humanoid_difference_weights[vert_idx] * distance_falloff_weights[vert_idx])
                context.target_obj.vertex_groups[group_name].add([vert_idx], result_weight, "REPLACE")

    current_humanoid_weights = store_weights(context.target_obj, context.bone_groups)
    for vert_idx, groups in current_humanoid_weights.items():
        for group_name, weight in groups.items():
            if group_name in context.target_obj.vertex_groups:
                factor = 1.0 - context.non_humanoid_total_weights[vert_idx] * (1.0 - non_humanoid_difference_weights[vert_idx] * distance_falloff_weights[vert_idx])
                result_weight = weight * factor
                context.target_obj.vertex_groups[group_name].add([vert_idx], result_weight, "REPLACE")

    for vert_idx in range(len(context.non_humanoid_total_weights)):
        context.non_humanoid_total_weights[vert_idx] = context.non_humanoid_total_weights[vert_idx] * (1.0 - non_humanoid_difference_weights[vert_idx] * distance_falloff_weights[vert_idx])

    cloth_bm.free()
