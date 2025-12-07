import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
import numpy as np
from algo_utils.vertex_group_utils import check_uniform_weights
from algo_utils.component_utils import find_connected_components
from blender_utils.generate_weight_hash import generate_weight_hash
from math_utils.geometry_utils import calculate_component_size
from math_utils.obb_utils import calculate_obb
from algo_utils.component_utils import (
    cluster_components_by_adaptive_distance,
)
from mathutils import Vector


@dataclass
class ComponentInfo:
    indices: List[int]
    is_uniform: bool
    weights: Dict[str, float]
    weight_hash: str
    max_extent: float
    vertices_world: Optional[np.ndarray] = None


class _ComponentSeparationContext:
    def __init__(self, mesh_obj, clothing_armature, do_not_separate_names, clustering, clothing_avatar_data):
        self.mesh_obj = mesh_obj
        self.clothing_armature = clothing_armature
        self.do_not_separate_names = do_not_separate_names or []
        self.clustering = clustering
        self.clothing_avatar_data = clothing_avatar_data
        self.allowed_bones: Set[str] = set()
        self.non_uniform_components: List[List[int]] = []

    def prepare_allowed_bones(self):
        if not self.clothing_avatar_data:
            return

        target_humanoid_bones = ["Spine", "Chest", "Neck", "LeftBreast", "RightBreast"]
        humanoid_to_bone = {}

        if "humanoidBones" in self.clothing_avatar_data:
            for bone_data in self.clothing_avatar_data["humanoidBones"]:
                humanoid_name = bone_data.get("humanoidBoneName", "")
                bone_name = bone_data.get("boneName", "")
                if humanoid_name and bone_name:
                    humanoid_to_bone[humanoid_name] = bone_name

        for humanoid_bone in target_humanoid_bones:
            if humanoid_bone in humanoid_to_bone:
                self.allowed_bones.add(humanoid_to_bone[humanoid_bone])

        if "auxiliaryBones" in self.clothing_avatar_data:
            for aux_bone_data in self.clothing_avatar_data["auxiliaryBones"]:
                parent_humanoid = aux_bone_data.get("parentHumanoidBoneName", "")
                if parent_humanoid in target_humanoid_bones:
                    bone_name = aux_bone_data.get("boneName", "")
                    if bone_name:
                        self.allowed_bones.add(bone_name)

        print(f"Allowed bones for separation: {sorted(self.allowed_bones)}")

    def has_allowed_bone_weights(self, weights: Dict[str, float]) -> bool:
        if not self.allowed_bones:
            return True
        return any(bone_name in self.allowed_bones for bone_name in weights.keys())

    def find_components(self) -> List[List[int]]:
        components = find_connected_components(self.mesh_obj)
        if len(components) <= 1:
            return components
        print(f"Found {len(components)} connected components in {self.mesh_obj.name}")
        return components

    def analyze_components(self, components: List[List[int]]) -> List[ComponentInfo]:
        component_infos: List[ComponentInfo] = []
        weight_hash_do_not_separate: List[str] = []

        for i, component in enumerate(components):
            is_uniform, weights = check_uniform_weights(self.mesh_obj, component, self.clothing_armature)

            if is_uniform and weights:
                vertices_world = []
                for vert_idx in component:
                    vert_co = self.mesh_obj.data.vertices[vert_idx].co.copy()
                    vert_world = self.mesh_obj.matrix_world @ vert_co
                    vertices_world.append(np.array([vert_world.x, vert_world.y, vert_world.z]))

                vertices_world = np.array(vertices_world)
                _, extents = calculate_obb(vertices_world)

                if extents is not None:
                    max_extent = np.max(extents) * 2.0
                    weight_hash = generate_weight_hash(weights)

                    if max_extent < 0.0003:
                        print(f"Component {i} in {self.mesh_obj.name} is too small (max extent: {max_extent:.4f}), skipping")
                        component_infos.append(ComponentInfo(component, False, {}, "", max_extent))
                        continue

                    should_separate = True
                    temp_name = f"{self.mesh_obj.name}_Uniform_{i}"

                    for name_pattern in self.do_not_separate_names:
                        if name_pattern in temp_name:
                            should_separate = False
                            print(f"Component {i} in {self.mesh_obj.name} name matches do_not_separate pattern: {name_pattern}")
                            weight_hash_do_not_separate.append(weight_hash)
                            break

                    if should_separate:
                        for hash_val in weight_hash_do_not_separate:
                            if hash_val == weight_hash:
                                should_separate = False
                                print(f"Component {i} in {self.mesh_obj.name} weight hash matches do_not_separate pattern: {hash_val}")
                                break

                    if should_separate:
                        print(f"Component {i} in {self.mesh_obj.name} has uniform weights: {weight_hash} (max extent: {max_extent:.4f})")
                        component_infos.append(ComponentInfo(component, True, weights, weight_hash, max_extent, vertices_world))
                    else:
                        component_infos.append(ComponentInfo(component, False, {}, "", max_extent))
                else:
                    print(f"Component {i} in {self.mesh_obj.name} OBB calculation failed")
                    component_infos.append(ComponentInfo(component, False, {}, "", 0.0))
            else:
                print(f"Component {i} in {self.mesh_obj.name} does not have uniform weights")
                component_infos.append(ComponentInfo(component, False, {}, "", 0.0))

        return component_infos

    def group_components(self, component_infos: List[ComponentInfo]) -> Dict[str, List[Tuple[List[int], Optional[np.ndarray]]]]:
        weight_groups: Dict[str, List[Tuple[List[int], Optional[np.ndarray]]]] = {}
        non_uniform_components: List[List[int]] = []

        for info in component_infos:
            if info.is_uniform:
                weight_groups.setdefault(info.weight_hash, []).append((info.indices, info.vertices_world))
            else:
                non_uniform_components.append(info.indices)

        self.non_uniform_components = non_uniform_components
        return weight_groups

    def _duplicate_and_trim(self, keep_vertices: Set[int], name: str, copy_shape_keys: bool) -> bpy.types.Object:
        original_active = bpy.context.view_layer.objects.active

        bpy.ops.object.select_all(action='DESELECT')
        self.mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = self.mesh_obj
        bpy.ops.object.duplicate(linked=False)
        new_obj = bpy.context.active_object
        new_obj.name = name

        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        bpy.context.view_layer.objects.active = new_obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action='DESELECT')

        bpy.ops.object.mode_set(mode='OBJECT')
        for i, vert in enumerate(new_obj.data.vertices):
            vert.select = i in keep_vertices

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='INVERT')
        bpy.ops.mesh.delete(type='VERT')
        bpy.ops.object.mode_set(mode='OBJECT')

        if copy_shape_keys and self.mesh_obj.data.shape_keys:
            for key_block in self.mesh_obj.data.shape_keys.key_blocks:
                if key_block.name not in new_obj.data.shape_keys.key_blocks:
                    shape_key = new_obj.shape_key_add(name=key_block.name)
                    shape_key.value = key_block.value

        bpy.context.view_layer.objects.active = original_active
        return new_obj

    def _cluster_components(self, weight_hash: str, components_with_coords):
        component_coords = {}
        component_sizes = {}
        component_indices = {}

        for i, (component, vertices_world) in enumerate(components_with_coords):
            if vertices_world is not None and len(vertices_world) > 0:
                vectors = [Vector(v) for v in vertices_world]
                component_coords[i] = vectors
                component_sizes[i] = calculate_component_size(vectors)
                component_indices[i] = component

        clusters = cluster_components_by_adaptive_distance(component_coords, component_sizes)
        print(f"Weight hash {weight_hash} has {len(clusters)} spatial clusters")
        return clusters, component_indices

    def separate_uniform_components(self, weight_groups, component_infos: List[ComponentInfo]) -> List[bpy.types.Object]:
        uniform_objects: List[bpy.types.Object] = []

        if not self.clustering:
            return uniform_objects

        for weight_hash, components_with_coords in weight_groups.items():
            clusters, component_indices = self._cluster_components(weight_hash, components_with_coords)

            for cluster_idx, cluster in enumerate(clusters):
                first_component_id = -1
                for i, info in enumerate(component_infos):
                    if info.is_uniform and info.weight_hash == weight_hash:
                        for comp_idx in cluster:
                            if info.indices == component_indices.get(comp_idx):
                                first_component_id = i
                                break
                        if first_component_id >= 0:
                            break

                if first_component_id >= 0:
                    cluster_name = f"{self.mesh_obj.name}_Uniform_{first_component_id}_Cluster_{cluster_idx}"
                else:
                    cluster_name = f"{self.mesh_obj.name}_Uniform_Hash_{len(uniform_objects)}_Cluster_{cluster_idx}"

                should_separate = True
                for name_pattern in self.do_not_separate_names:
                    if name_pattern in cluster_name:
                        print(f"Component {cluster_idx} in {cluster_name} name matches do_not_separate pattern: {name_pattern}")
                        for component, _ in components_with_coords:
                            self.non_uniform_components.append(component)
                        should_separate = False
                        break
                if not should_separate:
                    continue

                keep_vertices = set()
                for comp_idx in cluster:
                    keep_vertices.update(component_indices[comp_idx])

                new_obj = self._duplicate_and_trim(keep_vertices, cluster_name, copy_shape_keys=True)
                uniform_objects.append(new_obj)

        return uniform_objects

    def build_non_uniform_object(self) -> Optional[bpy.types.Object]:
        if not self.non_uniform_components:
            return None

        keep_vertices = set()
        for component in self.non_uniform_components:
            keep_vertices.update(component)

        return self._duplicate_and_trim(keep_vertices, f"{self.mesh_obj.name}_NonUniform", copy_shape_keys=False)

    def report(self, uniform_objects: List[bpy.types.Object], non_uniform_obj: Optional[bpy.types.Object]):
        if non_uniform_obj:
            print(f"Non-separated object '{non_uniform_obj.name}' vertex count: {len(non_uniform_obj.data.vertices)}")
        else:
            print("No non-separated object.")

        for sep_obj in uniform_objects:
            print(f"Separated object '{sep_obj.name}' vertex count: {len(sep_obj.data.vertices)}")


def separate_and_combine_components(mesh_obj, clothing_armature, do_not_separate_names=None, clustering=True, clothing_avatar_data=None):
    """
    メッシュオブジェクト内の接続されていないコンポーネントを検出し、
    同じボーンウェイトパターンを持つものをグループ化して分離する
    """

    ctx = _ComponentSeparationContext(
        mesh_obj,
        clothing_armature,
        do_not_separate_names,
        clustering,
        clothing_avatar_data,
    )

    ctx.prepare_allowed_bones()
    components = ctx.find_components()
    if len(components) <= 1:
        return [], [mesh_obj]

    component_infos = ctx.analyze_components(components)
    weight_groups = ctx.group_components(component_infos)
    uniform_objects = ctx.separate_uniform_components(weight_groups, component_infos)
    non_uniform_obj = ctx.build_non_uniform_object()

    separated_objects = uniform_objects
    non_separated_objects = [non_uniform_obj] if non_uniform_obj else []

    ctx.report(separated_objects, non_uniform_obj)
    return separated_objects, non_separated_objects
