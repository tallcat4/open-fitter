import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass

import bmesh
import bpy
from algo_utils.find_connected_components import find_connected_components
from algo_utils.get_humanoid_and_auxiliary_bone_groups import (
    get_humanoid_and_auxiliary_bone_groups,
)
from math_utils.calculate_obb_from_points import calculate_obb_from_points
from math_utils.check_mesh_obb_intersection import check_mesh_obb_intersection


@dataclass
class _WeightPatternContext:
    obj: bpy.types.Object
    base_obj: bpy.types.Object
    bm: bmesh.types.BMesh
    target_groups: set
    existing_target_groups: set
    rigid_group: bpy.types.VertexGroup
    tolerance: float = 0.0001
    round_digits: int = 4
    rigid_group_name: str = "Rigid2"


def _build_context(obj, base_avatar_data, clothing_armature, bm):
    base_obj = bpy.data.objects.get("Body.BaseAvatar")
    if not base_obj:
        raise Exception("Base avatar mesh (Body.BaseAvatar) not found")

    target_groups = get_humanoid_and_auxiliary_bone_groups(base_avatar_data)
    if clothing_armature:
        target_groups.update(bone.name for bone in clothing_armature.data.bones)

    existing_target_groups = {vg.name for vg in obj.vertex_groups if vg.name in target_groups}

    rigid_group_name = "Rigid2"
    if rigid_group_name not in obj.vertex_groups:
        obj.vertex_groups.new(name=rigid_group_name)
    rigid_group = obj.vertex_groups[rigid_group_name]

    return _WeightPatternContext(
        obj=obj,
        base_obj=base_obj,
        bm=bm,
        target_groups=target_groups,
        existing_target_groups=existing_target_groups,
        rigid_group=rigid_group,
    )


def _collect_component_weights(ctx: _WeightPatternContext, component):
    vertex_weights = []
    for vert_idx in component:
        vert = ctx.obj.data.vertices[vert_idx]
        weights = {group: 0.0 for group in ctx.existing_target_groups}
        for g in vert.groups:
            group_name = ctx.obj.vertex_groups[g.group].name
            if group_name in ctx.existing_target_groups:
                weights[group_name] = g.weight
        vertex_weights.append(weights)
    return vertex_weights


def _is_uniform_pattern(vertex_weights, existing_target_groups, tolerance):
    if not vertex_weights:
        return False, None
    first_weights = vertex_weights[0]
    for weights in vertex_weights[1:]:
        for group_name in existing_target_groups:
            if abs(weights[group_name] - first_weights[group_name]) >= tolerance:
                return False, None
    return True, first_weights


def _component_world_points(ctx: _WeightPatternContext, component):
    points = []
    for idx in component:
        if idx < len(ctx.bm.verts):
            points.append(ctx.obj.matrix_world @ ctx.bm.verts[idx].co)
    return points


def _should_exclude_by_intersection(ctx: _WeightPatternContext, component_points):
    if len(component_points) < 3:
        return False
    obb = calculate_obb_from_points(component_points)
    if obb is None:
        return False
    if check_mesh_obb_intersection(ctx.base_obj, obb):
        print(
            f"Component with {len(component_points)} vertices intersects with base mesh, excluding from rigid transfer"
        )
        return True
    return False


def _pattern_key(first_weights, round_digits):
    return tuple(sorted((k, round(v, round_digits)) for k, v in first_weights.items() if v > 0))


def _apply_rigid(ctx: _WeightPatternContext, component):
    for vert_idx in component:
        ctx.rigid_group.add([vert_idx], 1.0, "REPLACE")


def _debug_dump_patterns(obj_name, components, component_patterns):
    print(f"Found {len(components)} connected components in {obj_name}")
    print(f"Found {len(component_patterns)} uniform weight patterns in {obj_name}")
    for i, (pattern, components_list) in enumerate(component_patterns.items()):
        total_vertices = sum(len(comp) for comp in components_list)
        print(f"Pattern {i}: {pattern}")
        print(f"  Components: {len(components_list)}, Total vertices: {total_vertices}")
        for j, comp in enumerate(components_list):
            print(f"    Component {j}: {len(comp)} vertices")


def group_components_by_weight_pattern(obj, base_avatar_data, clothing_armature):
    """
    同じウェイトパターンを持つ連結成分をグループ化する
    
    Parameters:
        obj: 処理対象のメッシュオブジェクト
        base_avatar_data: ベースアバターデータ
        
    Returns:
        dict: ウェイトパターンをキー、連結成分のリストを値とする辞書
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        ctx = _build_context(obj, base_avatar_data, clothing_armature, bm)

        components = find_connected_components(obj)
        component_patterns = {}
        uniform_components = []

        for component in components:
            vertex_weights = _collect_component_weights(ctx, component)
            if not vertex_weights:
                continue

            is_uniform, first_weights = _is_uniform_pattern(
                vertex_weights, ctx.existing_target_groups, ctx.tolerance
            )
            if not is_uniform:
                continue

            component_points = _component_world_points(ctx, component)
            if _should_exclude_by_intersection(ctx, component_points):
                continue

            uniform_components.append(component)

            pattern_tuple = _pattern_key(first_weights, ctx.round_digits)
            if pattern_tuple:
                _apply_rigid(ctx, component)
                if pattern_tuple not in component_patterns:
                    component_patterns[pattern_tuple] = []
                component_patterns[pattern_tuple].append(component)

        _debug_dump_patterns(obj.name, components, component_patterns)
        return component_patterns
    finally:
        bm.free()


def process_weight_patterns(obj, base_avatar_data, clothing_armature):
    """Thin wrapper to align with other process_* entrypoints."""
    return group_components_by_weight_pattern(obj, base_avatar_data, clothing_armature)
