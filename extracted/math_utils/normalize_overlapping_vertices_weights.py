import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass

import bpy
from algo_utils.get_humanoid_and_auxiliary_bone_groups import (
    get_humanoid_and_auxiliary_bone_groups,
)
from blender_utils.subdivide_selected_vertices import subdivide_selected_vertices
from mathutils import Vector


@dataclass
class OverlapContext:
    target_groups: list
    distance_threshold: float = 0.0001


class _OverlapNormalizationContext:
    """Orchestrates overlapping-vertex weight normalization per mesh."""

    def __init__(self, clothing_meshes, base_avatar_data, overlap_attr_name, world_pos_attr_name):
        self.clothing_meshes = clothing_meshes
        self.overlap_attr_name = overlap_attr_name
        self.world_pos_attr_name = world_pos_attr_name
        self.original_active = bpy.context.view_layer.objects.active
        self.ctx = OverlapContext(
            target_groups=get_humanoid_and_auxiliary_bone_groups(base_avatar_data),
            distance_threshold=0.0001,
        )
        self.valid_meshes = []

    def filter_valid_meshes(self):
        self.valid_meshes = _filter_valid_meshes(
            self.clothing_meshes, self.overlap_attr_name, self.world_pos_attr_name
        )
        return self.valid_meshes

    def _process_mesh(self, mesh_obj):
        overlap_attr = mesh_obj.data.attributes[self.overlap_attr_name]
        world_pos_attr = mesh_obj.data.attributes[self.world_pos_attr_name]

        work_obj = _duplicate_work_object(mesh_obj)
        overlapping_verts_ids = _find_overlapping_vertex_indices(overlap_attr)

        if not overlapping_verts_ids:
            print(f"警告: {mesh_obj.name}に重なっている頂点が見つかりません。処理をスキップします。")
            bpy.data.objects.remove(work_obj, do_unlink=True)
            return

        subdivide_selected_vertices(work_obj.name, overlapping_verts_ids, level=2)
        subdiv_overlap_attr = work_obj.data.attributes[self.overlap_attr_name]
        subdiv_overlapping_verts_ids = _find_overlapping_vertex_indices(subdiv_overlap_attr)
        subdiv_world_pos_attr = work_obj.data.attributes[self.world_pos_attr_name]

        subdiv_original_world_positions = _collect_world_positions(
            subdiv_world_pos_attr, subdiv_overlapping_verts_ids
        )
        overlapping_groups = _group_vertices_by_position(
            subdiv_overlapping_verts_ids,
            subdiv_original_world_positions,
            self.ctx.distance_threshold,
        )
        _, vert_weights = _compute_reference_weights(
            work_obj,
            mesh_obj,
            self.ctx.target_groups,
            overlapping_groups,
        )

        bpy.ops.object.select_all(action='DESELECT')
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_obj

        updated_count = _apply_weights_to_original(
            mesh_obj,
            world_pos_attr,
            overlapping_verts_ids,
            subdiv_overlapping_verts_ids,
            subdiv_original_world_positions,
            vert_weights,
            self.ctx.distance_threshold,
        )

        bpy.data.objects.remove(work_obj, do_unlink=True)
        print(f"{mesh_obj.name}の{updated_count}個の頂点のウェイトを正規化しました。")

    def process_all(self):
        if not self.valid_meshes:
            print(
                f"警告: {self.overlap_attr_name}と{self.world_pos_attr_name}属性を持つメッシュが見つかりません。処理をスキップします。"
            )
            return

        for mesh_obj in self.valid_meshes:
            self._process_mesh(mesh_obj)

    def restore_active(self):
        bpy.context.view_layer.objects.active = self.original_active


def _filter_valid_meshes(clothing_meshes, overlap_attr_name, world_pos_attr_name):
    return [
        mesh
        for mesh in clothing_meshes
        if (
            overlap_attr_name in mesh.data.attributes
            and world_pos_attr_name in mesh.data.attributes
            and "InpaintMask" in mesh.vertex_groups
        )
    ]


def _duplicate_work_object(mesh_obj):
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.duplicate(linked=False)
    work_obj = bpy.context.active_object
    work_obj.name = f"{mesh_obj.name}_OverlapWork"
    return work_obj


def _find_overlapping_vertex_indices(overlap_attr, threshold=0.9999):
    return [i for i, data in enumerate(overlap_attr.data) if data.value > threshold]


def _collect_world_positions(world_pos_attr, vertex_indices):
    return [Vector(world_pos_attr.data[vert_idx].vector) for vert_idx in vertex_indices]


def _group_vertices_by_position(vertex_indices, positions, distance_threshold):
    overlapping_groups = {}
    for orig_idx, world_pos in zip(vertex_indices, positions):
        for group_id, (group_pos, members) in overlapping_groups.items():
            if (world_pos - group_pos).length <= distance_threshold:
                members.append(orig_idx)
                break
        else:
            group_id = len(overlapping_groups)
            overlapping_groups[group_id] = (world_pos, [orig_idx])
    return overlapping_groups


def _compute_reference_weights(work_obj, mesh_obj, target_groups, overlapping_groups):
    reference_weights = {}
    vert_weights = {}

    for group_id, (group_pos, member_indices) in overlapping_groups.items():
        member_inpaint_weights = []
        for idx in member_indices:
            inpaint_weight = 0.0
            if "InpaintMask" in work_obj.vertex_groups:
                inpaint_group = work_obj.vertex_groups["InpaintMask"]
                for g in work_obj.data.vertices[idx].groups:
                    if g.group == inpaint_group.index:
                        inpaint_weight = g.weight
                        break
            member_inpaint_weights.append((idx, inpaint_weight))

        member_inpaint_weights.sort(key=lambda x: x[1])

        if not member_inpaint_weights:
            continue

        reference_idx = member_inpaint_weights[0][0]
        ref_weights = {}
        for group_name in target_groups:
            if group_name in work_obj.vertex_groups:
                group = work_obj.vertex_groups[group_name]
                weight = 0.0
                for g in work_obj.data.vertices[reference_idx].groups:
                    if g.group == group.index:
                        weight = g.weight
                        break
                ref_weights[group_name] = weight

        reference_weights[group_id] = ref_weights

        min_inpaint_weight = member_inpaint_weights[0][1]
        same_weight_vert_ids = [v[0] for v in member_inpaint_weights if abs(v[1] - min_inpaint_weight) < 0.0001]
        same_weight_verts = [work_obj.data.vertices[idx] for idx in same_weight_vert_ids]

        if len(same_weight_verts) > 1:
            avg_weights = {}
            for group_name in target_groups:
                if group_name in work_obj.vertex_groups:
                    weights_sum = 0.0
                    count = 0
                    for v in same_weight_verts:
                        weight = 0.0
                        for g in v.groups:
                            if g.group == mesh_obj.vertex_groups[group_name].index:
                                weight = g.weight
                                break
                        if weight > 0:
                            weights_sum += weight
                            count += 1
                    if count > 0:
                        avg_weights[group_name] = weights_sum / count
            reference_weights[group_id] = avg_weights

        for vert_idx in member_indices:
            vert_weights[vert_idx] = reference_weights[group_id].copy()

    return reference_weights, vert_weights


def _apply_weights_to_original(
    mesh_obj,
    world_pos_attr,
    overlapping_verts_ids,
    subdiv_overlapping_verts_ids,
    subdiv_original_world_positions,
    vert_weights,
    distance_threshold,
):
    updated_count = 0
    for orig_idx in overlapping_verts_ids:
        orig_world_pos = Vector(world_pos_attr.data[orig_idx].vector)
        closest_idx = None
        min_dist = float("inf")

        for subdiv_idx, subdiv_pos in zip(subdiv_overlapping_verts_ids, subdiv_original_world_positions):
            dist = (orig_world_pos - subdiv_pos).length
            if dist < min_dist:
                min_dist = dist
                closest_idx = subdiv_idx

        if closest_idx is not None and closest_idx in vert_weights and min_dist < distance_threshold:
            for group_name, weight in vert_weights[closest_idx].items():
                if group_name in mesh_obj.vertex_groups:
                    mesh_obj.vertex_groups[group_name].add([orig_idx], weight, "REPLACE")
            updated_count += 1

    return updated_count


def normalize_overlapping_vertices_weights(clothing_meshes, base_avatar_data, overlap_attr_name="Overlapped", world_pos_attr_name="OriginalWorldPosition"):
    """
    Overlapped属性が1となる頂点で構成される面およびエッジのみを対象に
    重なっている頂点のウェイトを正規化する
    
    Parameters:
        clothing_meshes: 処理対象の衣装メッシュのリスト
        base_avatar_data: ベースアバターデータ
        overlap_attr_name: 重なり検出フラグの属性名
        world_pos_attr_name: ワールド座標が保存された属性名
    """
    print("Normalizing weights for overlapping vertices using custom attributes...")

    ctx = _OverlapNormalizationContext(
        clothing_meshes,
        base_avatar_data,
        overlap_attr_name,
        world_pos_attr_name,
    )

    try:
        ctx.filter_valid_meshes()
        ctx.process_all()
    finally:
        ctx.restore_active()
        print("重なっている頂点のウェイト正規化が完了しました。")
