import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from algo_utils.vertex_group_utils import get_vertex_groups_and_weights
from mathutils import Matrix


def _validate_inputs(armature_obj, mesh_obj):
    if not armature_obj or armature_obj.type != 'ARMATURE':
        raise ValueError("有効なArmatureオブジェクトを指定してください")

    if not mesh_obj or mesh_obj.type != 'MESH':
        raise ValueError("有効なメッシュオブジェクトを指定してください")


def _gather_world_vertices(mesh_obj):
    return [v.co.copy() for v in mesh_obj.data.vertices]


def _compute_combined_matrix(weights, armature_obj):
    combined_matrix = Matrix.Identity(4)
    combined_matrix.zero()
    total_weight = 0.0

    for bone_name, weight in weights.items():
        if weight > 0 and bone_name in armature_obj.data.bones:
            bone = armature_obj.data.bones[bone_name]
            pose_bone = armature_obj.pose.bones.get(bone_name)
            if bone and pose_bone:
                bone_matrix = pose_bone.matrix @ bone.matrix_local.inverted()
                combined_matrix += bone_matrix * weight
                total_weight += weight

    return combined_matrix, total_weight


def _safe_inverse_matrix(combined_matrix, vertex_index):
    try:
        return combined_matrix.inverted()
    except Exception:
        print(f"警告: 頂点 {vertex_index} の逆行列を計算できませんでした")
        return Matrix.Identity(4)


def _log_progress(vertex_index, total_vertices):
    if (vertex_index + 1) % 1000 == 0:
        print(f"進捗: {vertex_index + 1}/{total_vertices} 頂点処理完了")


def _compute_inverse_vertices(vertices, mesh_obj, armature_obj):
    inverse_transformed_vertices = []

    for vertex_index, pos in enumerate(vertices):
        weights = get_vertex_groups_and_weights(mesh_obj, vertex_index)

        if not weights:
            print(f"警告: 頂点 {vertex_index} のウェイトがないため、単位行列を使用します")
            inverse_transformed_vertices.append(pos)
            _log_progress(vertex_index, len(vertices))
            continue

        combined_matrix, total_weight = _compute_combined_matrix(weights, armature_obj)

        if total_weight > 0:
            combined_matrix = combined_matrix * (1.0 / total_weight)
        else:
            print(f"警告: 頂点 {vertex_index} のウェイトがないため、単位行列を使用します")
            combined_matrix = Matrix.Identity(4)

        inverse_matrix = _safe_inverse_matrix(combined_matrix, vertex_index)
        rest_pose_pos = inverse_matrix @ pos

        inverse_transformed_vertices.append(rest_pose_pos)
        _log_progress(vertex_index, len(vertices))

    return inverse_transformed_vertices


def _apply_inverse_to_shape_keys(mesh_obj, inverse_transformed_vertices, original_vertices):
    if not mesh_obj.data.shape_keys:
        return

    for shape_key in mesh_obj.data.shape_keys.key_blocks:
        if shape_key.name != "Basis":
            for i, vert in enumerate(shape_key.data):
                vert.co += inverse_transformed_vertices[i] - original_vertices[i]

    basis_shape_key = mesh_obj.data.shape_keys.key_blocks["Basis"]
    for i, vert in enumerate(basis_shape_key.data):
        vert.co = inverse_transformed_vertices[i]


def _apply_inverse_to_mesh(mesh_obj, inverse_transformed_vertices):
    for vertex_index, pos in enumerate(inverse_transformed_vertices):
        mesh_obj.data.vertices[vertex_index].co = pos


def inverse_bone_deform_all_vertices(armature_obj, mesh_obj):
    """
    メッシュオブジェクトの評価後の頂点のワールド座標から、
    現在のArmatureオブジェクトのポーズの逆変換をすべての頂点に対して行う
    
    Parameters:
        armature_obj: Armatureオブジェクト
        mesh_obj: メッシュオブジェクト
        
    Returns:
        np.ndarray: すべての頂点の逆変換後の座標（ローカル座標）
        

        通常のボーン変形: 変形後 = Σ(weight_i × bone_matrix_i) × 変形前
        この関数の逆変換: 変形前 = [Σ(weight_i × bone_matrix_i)]^(-1) × 変形後
    """
    _validate_inputs(armature_obj, mesh_obj)

    vertices = _gather_world_vertices(mesh_obj)

    print(f"ボーン変形の逆変換を開始: {len(vertices)}頂点")

    inverse_transformed_vertices = _compute_inverse_vertices(vertices, mesh_obj, armature_obj)

    print(f"ボーン変形の逆変換が完了しました")

    _apply_inverse_to_shape_keys(mesh_obj, inverse_transformed_vertices, vertices)
    _apply_inverse_to_mesh(mesh_obj, inverse_transformed_vertices)

    result = np.array([[v[0], v[1], v[2]] for v in inverse_transformed_vertices])

    return result
