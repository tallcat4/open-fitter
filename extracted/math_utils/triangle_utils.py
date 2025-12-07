"""
三角形関連のユーティリティ関数

- triangle_area: 三角形の面積を計算
- is_degenerate_triangle: 三角形が縮退しているかチェック
- calc_triangle_normal: 三角形の法線を計算
"""

import math

from mathutils import Vector


def triangle_area(triangle: list[Vector]) -> float:
    """ヘロンの公式を使用して三角形の面積を計算"""
    a = (triangle[1] - triangle[0]).length
    b = (triangle[2] - triangle[1]).length
    c = (triangle[0] - triangle[2]).length
    s = (a + b + c) / 2  # 半周長
    # 浮動小数点の誤差による負の値を防ぐため max(..., 0) とする
    area_val = max(s * (s - a) * (s - b) * (s - c), 0)
    area = math.sqrt(area_val)
    return area


def is_degenerate_triangle(triangle: list[Vector], epsilon: float = 1e-6) -> bool:
    """三角形が縮退しているかチェック"""
    area = triangle_area(triangle)
    return area < epsilon


def calc_triangle_normal(triangle: list[Vector]) -> Vector:
    """三角形の法線を計算（正規化済み）"""
    v1 = triangle[1] - triangle[0]
    v2 = triangle[2] - triangle[0]
    normal = v1.cross(v2)
    length = normal.length
    if length > 1e-8:  # 数値的な安定性のため
        return normal / length
    return Vector((0, 0, 0))
