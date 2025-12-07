import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
import numpy as np
from blender_utils.batch_process_vertices_with_custom_range import (
    batch_process_vertices_with_custom_range,
)
from blender_utils.get_armature_from_modifier import get_armature_from_modifier
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state
from math_utils.apply_similarity_transform_to_points import (
    apply_similarity_transform_to_points,
)
from math_utils.calculate_inverse_pose_matrix import calculate_inverse_pose_matrix
from math_utils.calculate_optimal_similarity_transform import (
    calculate_optimal_similarity_transform,
)
from mathutils import Matrix, Vector
from misc_utils.get_deformation_field_multi_step import get_deformation_field_multi_step


def apply_blendshape_operation(target_obj, operation, target_shape_key, rigid_transformation=False):
    """
    単一のBlendShape遷移を指定されたオブジェクトに適用する
    
    Parameters:
        target_obj: 対象メッシュオブジェクト
        transition: 遷移データ
        target_shape_key: 適用先のシェイプキー名 (Noneの場合はBasisに適用)
    """
    try:
        armature_obj = get_armature_from_modifier(target_obj)
        
        field_file_path = operation['file_path']
        num_steps = operation['num_steps']
        from_step = operation['from_step']
        to_step = operation['to_step']
        field_type = operation['field_type']
        
        print(f"Applying operation: {operation['blend_shape']} "
              f"({operation['from_value']} -> {operation['to_value']}) "
              f"steps {from_step}->{to_step}/{num_steps}")
        
        if not os.path.exists(field_file_path):
            print(f"Warning: Deformation field file not found: {field_file_path}")
            return
        
        # ステップ間の変換を計算
        if from_step == to_step:
            print("No step change required")
            return
        
        # 現在のオブジェクトの頂点位置を取得
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = target_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        vertices = np.array([v.co for v in eval_mesh.vertices])
        num_vertices = len(vertices)
        
        # ③ メインの Deformation Field 情報を取得
        field_info = get_deformation_field_multi_step(field_file_path)
        all_field_points = field_info['all_field_points']
        all_delta_positions = field_info['all_delta_positions']
        deform_weights = field_info['field_weights']
        field_matrix = field_info['world_matrix']
        field_matrix_inv = field_info['world_matrix_inv']
        k_neighbors = field_info['kdtree_query_k']

        # もしdeform_weightsがNoneの場合は、全ての頂点のウェイトを1.0とする
        if deform_weights is None:
            deform_weights = np.ones(num_vertices)
        
        from_value = operation['from_value']
        to_value = operation['to_value']
        if field_type == 'inverted':
            from_value = 1.0 - from_value
            to_value = 1.0 - to_value
            if from_value < 0.00001:
                from_value = 0.0
            if to_value < 0.00001:
                to_value = 0.0
            if from_value > 0.99999:
                from_value = 1.0
            if to_value > 0.99999:
                to_value = 1.0

        # カスタムレンジ処理を使用
        world_positions = batch_process_vertices_with_custom_range(
            vertices,
            all_field_points,
            all_delta_positions,
            deform_weights,
            field_matrix,
            field_matrix_inv,
            target_obj.matrix_world,
            target_obj.matrix_world.inverted(),
            from_value,
            to_value,
            deform_weights=deform_weights,
            batch_size=1000,
            k=k_neighbors
        )

        if rigid_transformation:
            # numpy配列に変換
            source_points = np.array([target_obj.matrix_world @ Vector(v) for v in vertices])
            s, R, t = calculate_optimal_similarity_transform(source_points, world_positions)
            # 相似変換を適用した結果を計算
            world_positions = apply_similarity_transform_to_points(source_points, s, R, t)

        # 結果を適用
        matrix_armature_inv_fallback = Matrix.Identity(4)
        for i in range(len(target_obj.data.vertices)):
            matrix_armature_inv = calculate_inverse_pose_matrix(target_obj, armature_obj, i)
            if matrix_armature_inv is None:
                matrix_armature_inv = matrix_armature_inv_fallback
            undeformed_world_pos = matrix_armature_inv @ Vector(world_positions[i])
            local_pos = target_obj.matrix_world.inverted() @ undeformed_world_pos
            target_shape_key.data[i].co = local_pos
            matrix_armature_inv_fallback = matrix_armature_inv
        
        return target_shape_key
        
    except Exception as e:
        print(f"Error applying operation {operation['blend_shape']}: {e}")
        import traceback
        traceback.print_exc()


def apply_blendshape_operation_with_shape_key_name(target_obj, operation, target_shape_key_name, rigid_transformation=False):
    target_shape_key = target_obj.data.shape_keys.key_blocks.get(target_shape_key_name)
    if target_shape_key is None:
        print(f"Shape key {target_shape_key_name} not found")
        return
    
    original_shape_key_state = save_shape_key_state(target_obj)

    #すべてのシェイプキーの値を0にする
    for key_block in target_obj.data.shape_keys.key_blocks:
        key_block.value = 0.0
    
    target_shape_key.value = 1.0

    apply_blendshape_operation(target_obj, operation, target_shape_key, rigid_transformation)

    restore_shape_key_state(target_obj, original_shape_key_state)
