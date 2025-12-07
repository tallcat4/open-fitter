import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
import numpy as np
from blender_utils.batch_process_vertices_multi_step import (
    batch_process_vertices_multi_step,
)
from blender_utils.create_blendshape_mask import create_blendshape_mask
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


def process_blendshape_fields_with_rigid_transform(obj, field_data_path, base_avatar_data, clothing_avatar_data, config_blend_shape_labels, influence_range=1.0, config_data=None):
    """
    base_avatar_dataのblendShapeFieldsを剛体変換を使用して処理する
    
    Parameters:
        obj: 対象メッシュオブジェクト
        field_data_path: Deformation Fieldのパス
        base_avatar_data: ベースアバターデータ
        clothing_avatar_data: 衣装アバターデータ
        influence_range: DistanceWeight頂点グループによる影響度の範囲（0.0-1.0、デフォルト0.5）
    """

    # base_avatar_dataのblendShapeFieldsを処理
    if base_avatar_data and "blendShapeFields" in base_avatar_data:
        # アーマチュアの取得
        armature_obj = get_armature_from_modifier(obj)
        if not armature_obj:
            raise ValueError("Armatureモディファイアが見つかりません")

        # 対象メッシュオブジェクトの元のシェイプキー設定を保存
        original_shape_key_state = save_shape_key_state(obj)
        
        # すべてのシェイプキーの値を0にする
        if obj.data.shape_keys:
            for key_block in obj.data.shape_keys.key_blocks:
                key_block.value = 0.0
        
        # 評価されたメッシュの頂点位置を取得（シェイプキーA適用後）
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
        vertices = np.array([v.co for v in obj.data.vertices])  # オリジナルの頂点配列
        deformed_vertices = np.array([v.co for v in eval_mesh.vertices])

        # 各blendShapeFieldを剛体変換を使用して処理
        for blend_field in base_avatar_data["blendShapeFields"]:
            label = blend_field["label"]
            
            # configファイルのblendShapeFieldsのlabelと一致する場合はスキップ
            if label in config_blend_shape_labels:
                print(f"Skipping base avatar blend shape field '{label}' (already processed from config)")
                continue
                
            field_path = os.path.join(os.path.dirname(field_data_path), blend_field["filePath"])
            
            if os.path.exists(field_path):
                print(f"Applying blend shape field for {label} with rigid transform")
                # フィールドデータの読み込み
                field_info_blend = get_deformation_field_multi_step(field_path)
                blend_points = field_info_blend['all_field_points']
                blend_deltas = field_info_blend['all_delta_positions']
                blend_field_weights = field_info_blend['field_weights']
                blend_matrix = field_info_blend['world_matrix']
                blend_matrix_inv = field_info_blend['world_matrix_inv']
                blend_k_neighbors = field_info_blend['kdtree_query_k']
                
                # マスクウェイトを取得
                mask_weights = None
                if "maskBones" in blend_field:
                    mask_weights = create_blendshape_mask(obj, blend_field["maskBones"], clothing_avatar_data, field_name=label, store_debug_mask=True)
                
                # 変形後の位置を計算
                deformed_positions = batch_process_vertices_multi_step(
                    deformed_vertices,
                    blend_points,
                    blend_deltas,
                    blend_field_weights,
                    blend_matrix,
                    blend_matrix_inv,
                    obj.matrix_world,
                    obj.matrix_world.inverted(),
                    mask_weights,
                    batch_size=1000,
                    k=blend_k_neighbors
                )

                # 変位が0かどうかをワールド座標でチェック
                has_displacement = False
                for i in range(len(deformed_vertices)):
                    displacement = deformed_positions[i] - (obj.matrix_world @ Vector(deformed_vertices[i]))
                    if np.any(np.abs(displacement) > 1e-5):  # 微小な変位は無視
                        print(f"blendShapeFields {label} world_displacement: {displacement}")
                        has_displacement = True
                        break

                # 変位が存在する場合のみシェイプキーを作成
                if has_displacement:
                    # ソースと変形後の点群から相似変換を計算
                    source_points = np.array([obj.matrix_world @ Vector(v) for v in deformed_vertices])
                    target_points = np.array(deformed_positions)
                    
                    # # DistanceWeight頂点グループからの影響度を取得
                    # influence_factors = get_distance_weight_influence_factors(obj, influence_range)
                    
                    # # 最適な相似変換を計算（重み付きまたは通常）
                    # if influence_factors is not None:
                    #     print(f"Using weighted similarity transform with DistanceWeight vertex group for blend shape {label}")
                    #     s, R, t = calculate_optimal_similarity_transform_weighted(source_points, target_points, influence_factors)
                    # else:
                    #     s, R, t = calculate_optimal_similarity_transform(source_points, target_points)

                    s, R, t = calculate_optimal_similarity_transform(source_points, target_points)
                    
                    # 相似変換を適用した結果を計算
                    similarity_transformed = apply_similarity_transform_to_points(source_points, s, R, t)
                    
                    blend_shape_key_name = label
                    if obj.data.shape_keys and label in obj.data.shape_keys.key_blocks:
                        blend_shape_key_name = f"{label}_generated"
                    
                    # シェイプキーを作成
                    shape_key_b = obj.shape_key_add(name=blend_shape_key_name)
                    shape_key_b.value = 0.0  # 初期値は0

                    # シェイプキーに頂点位置を保存
                    matrix_armature_inv_fallback = Matrix.Identity(4)
                    for i in range(len(vertices)):
                        matrix_armature_inv = calculate_inverse_pose_matrix(obj, armature_obj, i)
                        if matrix_armature_inv is None:
                            matrix_armature_inv = matrix_armature_inv_fallback
                        # 変形後の位置をローカル座標に変換
                        deformed_world_pos = matrix_armature_inv @ Vector(similarity_transformed[i])
                        deformed_local_pos = obj.matrix_world.inverted() @ deformed_world_pos
                        shape_key_b.data[i].co = deformed_local_pos
                        matrix_armature_inv_fallback = matrix_armature_inv
                else:
                    print(f"Skipping creation of shape key '{label}' as it has no displacement")

            else:
                print(f"Warning: Field file not found for blend shape {label}")
        # 元のシェイプキー設定を復元
        restore_shape_key_state(obj, original_shape_key_state)
