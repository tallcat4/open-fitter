import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from blender_utils.blendshape_utils import (
    calculate_blendshape_settings_difference,
)
from mathutils.bvhtree import BVHTree
from typing import Dict, Optional
from typing import Optional
import bmesh
import bpy
import mathutils
import os
import sys

# Merged from find_nearest_parent_with_pose.py

def find_nearest_parent_with_pose(bone_name: str, 
                                bone_parents: Dict[str, str], 
                                bone_to_humanoid: Dict[str, str],
                                pose_data: dict) -> Optional[str]:
    """
    指定されたボーンの親を辿り、ポーズデータを持つ最も近い親のHumanoidボーン名を返す

    Parameters:
        bone_name (str): 開始ボーン名
        bone_parents (Dict[str, str]): ボーンの親子関係辞書
        bone_to_humanoid (Dict[str, str]): ボーン名からHumanoidボーン名への変換辞書
        pose_data (dict): ポーズデータ

    Returns:
        Optional[str]: 見つかった親のHumanoidボーン名、見つからない場合はNone
    """
    current_bone = bone_name
    while current_bone in bone_parents:
        parent_bone = bone_parents[current_bone]
        if parent_bone in bone_to_humanoid:
            parent_humanoid = bone_to_humanoid[parent_bone]
            if parent_humanoid in pose_data:
                return parent_humanoid
        current_bone = parent_bone
    return None

# Merged from find_closest_vertices_brute_force.py

def find_closest_vertices_brute_force(positions, vertices_world, max_distance=0.0001):
    """
    複数の位置に対して最も近い頂点を総当たりで探索
    
    Args:
        positions: 検索する位置のリスト（ワールド座標）
        vertices_world: メッシュの頂点のワールド座標のリスト
        max_distance: 許容する最大距離
    Returns:
        Dict[int, float]: 頂点インデックスをキーとし、距離を値とする辞書
    """
    valid_mappings = {}
    
    # 各検索位置について
    for i, search_pos in enumerate(positions):
        min_distance = float('inf')
        closest_idx = None
        
        # すべてのメッシュ頂点と距離を計算
        for vertex_idx, vertex_pos in enumerate(vertices_world):
            # ユークリッド距離を計算
            distance = ((search_pos[0] - vertex_pos[0])**2 + 
                       (search_pos[1] - vertex_pos[1])**2 + 
                       (search_pos[2] - vertex_pos[2])**2)**0.5
            
            # より近い頂点が見つかった場合は更新
            if distance < min_distance:
                min_distance = distance
                closest_idx = vertex_idx
        
        # 最大距離以内の場合のみマッピングを追加
        if closest_idx is not None and min_distance < max_distance:
            valid_mappings[i] = closest_idx
    
    return valid_mappings

# Merged from find_humanoid_parent_in_hierarchy.py

def find_humanoid_parent_in_hierarchy(bone_name: str, clothing_avatar_data: dict, base_avatar_data: dict) -> Optional[str]:
    """
    clothing_avatar_dataのboneHierarchyでbone_nameから親を辿り、base_armatureにも存在する最初のhumanoidボーンを返す
    
    Parameters:
        bone_name: 開始ボーン名
        clothing_avatar_data: 衣装のアバターデータ
        base_avatar_data: ベースのアバターデータ
        
    Returns:
        Optional[str]: 見つかった親のHumanoidボーン名、見つからない場合はNone
    """
    # clothing_avatar_dataのhumanoidBonesからbone_nameのhumanoidBoneNameを取得
    clothing_bones_to_humanoid = {bone_map["boneName"]: bone_map["humanoidBoneName"] 
                                for bone_map in clothing_avatar_data["humanoidBones"]}
    base_humanoid_bones = {bone_map["humanoidBoneName"] for bone_map in base_avatar_data["humanoidBones"]}
    
    def find_bone_in_hierarchy(hierarchy_node, target_name):
        """階層内でボーンを探す再帰関数"""
        if hierarchy_node["name"] == target_name:
            return hierarchy_node
        for child in hierarchy_node.get("children", []):
            result = find_bone_in_hierarchy(child, target_name)
            if result:
                return result
        return None
    
    def find_parent_path(hierarchy_node, target_name, path=[]):
        """ターゲットボーンまでのパスを見つける再帰関数"""
        current_path = path + [hierarchy_node["name"]]
        if hierarchy_node["name"] == target_name:
            return current_path
        for child in hierarchy_node.get("children", []):
            result = find_parent_path(child, target_name, current_path)
            if result:
                return result
        return None
    
    # boneHierarchyでbone_nameまでのパスを取得
    bone_hierarchy = clothing_avatar_data.get("boneHierarchy")
    if not bone_hierarchy:
        return None
    
    path = find_parent_path(bone_hierarchy, bone_name)
    if not path:
        return None
    
    # パスを逆順にして親から辿る
    path.reverse()
    
    # 自分から親に向かってhumanoidボーンを探す
    for parent_bone_name in path:
        if parent_bone_name in clothing_bones_to_humanoid:
            humanoid_name = clothing_bones_to_humanoid[parent_bone_name]
            if humanoid_name in base_humanoid_bones:
                return humanoid_name
    
    return None

# Merged from find_best_matching_target_settings.py

def find_best_matching_target_settings(source_label: str, 
                                     all_target_settings: dict, 
                                     all_target_mask_bones: dict,
                                     source_settings: list,
                                     blend_shape_fields: dict,
                                     config_dir: str,
                                     mask_bones: list = None) -> tuple:
    """
    sourceBlendShapeSettingsに最も近いtargetBlendShapeSettingsを見つける
    
    Parameters:
        all_target_settings: ラベルごとのtargetBlendShapeSettingsの辞書
        all_target_mask_bones: ラベルごとのmaskBonesの辞書
        source_settings: sourceBlendShapeSettings
        blend_shape_fields: BlendShapeFieldsの辞書
        config_dir: 設定ファイルのディレクトリ
        mask_bones: 比較対象のmaskBones
        
    Returns:
        tuple: (best_label, best_target_settings)
    """
    best_label = None
    best_target_settings = None
    min_difference = float('inf')
    
    for label, target_settings in all_target_settings.items():
        # mask_bonesとall_target_mask_bones[label]の間に共通要素があるかチェック
        if mask_bones is not None and label in all_target_mask_bones:
            target_mask_bones = all_target_mask_bones[label]
            if target_mask_bones is not None:
                # setに変換して共通要素をチェック
                mask_bones_set = set(mask_bones)
                target_mask_bones_set = set(target_mask_bones)
                
                # 共通要素がない場合はスキップ
                if not mask_bones_set.intersection(target_mask_bones_set):
                    print(f"label: {label} - skip: no common mask_bones")
                    continue
        
        difference = calculate_blendshape_settings_difference(
            target_settings, source_settings, blend_shape_fields, config_dir
        )

        # labelとsource_labelから___idを取り除いて比較
        label_without_id = label.split('___')[0] if '___' in label else label
        source_label_without_id = source_label.split('___')[0] if '___' in source_label else source_label
        
        # labelがsource_labelの場合は、差異を1.5で割り優先度を上げる
        if label_without_id == source_label_without_id:
            difference = difference / 1.5
        else:
            difference = difference + 0.00001
        
        print(f"label: {label} difference: {difference}")
        
        if difference < min_difference:
            min_difference = difference
            best_label = label
            best_target_settings = target_settings
    
    return best_label, best_target_settings

# Merged from find_material_index_from_faces.py

def find_material_index_from_faces(mesh_obj, faces_data):
    """
    面の頂点座標に基づいて該当する面を特定し、マッチした全ての面のマテリアルインデックスの中で
    最も頻度が高いものを返す
    
    Args:
        mesh_obj: Blenderのメッシュオブジェクト
        faces_data: Unityから来た面データのリスト
    
    Returns:
        int: 最も頻度が高いマテリアルインデックス（見つからない場合はNone）
    """
    from collections import Counter
    
    # オブジェクトモードであることを確認
    bpy.context.view_layer.objects.active = mesh_obj
    if bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # シーンの評価を最新の状態に更新
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    mesh = mesh_obj.data
    
    # ワールド変換行列を取得
    world_matrix = mesh_obj.matrix_world
    
    tolerance = 0.00001  # 座標の許容誤差
    
    # マッチした面のマテリアルインデックスを記録
    matched_material_indices = []
    
    for face_data in faces_data:
        # Unity座標をBlender座標に変換
        unity_vertices = face_data['vertices']
        blender_vertices = []
        
        for unity_vertex in unity_vertices:
            # Unity → Blender座標変換
            blender_vertex = mathutils.Vector((
                -unity_vertex['x'],  # X軸反転
                -unity_vertex['z'],  # Y → Z
                unity_vertex['y']    # Z → Y
            ))
            blender_vertices.append(blender_vertex)
        
        # Blenderの面を検索して一致するものを探す
        for polygon in mesh.polygons:
            if len(polygon.vertices) == 3:  # 三角形面処理
                # 面の頂点のワールド座標を取得
                face_world_verts = []
                for vert_idx in polygon.vertices:
                    vertex = mesh.vertices[vert_idx]
                    world_vert = world_matrix @ vertex.co
                    face_world_verts.append(world_vert)
                
                # 3つの頂点すべてが近い位置にあるかチェック
                match = True
                for i in range(3):
                    closest_dist = min(
                        (face_world_verts[j] - blender_vertices[i]).length 
                        for j in range(3)
                    )
                    if closest_dist > tolerance:
                        match = False
                        break
                
                if match:
                    # マッチした面のマテリアルインデックスを記録
                    material_index = polygon.material_index
                    matched_material_indices.append(material_index)
                    print(f"Found matching triangular face with material index: {material_index}")
                    
            elif len(polygon.vertices) >= 4:  # 多角形面処理
                num_vertices = len(polygon.vertices)
                # 面の頂点のワールド座標を取得
                face_world_verts = []
                for vert_idx in polygon.vertices:
                    vertex = mesh.vertices[vert_idx]
                    world_vert = world_matrix @ vertex.co
                    face_world_verts.append(world_vert)
                
                # 4つの頂点から3つを選ぶ全ての組み合わせをチェック
                from itertools import combinations
                
                for face_vert_combo in combinations(range(num_vertices), 3):
                    # この組み合わせでマッチするかチェック
                    match = True
                    for i in range(3):
                        closest_dist = min(
                            (face_world_verts[face_vert_combo[j]] - blender_vertices[i]).length 
                            for j in range(3)
                        )
                        if closest_dist > tolerance:
                            match = False
                            break
                    
                    if match:
                        # マッチした組み合わせが見つかった
                        material_index = polygon.material_index
                        matched_material_indices.append(material_index)
                        print(f"Found matching face (num_vertices: {num_vertices}) with material index: {material_index}")
                        break  # 同じ面の複数の組み合わせを重複カウントしないように
    
    # マッチした面が見つからない場合
    if not matched_material_indices:
        return None
    
    # 最も頻度が高いマテリアルインデックスを取得
    material_counter = Counter(matched_material_indices)
    most_common_material = material_counter.most_common(1)[0]
    most_common_index = most_common_material[0]
    most_common_count = most_common_material[1]
    
    print(f"Material index frequencies: {dict(material_counter)}")
    print(f"Most common material index: {most_common_index} (appears {most_common_count} times)")
    
    return most_common_index

# Merged from find_containing_objects.py

class _ContainingContext:
    """State holder for computing clothing containment."""

    def __init__(self, clothing_meshes, threshold):
        self.clothing_meshes = clothing_meshes
        self.threshold = threshold

        # Intermediate state
        self.average_distances = {}  # {(container, contained): average_distance}
        self.best_containers = {}  # {contained: (container, avg_distance)}
        self.containing_objects = {}  # {container: [contained, ...]}
        self.parent_map = {}  # {child: parent}
        self.merged_containing_objects = {}  # {root: [contained, ...]}
        self.roots_in_order = []  # insertion order for roots
        self.final_result = {}  # {root: [contained, ...]}

    # ---- 距離計測と平均距離算出 ----
    def compute_average_distances(self):
        for i, obj1 in enumerate(self.clothing_meshes):
            for j, obj2 in enumerate(self.clothing_meshes):
                if i == j:
                    continue

                depsgraph = bpy.context.evaluated_depsgraph_get()

                eval_obj1 = obj1.evaluated_get(depsgraph)
                eval_mesh1 = eval_obj1.data

                eval_obj2 = obj2.evaluated_get(depsgraph)
                eval_mesh2 = eval_obj2.data

                bm1 = bmesh.new()
                bm1.from_mesh(eval_mesh1)
                bm1.transform(obj1.matrix_world)
                bvh_tree1 = BVHTree.FromBMesh(bm1)

                all_within_threshold = True
                total_distance = 0.0
                vertex_count = 0

                for vert in eval_mesh2.vertices:
                    vert_world = obj2.matrix_world @ vert.co
                    nearest = bvh_tree1.find_nearest(vert_world)

                    if nearest is None:
                        all_within_threshold = False
                        break

                    distance = nearest[3]
                    total_distance += distance
                    vertex_count += 1

                    if distance > self.threshold:
                        all_within_threshold = False
                        break

                if all_within_threshold and vertex_count > 0:
                    average_distance = total_distance / vertex_count
                    self.average_distances[(obj1, obj2)] = average_distance

                bm1.free()

    # ---- 最良コンテナの選択 ----
    def choose_best_containers(self):
        for (container, contained), avg_distance in self.average_distances.items():
            if contained not in self.best_containers or avg_distance < self.best_containers[contained][1]:
                self.best_containers[contained] = (container, avg_distance)

    # ---- 初期包含辞書の構築 ----
    def build_initial_containing_objects(self):
        for contained, (container, _) in self.best_containers.items():
            if container not in self.containing_objects:
                self.containing_objects[container] = []
            self.containing_objects[container].append(contained)
        return self.containing_objects

    # ---- 親子マップの構築 ----
    def build_parent_map(self):
        for container, contained_list in self.containing_objects.items():
            for child in contained_list:
                self.parent_map[child] = container

    # ---- 体積計算 ----
    @staticmethod
    def get_bounding_box_volume(obj):
        try:
            dims = getattr(obj, "dimensions", None)
            if dims is None:
                return 0.0
            return float(dims[0]) * float(dims[1]) * float(dims[2])
        except Exception:
            return 0.0

    # ---- ルート探索（サイクル対応） ----
    def find_root(self, obj):
        visited_list = []
        visited_set = set()
        current = obj

        while current in self.parent_map and current not in visited_set:
            visited_list.append(current)
            visited_set.add(current)
            current = self.parent_map[current]

        if current in visited_set:
            cycle_start = visited_list.index(current)
            cycle_nodes = visited_list[cycle_start:]
            root = max(
                cycle_nodes,
                key=lambda o: (
                    self.get_bounding_box_volume(o),
                    getattr(o, "name", str(id(o)))
                )
            )
        else:
            root = current

        for node in visited_list:
            self.parent_map[node] = root

        return root

    # ---- 子孫収集 ----
    def collect_descendants(self, obj, visited):
        result = []
        for child in self.containing_objects.get(obj, []):
            if child in visited:
                continue
            visited.add(child)
            result.append(child)
            result.extend(self.collect_descendants(child, visited))
        return result

    # ---- 包含階層の統合 ----
    def merge_containing_objects(self):
        for container in self.containing_objects.keys():
            root = self.find_root(container)
            if root not in self.merged_containing_objects:
                self.merged_containing_objects[root] = []
                self.roots_in_order.append(root)

        assigned_objects = set()
        for root in self.roots_in_order:
            visited = {root}
            descendants = self.collect_descendants(root, visited)
            for child in descendants:
                if child in assigned_objects:
                    continue
                self.merged_containing_objects[root].append(child)
                assigned_objects.add(child)

        for contained, (container, _) in self.best_containers.items():
            if contained in assigned_objects:
                continue
            root = self.find_root(container)
            if root not in self.merged_containing_objects:
                self.merged_containing_objects[root] = []
                self.roots_in_order.append(root)
            if contained == root:
                continue
            self.merged_containing_objects[root].append(contained)
            assigned_objects.add(contained)

        self.final_result = {
            root: self.merged_containing_objects[root]
            for root in self.roots_in_order
            if self.merged_containing_objects[root]
        }

    # ---- 重複検出とログ出力 ----
    def detect_duplicates_and_log(self):
        if not self.final_result:
            return

        seen_objects = set()
        duplicate_objects = set()

        for container, contained_list in self.final_result.items():
            if container in seen_objects:
                duplicate_objects.add(container)
            else:
                seen_objects.add(container)

            for obj in contained_list:
                if obj in seen_objects:
                    duplicate_objects.add(obj)
                else:
                    seen_objects.add(obj)

        if duplicate_objects:
            duplicate_names = sorted(
                {getattr(obj, "name", str(id(obj))) for obj in duplicate_objects}
            )
            print(
                "find_containing_objects: 同じオブジェクトが複数回検出されました -> "
                + ", ".join(duplicate_names)
            )

    # ---- オーケストレーション ----
    def run(self):
        self.compute_average_distances()
        self.choose_best_containers()
        self.build_initial_containing_objects()

        if not self.containing_objects:
            return {}

        self.build_parent_map()
        self.merge_containing_objects()
        self.detect_duplicates_and_log()
        return self.final_result


def find_containing_objects(clothing_meshes, threshold=0.02):
    """Find containment pairs between clothing meshes."""

    ctx = _ContainingContext(clothing_meshes, threshold)

    ctx.compute_average_distances()
    ctx.choose_best_containers()
    ctx.build_initial_containing_objects()

    if not ctx.containing_objects:
        return {}

    ctx.build_parent_map()
    ctx.merge_containing_objects()
    ctx.detect_duplicates_and_log()

    return ctx.final_result