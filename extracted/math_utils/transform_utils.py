import os
import sys

from algo_utils.vertex_group_utils import get_vertex_groups_and_weights
from mathutils import Matrix
import bpy
import numpy as np
import os
import sys


# Merged from list_to_matrix.py

def list_to_matrix(matrix_list):
    """
    リストからMatrix型に変換する（JSON読み込み用）
    
    Parameters:
        matrix_list: list - 行列のデータを含む2次元リスト
        
    Returns:
        Matrix: 変換された行列
    """
    return Matrix(matrix_list)

# Merged from apply_similarity_transform_to_points.py

def apply_similarity_transform_to_points(points, s, R, t):
    """
    点群に相似変換を適用する
    
    Parameters:
        points: 変換する点群 (Nx3 のNumPy配列)
        s: スケーリング係数 (スカラー)
        R: 回転行列 (3x3)
        t: 平行移動ベクトル (3x1)
        
    Returns:
        transformed_points: 変換後の点群 (Nx3 のNumPy配列)
    """
    return s * (R @ points.T).T + t

# Merged from calculate_optimal_similarity_transform.py

def calculate_optimal_similarity_transform(source_points, target_points):
    """
    2つの点群間の最適な相似変換（スケール、回転、平行移動）を計算する
    
    Parameters:
        source_points: 変換元の点群 (Nx3 のNumPy配列)
        target_points: 変換先の点群 (Nx3 のNumPy配列)
        
    Returns:
        (s, R, t): スケーリング係数 (スカラー), 回転行列 (3x3), 平行移動ベクトル (3x1)
    """
    # 点群の重心を計算
    centroid_source = np.mean(source_points, axis=0)
    centroid_target = np.mean(target_points, axis=0)
    
    # 重心を原点に移動
    source_centered = source_points - centroid_source
    target_centered = target_points - centroid_target
    
    # ソース点群の二乗和を計算（スケーリング係数の計算用）
    source_scale = np.sum(source_centered**2)
    
    # 共分散行列を計算
    H = source_centered.T @ target_centered
    
    # 特異値分解
    U, S, Vt = np.linalg.svd(H)
    
    # 回転行列を計算
    R = Vt.T @ U.T
    
    # 反射を防ぐ（行列式が負の場合）
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    
    # 最適なスケーリング係数を計算
    trace_RSH = np.sum(S)
    s = trace_RSH / source_scale if source_scale > 0 else 1.0
    
    # 平行移動ベクトルを計算
    t = centroid_target - s * (R @ centroid_source)
    
    return s, R, t

# Merged from calculate_inverse_pose_matrix.py

def calculate_inverse_pose_matrix(mesh_obj, armature_obj, vertex_index):
    """指定された頂点のポーズ逆行列を計算"""

    # 頂点グループとウェイトの取得
    weights = get_vertex_groups_and_weights(mesh_obj, vertex_index)
    if not weights:
        print(f"頂点 {vertex_index} にウェイトが割り当てられていません")
        return None

    # 最終的な変換行列の初期化
    final_matrix = Matrix.Identity(4)
    final_matrix.zero()
    total_weight = 0

    # 各ボーンの影響を計算
    for bone_name, weight in weights.items():
        if weight > 0 and bone_name in armature_obj.data.bones:
            bone = armature_obj.data.bones[bone_name]
            pose_bone = armature_obj.pose.bones.get(bone_name)
            if bone and pose_bone:
                # ボーンの最終的な行列を計算
                mat = armature_obj.matrix_world @ \
                      pose_bone.matrix @ \
                      bone.matrix_local.inverted() @ \
                      armature_obj.matrix_world.inverted()
                
                # ウェイトを考慮して行列を加算
                final_matrix += mat * weight
                total_weight += weight

    # ウェイトの合計で正規化
    if total_weight > 0:
        final_matrix = final_matrix * (1.0 / total_weight)

    # 逆行列を計算して返す
    try:
        return final_matrix.inverted()
    except Exception as e:
        print(f"error: {e}")
        return Matrix.Identity(4)

# Merged from copy_bone_transform.py

def copy_bone_transform(source_bone: bpy.types.EditBone, target_bone: bpy.types.EditBone) -> None:
    """
    Copy transformation data from source bone to target bone.
    
    Parameters:
        source_bone: Source edit bone
        target_bone: Target edit bone
    """
    target_bone.head = source_bone.head.copy()
    target_bone.tail = source_bone.tail.copy()
    target_bone.roll = source_bone.roll
    target_bone.matrix = source_bone.matrix.copy()
    target_bone.length = source_bone.length