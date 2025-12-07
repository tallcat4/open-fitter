import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from math_utils.triangle_utils import calc_triangle_normal, is_degenerate_triangle
from mathutils import Vector


def intersect_triangle_triangle(t1: list[Vector], t2: list[Vector]) -> bool:
    """三角形同士の交差判定（数値誤差に注意）"""
    EPSILON2 = 1e-6  # 数値計算の許容値
    
    # 縮退した三角形のチェック
    if is_degenerate_triangle(t1, EPSILON2) or is_degenerate_triangle(t2, EPSILON2):
        return False
    
    # 法線計算（面積で重み付け）
    n1 = calc_triangle_normal(t1)
    n2 = calc_triangle_normal(t2)
    
    # 法線がゼロベクトルの場合（無効な三角形）
    if n1.length < EPSILON2 or n2.length < EPSILON2:
        return False
    
    # 平面の方程式の定数項
    d1_const = -n1.dot(t1[0])
    d2_const = -n2.dot(t2[0])
    
    # 各頂点と相手の平面との距離を計算
    dist1 = [n2.dot(v) + d2_const for v in t1]
    dist2 = [n1.dot(v) + d1_const for v in t2]
    
    # 全頂点が同じ側にある場合は交差なし
    if all(d >= 0 for d in dist1) or all(d <= 0 for d in dist1):
        return False
    if all(d >= 0 for d in dist2) or all(d <= 0 for d in dist2):
        return False
    
    # 内部関数：辺と平面の交点を計算
    def compute_intersection_points(triangle, dists):
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            di = dists[i]
            dj = dists[j]
            # 頂点が平面上にある場合も含む
            if abs(di) < 1e-8:
                pts.append(triangle[i])
            if di * dj < 0:
                t = di / (di - dj)
                pt = triangle[i] + t * (triangle[j] - triangle[i])
                pts.append(pt)
            elif abs(dj) < 1e-8:
                pts.append(triangle[j])
        # 重複する点を除去
        unique_pts = []
        for p in pts:
            if not any((p - q).length < 1e-8 for q in unique_pts):
                unique_pts.append(p)
        return unique_pts
    
    pts1 = compute_intersection_points(t1, dist1)
    pts2 = compute_intersection_points(t2, dist2)
    
    # 交点が2点未満なら交差していないとみなす
    if len(pts1) < 2 or len(pts2) < 2:
        return False
    
    # 共通線の方向を決定
    d = n1.cross(n2)
    if d.length < 1e-8:
        # ほぼ同一平面上の場合は、このメソッドでは処理しない
        return False
    d.normalize()
    
    # 交点を共通線上に射影して区間を求める
    s1 = [d.dot(p) for p in pts1]
    s2 = [d.dot(p) for p in pts2]
    seg1_min, seg1_max = min(s1), max(s1)
    seg2_min, seg2_max = min(s2), max(s2)
    
    # 区間の重なりをチェック
    if seg1_max < seg2_min or seg2_max < seg1_min:
        return False
    return True
