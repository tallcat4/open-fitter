import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

import bmesh
import bpy
from algo_utils.create_vertex_neighbors_array import create_vertex_neighbors_array
from algo_utils.vertex_group_utils import custom_max_vertex_group_numpy
from algo_utils.get_humanoid_and_auxiliary_bone_groups import (
    get_humanoid_and_auxiliary_bone_groups,
)
from math_utils.geometry_utils import calculate_component_size
from math_utils.obb_utils import calculate_obb_from_points
from math_utils.cluster_components_by_adaptive_distance import (
    cluster_components_by_adaptive_distance,
)
from mathutils import Vector

ComponentPattern = Tuple[Tuple[Tuple[str, float], ...], Tuple[Tuple[str, float], ...]]
OBBDataEntry = Dict[str, object]


@dataclass
class WeightTransferContext:
    target_obj: object
    armature: object
    base_avatar_data: Dict[str, object]
    clothing_avatar_data: Dict[str, object]
    field_path: str
    clothing_armature: object
    blend_shape_settings: List[Dict[str, object]]
    cloth_metadata: Dict[str, object] | None = None
    base_obj: object | None = None
    left_base_obj: object | None = None
    right_base_obj: object | None = None
    existing_target_groups: Set[str] = field(default_factory=set)
    original_vertex_weights: Dict[int, Dict[str, float]] | None = None
    component_patterns: Dict[ComponentPattern, List[List[int]]] | None = None
    obb_data: List[OBBDataEntry] | None = None
    neighbors_info: object | None = None
    offsets: object | None = None
    num_verts: int | None = None


def _apply_blend_shape_settings(ctx: WeightTransferContext):
    base_obj = ctx.base_obj
    left_base_obj = ctx.left_base_obj
    right_base_obj = ctx.right_base_obj
    if not base_obj or not base_obj.data.shape_keys:
        return
    for blend_shape_setting in ctx.blend_shape_settings:
        name = blend_shape_setting['name']
        value = blend_shape_setting['value']
        if name in base_obj.data.shape_keys.key_blocks:
            base_obj.data.shape_keys.key_blocks[name].value = value
            left_base_obj.data.shape_keys.key_blocks[name].value = value
            right_base_obj.data.shape_keys.key_blocks[name].value = value
            print(f"Set {name} to {value}")


def _get_existing_target_groups(ctx: WeightTransferContext):
    target_groups = get_humanoid_and_auxiliary_bone_groups(ctx.base_avatar_data)
    ctx.existing_target_groups = {vg.name for vg in ctx.target_obj.vertex_groups if vg.name in target_groups}
    return ctx.existing_target_groups


def _store_original_vertex_weights(ctx: WeightTransferContext):
    import time
    start_time = time.time()
    original_vertex_weights = {}
    for vert_idx, vert in enumerate(ctx.target_obj.data.vertices):
        weights = {}
        for group_name in ctx.existing_target_groups:
            weight = 0.0
            for g in vert.groups:
                if ctx.target_obj.vertex_groups[g.group].name == group_name:
                    weight = g.weight
                    break
            if weight > 0.0001:
                weights[group_name] = weight
        original_vertex_weights[vert_idx] = weights
    ctx.original_vertex_weights = original_vertex_weights
    print(f"元のウェイト保存時間: {time.time() - start_time:.2f}秒")
    return original_vertex_weights


def _normalize_component_patterns(ctx: WeightTransferContext, component_patterns):
    import time
    start_time = time.time()
    new_component_patterns = {}

    for pattern, components in component_patterns.items():
        if not any(group in ctx.existing_target_groups for group in pattern):
            all_deform_groups = set(ctx.existing_target_groups)
            if ctx.clothing_armature:
                all_deform_groups.update(bone.name for bone in ctx.clothing_armature.data.bones)

            non_humanoid_difference_group = ctx.target_obj.vertex_groups.get("NonHumanoidDifference")
            is_non_humanoid_difference_group = False
            max_weight = 0.0
            if non_humanoid_difference_group:
                for component in components:
                    for vert_idx in component:
                        vert = ctx.target_obj.data.vertices[vert_idx]
                        for g in vert.groups:
                            if g.group == non_humanoid_difference_group.index and g.weight > 0.0001:
                                is_non_humanoid_difference_group = True
                                if g.weight > max_weight:
                                    max_weight = g.weight
            if is_non_humanoid_difference_group:
                max_avg_pattern = {}
                count = 0
                for component in components:
                    for vert_idx in component:
                        vert = ctx.target_obj.data.vertices[vert_idx]
                        for g in vert.groups:
                            if g.group == non_humanoid_difference_group.index and g.weight == max_weight:
                                for g2 in vert.groups:
                                    if ctx.target_obj.vertex_groups[g2.group].name in all_deform_groups:
                                        if g2.group not in max_avg_pattern:
                                            max_avg_pattern[g2.group] = g2.weight
                                        else:
                                            max_avg_pattern[g2.group] += g2.weight
                                count += 1
                                break
                if count > 0:
                    for group_name, weight in max_avg_pattern.items():
                        max_avg_pattern[group_name] = weight / count
                for component in components:
                    for vert_idx in component:
                        vert = ctx.target_obj.data.vertices[vert_idx]
                        for g in vert.groups:
                            if g.group not in max_avg_pattern and ctx.target_obj.vertex_groups[g.group].name in all_deform_groups:
                                g.weight = 0.0
                        for max_group_id, max_weight in max_avg_pattern.items():
                            group = ctx.target_obj.vertex_groups[max_group_id]
                            group.add([vert_idx], max_weight, 'REPLACE')
            continue

        original_pattern_dict = {group_name: weight for group_name, weight in pattern}
        original_pattern = tuple(sorted((k, v) for k, v in original_pattern_dict.items() if k in ctx.existing_target_groups))

        all_weights = {group: [] for group in ctx.existing_target_groups}
        all_vertices = set()

        for component in components:
            for vert_idx in component:
                all_vertices.add(vert_idx)
                vert = ctx.target_obj.data.vertices[vert_idx]
                for group_name in ctx.existing_target_groups:
                    weight = 0.0
                    for g in vert.groups:
                        if ctx.target_obj.vertex_groups[g.group].name == group_name:
                            weight = g.weight
                            break
                    all_weights[group_name].append(weight)

        avg_weights = {}
        for group_name, weights in all_weights.items():
            avg_weights[group_name] = sum(weights) / len(weights) if weights else 0.0

        for vert_idx in all_vertices:
            for group_name, avg_weight in avg_weights.items():
                group = ctx.target_obj.vertex_groups[group_name]
                if avg_weight > 0.0001:
                    group.add([vert_idx], avg_weight, 'REPLACE')
                else:
                    group.add([vert_idx], 0.0, 'REPLACE')

        new_pattern = tuple(sorted((k, round(v, 4)) for k, v in avg_weights.items() if v > 0.0001))
        new_component_patterns[(new_pattern, original_pattern)] = components

    print(f"コンポーネントパターン正規化時間: {time.time() - start_time:.2f}秒")
    ctx.component_patterns = new_component_patterns
    return new_component_patterns


def _collect_obb_data(ctx: WeightTransferContext):
    import time
    obb_data = []

    start_time = time.time()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    ctx.target_obj.select_set(True)
    bpy.context.view_layer.objects.active = ctx.target_obj

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = ctx.target_obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.data

    if len(eval_mesh.vertices) == 0:
        print(f"警告: {ctx.target_obj.name} の評価済みメッシュに頂点がありません。OBB計算をスキップします。")
        return obb_data

    all_rigid_component_vertices = set()
    for (_, _), components in ctx.component_patterns.items():
        for component in components:
            all_rigid_component_vertices.update(component)

    component_count = 0
    for (new_pattern, original_pattern), components in ctx.component_patterns.items():
        pattern_weights = {group_name: weight for group_name, weight in new_pattern}
        original_pattern_weights = {group_name: weight for group_name, weight in original_pattern}

        component_coords = {}
        component_sizes = {}

        for component_idx, component in enumerate(components):
            coords = []
            for vert_idx in component:
                if vert_idx < len(eval_mesh.vertices):
                    coords.append(eval_obj.matrix_world @ eval_mesh.vertices[vert_idx].co)
            if coords:
                component_coords[component_idx] = coords
                size = calculate_component_size(coords)
                component_sizes[component_idx] = size

        if not component_coords:
            continue

        clusters = cluster_components_by_adaptive_distance(component_coords, component_sizes)

        for cluster_idx, cluster in enumerate(clusters):
            cluster_vertices = set()
            cluster_coords = []

            for comp_idx in cluster:
                for vert_idx in components[comp_idx]:
                    cluster_vertices.add(vert_idx)
                    if vert_idx < len(eval_mesh.vertices):
                        cluster_coords.append(eval_obj.matrix_world @ eval_mesh.vertices[vert_idx].co)

            if len(cluster_coords) < 3:
                print(f"警告: パターン {new_pattern} のクラスター {cluster_idx} の有効な頂点が少なすぎます（{len(cluster_coords)}点）。スキップします。")
                continue

            obb = calculate_obb_from_points(cluster_coords)
            if obb is None:
                print(f"警告: パターン {new_pattern} のクラスター {cluster_idx} のOBB計算に失敗しました。スキップします。")
                continue

            obb['radii'] = [radius * 1.3 for radius in obb['radii']]

            vertices_in_obb = []
            for vert_idx, vert in enumerate(ctx.target_obj.data.vertices):
                if vert_idx in all_rigid_component_vertices or vert_idx >= len(eval_mesh.vertices):
                    continue
                try:
                    vert_world = eval_obj.matrix_world @ eval_mesh.vertices[vert_idx].co
                    relative_pos = vert_world - Vector(obb['center'])
                    projections = [abs(relative_pos.dot(Vector(obb['axes'][:, i]))) for i in range(3)]
                    if all(proj <= radius for proj, radius in zip(projections, obb['radii'])):
                        vertices_in_obb.append(vert_idx)
                except Exception as e:
                    print(f"警告: 頂点 {vert_idx} のOBBチェック中にエラーが発生しました: {e}")
                    continue

            if not vertices_in_obb:
                print(f"警告: パターン {new_pattern} のクラスター {cluster_idx} のOBB内に頂点が見つかりませんでした。スキップします。")
                continue

            obb_data.append({
                'component_vertices': cluster_vertices,
                'vertices_in_obb': vertices_in_obb,
                'component_id': component_count,
                'pattern_weights': pattern_weights,
                'original_pattern_weights': original_pattern_weights
            })
            component_count += 1

    print(f"OBBデータ収集時間: {time.time() - start_time:.2f}秒")
    ctx.obb_data = obb_data
    return obb_data


def _process_obb_groups(ctx: WeightTransferContext):
    import time
    start_time = time.time()

    neighbors_info, offsets, num_verts = create_vertex_neighbors_array(ctx.target_obj, expand_distance=0.02, sigma=0.00659)
    ctx.neighbors_info = neighbors_info
    ctx.offsets = offsets
    ctx.num_verts = num_verts
    print(f"頂点近傍リスト作成時間: {time.time() - start_time:.2f}秒")

    start_time = time.time()
    bpy.ops.object.mode_set(mode='EDIT')

    for obb_idx, data in enumerate(ctx.obb_data):
        obb_start = time.time()
        connected_group = ctx.target_obj.vertex_groups.new(name=f"Connected_{data['component_id']}")
        print(f"    Connected頂点グループ作成: {connected_group.name}")

        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(ctx.target_obj.data)
        bm.verts.ensure_lookup_table()

        obb_vertex_select_start = time.time()
        for vert_idx in data['vertices_in_obb']:
            if vert_idx < len(bm.verts):
                bm.verts[vert_idx].select = True
        bmesh.update_edit_mesh(ctx.target_obj.data)
        print(f"    OBB内頂点選択時間: {time.time() - obb_vertex_select_start:.2f}秒")

        edge_loop_start = time.time()
        initial_selection = {v.index for v in bm.verts if v.select}

        if initial_selection:
            selected_edges = [e for e in bm.edges if all(v.select for v in e.verts)]
            complete_loops = set()
            edge_count = len(selected_edges)
            print(f"    処理対象エッジ数: {edge_count}")

            for edge_idx, edge in enumerate(selected_edges):
                if edge_idx % 100 == 0 and edge_idx > 0:
                    print(f"    エッジ処理進捗: {edge_idx}/{edge_count} ({edge_idx/edge_count*100:.1f}%)")

                bpy.ops.mesh.select_all(action='DESELECT')
                edge.select = True
                bmesh.update_edit_mesh(ctx.target_obj.data)
                bpy.ops.mesh.loop_multi_select(ring=False)

                bm = bmesh.from_edit_mesh(ctx.target_obj.data)
                loop_verts = {v.index for v in bm.verts if v.select}

                is_closed_loop = True
                for v in bm.verts:
                    if v.select:
                        selected_edge_count = sum(1 for e in v.link_edges if e.select)
                        total_edge_count = len(v.link_edges)
                        if selected_edge_count != 2 or total_edge_count != 4:
                            is_closed_loop = False
                            break

                if is_closed_loop:
                    is_similar_pattern = True
                    pattern_weights = data['original_pattern_weights']

                    for vert_idx in loop_verts:
                        if vert_idx in ctx.original_vertex_weights:
                            orig_weights = ctx.original_vertex_weights[vert_idx]
                            similarity_score = 0.0
                            total_weight = 0.0

                            for group_name, pattern_weight in pattern_weights.items():
                                orig_weight = orig_weights.get(group_name, 0.0)
                                diff = abs(pattern_weight - orig_weight)
                                similarity_score += diff
                                total_weight += pattern_weight

                            if total_weight > 0:
                                normalized_score = similarity_score / total_weight
                                if normalized_score > 0.05:
                                    is_similar_pattern = False
                                    break

                    if is_similar_pattern:
                        complete_loops.update(loop_verts)

            bpy.ops.mesh.select_all(action='DESELECT')
            bm = bmesh.from_edit_mesh(ctx.target_obj.data)
            for vert in bm.verts:
                if vert.index in complete_loops:
                    vert.select = True
            bmesh.update_edit_mesh(ctx.target_obj.data)

        print(f"    エッジループ検出時間: {time.time() - edge_loop_start:.2f}秒")

        select_more_start = time.time()
        for _ in range(1):
            bpy.ops.mesh.select_more()
        bm = bmesh.from_edit_mesh(ctx.target_obj.data)
        selected_verts = [v.index for v in bm.verts if v.select]
        print(f"    選択範囲拡大時間: {time.time() - select_more_start:.2f}秒")

        if len(selected_verts) == 0:
            print(f"警告: OBB {obb_idx} 内に頂点が見つかりませんでした。スキップします。")
            continue

        mode_switch_start = time.time()
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"    モード切替時間: {time.time() - mode_switch_start:.2f}秒")

        weight_assign_start = time.time()
        for vert_idx in selected_verts:
            if vert_idx not in data['component_vertices']:
                connected_group.add([vert_idx], 1.0, 'REPLACE')
        print(f"    ウェイト割り当て時間: {time.time() - weight_assign_start:.2f}秒")

        smoothing_start = time.time()
        bpy.ops.object.select_all(action='DESELECT')
        ctx.target_obj.select_set(True)
        bpy.context.view_layer.objects.active = ctx.target_obj

        for i, group in enumerate(ctx.target_obj.vertex_groups):
            ctx.target_obj.vertex_groups.active_index = i
            if group.name == f"Connected_{data['component_id']}":
                break

        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        smooth_op_start = time.time()
        bpy.ops.object.vertex_group_smooth(factor=0.5, repeat=3, expand=0.5)
        print(f"    標準スムージング時間: {time.time() - smooth_op_start:.2f}秒")

        custom_smooth_start = time.time()
        custom_max_vertex_group_numpy(ctx.target_obj, f"Connected_{data['component_id']}", ctx.neighbors_info, ctx.offsets, ctx.num_verts, repeat=3, weight_factor=1.0)
        print(f"    カスタムスムージング時間: {time.time() - custom_smooth_start:.2f}秒")

        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"    スムージング処理時間: {time.time() - smoothing_start:.2f}秒")

        decay_start = time.time()
        connected_group = ctx.target_obj.vertex_groups[f"Connected_{data['component_id']}"]
        original_pattern_weights = data['original_pattern_weights']

        for vert_idx, vert in enumerate(ctx.target_obj.data.vertices):
            if vert_idx in data['component_vertices']:
                connected_group.add([vert_idx], 0.0, 'REPLACE')
                continue
            if vert_idx in ctx.original_vertex_weights:
                orig_weights = ctx.original_vertex_weights[vert_idx]
                similarity_score = 0.0
                total_weight = 0.0

                for group_name, pattern_weight in original_pattern_weights.items():
                    orig_weight = orig_weights.get(group_name, 0.0)
                    diff = abs(pattern_weight - orig_weight)
                    similarity_score += diff
                    total_weight += pattern_weight

                if total_weight > 0:
                    normalized_score = similarity_score / total_weight
                    decay_factor = 1.0 - min(normalized_score * 3.33333, 1.0)

                    connected_weight = 0.0
                    for g in ctx.target_obj.data.vertices[vert_idx].groups:
                        if g.group == connected_group.index:
                            connected_weight = g.weight
                            break

                    if normalized_score > 0.3:
                        connected_group.add([vert_idx], 0.0, 'REPLACE')
                    else:
                        connected_group.add([vert_idx], connected_weight * decay_factor, 'REPLACE')
                else:
                    connected_group.add([vert_idx], 0.0, 'REPLACE')
        print(f"    ウェイト減衰時間: {time.time() - decay_start:.2f}秒")

        print(f"  OBB {obb_idx+1}/{len(ctx.obb_data)} 処理時間: {time.time() - obb_start:.2f}秒")

        if obb_idx < len(ctx.obb_data) - 1:
            bpy.ops.object.mode_set(mode='EDIT')

    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"OBB処理時間: {time.time() - start_time:.2f}秒")


def _synthesize_weights(ctx: WeightTransferContext):
    import time
    start_time = time.time()
    connected_groups = [vg for vg in ctx.target_obj.vertex_groups if vg.name.startswith("Connected_")]

    if not connected_groups:
        print(f"ウェイト合成時間: {time.time() - start_time:.2f}秒")
        return

    for vert in ctx.target_obj.data.vertices:
        skip = False
        for (_, _), components in ctx.component_patterns.items():
            for component in components:
                if vert.index in component:
                    skip = True
                    break
            if skip:
                break
        if skip:
            continue

        connected_weights = {}
        total_weight = 0.0

        for connected_group in connected_groups:
            weight = 0.0
            for g in vert.groups:
                if g.group == connected_group.index:
                    weight = g.weight
                    break

            if weight > 0:
                component_id = int(connected_group.name.split('_')[1])
                for data in ctx.obb_data:
                    if data['component_id'] == component_id:
                        pattern_tuple = tuple(sorted((k, v) for k, v in data['pattern_weights'].items() if v > 0.0001))
                        connected_weights[pattern_tuple] = weight
                        total_weight += weight
                        break

        if total_weight <= 0:
            continue

        combined_weights = {}
        for pattern, weight in connected_weights.items():
            normalized_weight = weight / total_weight
            for group_name, value in pattern:
                if group_name not in combined_weights:
                    combined_weights[group_name] = 0.0
                combined_weights[group_name] += value * normalized_weight

        factor = min(total_weight, 1.0)
        existing_weights = {}
        for group_name in ctx.existing_target_groups:
            if group_name in ctx.target_obj.vertex_groups:
                group = ctx.target_obj.vertex_groups[group_name]
                weight = 0.0
                for g in vert.groups:
                    if g.group == group.index:
                        weight = g.weight
                        break
                existing_weights[group_name] = weight

        new_weights = {}
        for group_name, weight in existing_weights.items():
            if group_name in ctx.target_obj.vertex_groups and group_name in ctx.existing_target_groups:
                new_weights[group_name] = weight * (1.0 - factor)

        for pattern, weight in connected_weights.items():
            normalized_weight = weight / total_weight
            if total_weight < 1.0:
                normalized_weight = weight
            for group_name, value in pattern:
                if group_name in ctx.target_obj.vertex_groups and group_name in ctx.existing_target_groups:
                    compornent_weight = value * normalized_weight
                    new_weights[group_name] = new_weights[group_name] + compornent_weight

        for group_name, weight in new_weights.items():
            if weight > 1.0:
                weight = 1.0
            group = ctx.target_obj.vertex_groups[group_name]
            group.add([vert.index], weight, 'REPLACE')

    print(f"ウェイト合成時間: {time.time() - start_time:.2f}秒")
