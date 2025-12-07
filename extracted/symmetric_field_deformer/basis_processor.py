"""
basis_processor - Basis変形処理モジュール

基本形状の変形と交差判定ループを実行する。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from find_intersecting_faces_bvh import find_intersecting_faces_bvh
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state
from process_field_deformation import process_field_deformation


def process_basis_loop(ctx):
    """
    Basis変形と交差判定ループを実行する。

    Args:
        ctx: SymmetricFieldDeformerContext インスタンス
    """
    MAX_ITERATIONS = 0
    iteration = 0
    basis_field_path = os.path.join(
        os.path.dirname(ctx.field_data_path), ctx.field_data_path
    )

    while iteration <= MAX_ITERATIONS:
        original_shape_key_state = save_shape_key_state(ctx.target_obj)

        print(f"selected field_data_path: {basis_field_path}")

        if ctx.shape_key:
            ctx.target_obj.shape_key_remove(ctx.shape_key)
        ctx.shape_key = process_field_deformation(
            ctx.target_obj,
            basis_field_path,
            ctx.blend_shape_labels,
            ctx.clothing_avatar_data,
            ctx.shape_key_name,
            ctx.ignore_blendshape,
        )

        restore_shape_key_state(ctx.target_obj, original_shape_key_state)

        if ctx.config_data:
            ctx.deferred_transitions.append(
                {
                    "target_obj": ctx.target_obj,
                    "config_data": ctx.config_data,
                    "target_label": "Basis",
                    "target_shape_key_name": ctx.shape_key_name,
                    "base_avatar_data": ctx.base_avatar_data,
                    "clothing_avatar_data": ctx.clothing_avatar_data,
                    "save_original_shape_key": False,
                }
            )

        intersections = find_intersecting_faces_bvh(ctx.target_obj)
        print(f"Iteration {iteration + 1}: Intersecting faces: {len(intersections)}")

        if not ctx.subdivision:
            print("Subdivision skipped")
            break

        if not intersections:
            print("No intersections detected")
            break

        if iteration == MAX_ITERATIONS:
            print("Maximum iterations reached")
            break

        iteration += 1
