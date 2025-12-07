import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np

try:
    import bpy
except ImportError:
    bpy = None


def calculate_obb(vertices_world):
    """
    頂点のワールド座標から最適な向きのバウンディングボックスを計算
    
    Parameters:
        vertices_world: 頂点のワールド座標のリスト
        
    Returns:
        (axes, extents): 主軸方向と、各方向の半分の長さ
    """
    if vertices_world is None or len(vertices_world) < 3:
        return None, None
    
    # 点群の重心を計算
    centroid = np.mean(vertices_world, axis=0)
    
    # 重心を原点に移動
    centered = vertices_world - centroid
    
    # 共分散行列を計算
    cov = np.cov(centered, rowvar=False)
    
    # 固有ベクトルと固有値を計算
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    
    # 固有ベクトルが主軸となる
    axes = eigenvectors
    
    # 各軸方向のextentを計算
    extents = np.zeros(3)
    for i in range(3):
        axis = axes[:, i]
        projection = np.dot(centered, axis)
        extents[i] = (np.max(projection) - np.min(projection)) / 2.0
    
    return axes, extents


def calculate_obb_from_object(obj):
    """
    オブジェクトのOriented Bounding Box (OBB)を計算する
    
    Parameters:
        obj: 対象のメッシュオブジェクト
        
    Returns:
        dict: OBBの情報（中心、軸、半径）
    """
    if bpy is None:
        raise ImportError("bpy module required for calculate_obb_from_object")
    
    # 評価済みメッシュを取得
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.data
    
    # 頂点座標をワールド空間で取得
    vertices = np.array([obj.matrix_world @ v.co for v in eval_mesh.vertices])
    
    if len(vertices) == 0:
        return None
    
    # 頂点の平均位置（中心）を計算
    center = np.mean(vertices, axis=0)
    
    # 中心を原点に移動
    centered_vertices = vertices - center
    
    # 共分散行列を計算
    covariance_matrix = np.cov(centered_vertices.T)
    
    # 固有値と固有ベクトルを計算
    eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
    
    # 固有ベクトルを正規化
    for i in range(3):
        eigenvectors[:, i] = eigenvectors[:, i] / np.linalg.norm(eigenvectors[:, i])
    
    # 各軸に沿った投影の最大値を計算
    min_proj = np.full(3, float('inf'))
    max_proj = np.full(3, float('-inf'))
    
    for vertex in centered_vertices:
        for i in range(3):
            proj = np.dot(vertex, eigenvectors[:, i])
            min_proj[i] = min(min_proj[i], proj)
            max_proj[i] = max(max_proj[i], proj)
    
    # 半径（各軸方向の長さの半分）を計算
    radii = (max_proj - min_proj) / 2
    
    # 中心位置を調整
    adjusted_center = center + np.sum([(min_proj[i] + max_proj[i]) / 2 * eigenvectors[:, i] for i in range(3)], axis=0)
    
    return {
        'center': adjusted_center,
        'axes': eigenvectors,
        'radii': radii
    }


def calculate_obb_from_points(points):
    """
    点群からOriented Bounding Box (OBB)を計算する
    
    Parameters:
        points: 点群のリスト（Vector型またはタプル）
        
    Returns:
        dict: OBBの情報を含む辞書
            'center': 中心座標
            'axes': 主軸（3x3の行列、各列が軸）
            'radii': 各軸方向の半径
        または None: 計算不能な場合
    """
    
    # 点群が少なすぎる場合はNoneを返す
    if len(points) < 3:
        print(f"警告: 点群が少なすぎます（{len(points)}点）。OBB計算をスキップします。")
        return None
    
    try:
        # 点群をnumpy配列に変換
        points_np = np.array([[p.x, p.y, p.z] for p in points])
        
        # 点群の中心を計算
        center = np.mean(points_np, axis=0)
        
        # 中心を原点に移動
        centered_points = points_np - center
        
        # 共分散行列を計算
        cov_matrix = np.cov(centered_points, rowvar=False)
        
        # 行列のランクをチェック
        if np.linalg.matrix_rank(cov_matrix) < 3:
            print("警告: 共分散行列のランクが不足しています。OBB計算をスキップします。")
            return None
        
        # 固有値と固有ベクトルを計算
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # 固有値が非常に小さい場合はスキップ
        if np.any(np.abs(eigenvalues) < 1e-10):
            print("警告: 固有値が非常に小さいです。OBB計算をスキップします。")
            return None
        
        # 固有値の大きさでソート（降順）
        idx = eigenvalues.argsort()[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # 主軸を取得（列ベクトルとして）
        axes = eigenvectors
        
        # 各軸方向の点の投影を計算
        projections = np.abs(np.dot(centered_points, axes))
        
        # 各軸方向の最大値を半径として使用
        radii = np.max(projections, axis=0)
        
        # 結果を辞書として返す
        return {
            'center': center,
            'axes': axes,
            'radii': radii
        }
    except Exception as e:
        print(f"OBB計算中にエラーが発生しました: {e}")
        return None
