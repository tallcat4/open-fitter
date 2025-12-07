import os
import sys

from algo_utils.bone_group_utils import (
    get_humanoid_and_auxiliary_bone_groups,
)
from dataclasses import dataclass
from math_utils.geometry_utils import check_mesh_obb_intersection
from math_utils.obb_utils import calculate_obb_from_points
from mathutils import Vector
import bmesh
import bpy
import os
import sys


# Merged from find_connected_components.py

def find_connected_components(mesh_obj):
    """
    メッシュオブジェクト内で接続していないコンポーネントを検出する
    
    Parameters:
        mesh_obj: 検出対象のメッシュオブジェクト
        
    Returns:
        List[Set[int]]: 各コンポーネントに含まれる頂点インデックスのセットのリスト
    """
    # BMeshを作成し、元のメッシュからデータをコピー
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.verts.ensure_lookup_table()
    
    # 頂点インデックスのマッピングを作成（BMesh内のインデックス → 元のメッシュのインデックス）
    vert_indices = {v.index: i for i, v in enumerate(bm.verts)}
    
    # 未訪問の頂点を追跡
    unvisited = set(vert_indices.keys())
    components = []
    
    while unvisited:
        # 未訪問の頂点から開始
        start_idx = next(iter(unvisited))
        
        # 幅優先探索で連結成分を検出
        component = set()
        queue = [start_idx]
        
        while queue:
            current = queue.pop(0)
            if current in unvisited:
                unvisited.remove(current)
                component.add(vert_indices[current])  # 元のメッシュのインデックスに変換して追加
                
                # 隣接頂点をキューに追加（エッジで接続されている頂点のみ）
                for edge in bm.verts[current].link_edges:
                    other = edge.other_vert(bm.verts[current]).index
                    if other in unvisited:
                        queue.append(other)
        
        # 頂点数が1のコンポーネント（孤立頂点）は除外
        if len(component) > 1:
            components.append(component)
    
    bm.free()
    return components

# Merged from group_components_by_weight_pattern.py

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

# Merged from cluster_components_by_adaptive_distance.py

def cluster_components_by_adaptive_distance(component_coords, component_sizes):
    """
    コンポーネント間の距離に基づいてクラスタリングする（サイズに応じた適応的な閾値を使用）
    
    Parameters:
        component_coords: コンポーネントインデックスをキー、頂点座標のリストを値とする辞書
        component_sizes: コンポーネントインデックスをキー、サイズを値とする辞書
        
    Returns:
        list: クラスターのリスト（各クラスターはコンポーネントインデックスのリスト）
    """
    if not component_coords:
        return []
    
    # 各コンポーネントの中心点を計算
    centers = {}
    for comp_idx, coords in component_coords.items():
        if coords:
            center = Vector((0, 0, 0))
            for co in coords:
                center += co
            center /= len(coords)
            centers[comp_idx] = center
    
    # クラスターのリスト（初期状態では各コンポーネントが独立したクラスター）
    clusters = [[comp_idx] for comp_idx in centers.keys()]
    
    # コンポーネントの平均サイズを計算
    if component_sizes:
        average_size = sum(component_sizes.values()) / len(component_sizes)
    else:
        average_size = 0.1  # デフォルト値
    
    # 最小閾値と最大閾値を設定
    min_threshold = 0.1
    max_threshold = 1.0
    
    # クラスターをマージする
    merged = True
    while merged:
        merged = False
        
        # 各クラスターペアをチェック
        for i in range(len(clusters)):
            if i >= len(clusters):  # クラスター数が変わった場合の安全チェック
                break
                
            for j in range(i + 1, len(clusters)):
                if j >= len(clusters):  # クラスター数が変わった場合の安全チェック
                    break
                    
                # 各クラスター内のコンポーネント間の最小距離と関連するサイズを計算
                min_distance = float('inf')
                comp_i_size = 0.0
                comp_j_size = 0.0
                
                for comp_i in clusters[i]:
                    for comp_j in clusters[j]:
                        if comp_i in centers and comp_j in centers:
                            dist = (centers[comp_i] - centers[comp_j]).length
                            if dist < min_distance:
                                min_distance = dist
                                comp_i_size = component_sizes.get(comp_i, average_size)
                                comp_j_size = component_sizes.get(comp_j, average_size)
                
                # 2つのコンポーネントのサイズに基づいて適応的な閾値を計算
                # より大きいコンポーネントのサイズの一定割合を使用
                adaptive_threshold = max(comp_i_size, comp_j_size) * 0.5
                
                # 閾値の範囲を制限
                adaptive_threshold = max(min_threshold, min(max_threshold, adaptive_threshold))
                
                # 距離が閾値以下ならクラスターをマージ
                if min_distance <= adaptive_threshold:
                    clusters[i].extend(clusters[j])
                    clusters.pop(j)
                    merged = True
                    break
            
            if merged:
                break
    
    return clusters