import os
import sys

# Add the parent directory (extracted/) to sys.path to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import deque

import bmesh
from math_utils.weight_utils import get_vertex_weight_safe
from blender_utils.weight_processing_utils import merge_weights_to_parent


def merge_added_groups(context):
    group_merge_time_start = time.time()
    max_iterations = 5
    iteration = 0
    added_groups = set(context.added_groups)
    while added_groups and iteration < max_iterations:
        changed = False
        remaining_groups = set()
        print(f"  反復処理: {iteration}")
        for group_name in added_groups:
            print(f"  グループ名: {group_name}")
            if group_name not in context.target_obj.vertex_groups:
                print(f"  {group_name} は削除されています。スキップします")
                continue
            group = context.target_obj.vertex_groups[group_name]
            verts_with_weight = []
            for v in context.target_obj.data.vertices:
                weight = get_vertex_weight_safe(context.target_obj, group, v.index)
                if weight > 0:
                    verts_with_weight.append(v)
            print(f"  ウェイトを持つ頂点数: {len(verts_with_weight)}")
            if len(verts_with_weight) == 0:
                print(f"  {group_name} は空: スキップします")
                continue
            if group_name in context.bone_to_humanoid:
                humanoid_group_name = context.bone_to_humanoid[group_name]
                if "LeftToes" in context.humanoid_to_bone and context.humanoid_to_bone["LeftToes"] in context.original_groups:
                    if humanoid_group_name in context.left_foot_finger_humanoid_bones:
                        merge_weights_to_parent(context.target_obj, group_name, context.humanoid_to_bone["LeftToes"])
                        changed = True
                        continue
                if "RightToes" in context.humanoid_to_bone and context.humanoid_to_bone["RightToes"] in context.original_groups:
                    if humanoid_group_name in context.right_foot_finger_humanoid_bones:
                        merge_weights_to_parent(context.target_obj, group_name, context.humanoid_to_bone["RightToes"])
                        changed = True
                        continue

            existing_groups = set()
            for vert in verts_with_weight:
                for g in vert.groups:
                    g_name = context.target_obj.vertex_groups[g.group].name
                    if g_name in context.bone_groups and g_name in context.original_groups and g.weight > 0:
                        existing_groups.add(g_name)
            print(f"  既存グループ: {existing_groups}")
            if len(existing_groups) == 1:
                merge_weights_to_parent(context.target_obj, group_name, list(existing_groups)[0])
                changed = True
            elif len(existing_groups) == 0:
                bm = bmesh.new()
                bm.from_mesh(context.target_obj.data)
                bm.verts.ensure_lookup_table()
                visited_verts = set(vert.index for vert in verts_with_weight)
                queue = deque(verts_with_weight)
                while queue:
                    vert = queue.popleft()
                    for edge in bm.verts[vert.index].link_edges:
                        other_vert = edge.other_vert(bm.verts[vert.index])
                        if other_vert.index not in visited_verts:
                            visited_verts.add(other_vert.index)
                            for g in context.target_obj.data.vertices[other_vert.index].groups:
                                if context.target_obj.vertex_groups[g.group].name in context.bone_groups and g.weight > 0:
                                    existing_groups.add(context.target_obj.vertex_groups[g.group].name)
                                    if len(existing_groups) > 1:
                                        break
                            if len(existing_groups) == 1:
                                merge_weights_to_parent(context.target_obj, group_name, existing_groups.pop())
                                changed = True
                                break
                            queue.append(context.target_obj.data.vertices[other_vert.index])
                bm.free()
                print(f"  隣接探索後の既存グループ: {existing_groups}")

            if len(existing_groups) != 1:
                remaining_groups.add(group_name)

        if not changed:
            break
        added_groups = remaining_groups
        iteration += 1
    group_merge_time = time.time() - group_merge_time_start
    print(f"  グループ統合処理: {group_merge_time:.2f}秒")

    aux_bone_time_start = time.time()
    for group_name in list(added_groups):
        for aux_set in context.base_avatar_data.get("auxiliaryBones", []):
            if group_name in aux_set["auxiliaryBones"]:
                humanoid_bone = aux_set["humanoidBoneName"]
                if humanoid_bone in context.humanoid_to_bone and context.humanoid_to_bone[humanoid_bone] in context.bone_groups:
                    merge_weights_to_parent(context.target_obj, group_name, context.humanoid_to_bone[humanoid_bone])
                    try:
                        added_groups.remove(group_name)
                    except KeyError:
                        pass
                    break

    for group_name in added_groups:
        if group_name not in context.target_obj.vertex_groups:
            continue
        group = context.target_obj.vertex_groups[group_name]
        for vert in context.target_obj.data.vertices:
            weight = get_vertex_weight_safe(context.target_obj, group, vert.index)
            if weight > 0:
                for orig_group_name, orig_weight in context.original_humanoid_weights[vert.index].items():
                    if orig_group_name in context.target_obj.vertex_groups:
                        context.target_obj.vertex_groups[orig_group_name].add([vert.index], orig_weight * weight, "ADD")

    for group_name in added_groups:
        if group_name in context.target_obj.vertex_groups:
            context.target_obj.vertex_groups.remove(context.target_obj.vertex_groups[group_name])
    aux_bone_time = time.time() - aux_bone_time_start
    print(f"  補助ボーン処理: {aux_bone_time:.2f}秒")
