import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
from apply_field_delta_with_rigid_transform import (
    apply_field_delta_with_rigid_transform,
)
from apply_symmetric_field_delta import apply_symmetric_field_delta
from math_utils.calculate_distance_based_weights import calculate_distance_based_weights
from math_utils.obb_utils import calculate_obb_from_object
from math_utils.check_mesh_obb_intersection import check_mesh_obb_intersection
from misc_utils.separate_and_combine_components import separate_and_combine_components
from process_blendshape_fields_with_rigid_transform import (
    process_blendshape_fields_with_rigid_transform,
)


def process_mesh_with_connected_components_inline(obj, field_data_path, blend_shape_labels, clothing_avatar_data, base_avatar_data, clothing_armature, cloth_metadata=None, subdivision=True, skip_blend_shape_generation=False, config_data=None):
    """
    メッシュを連結成分ごとに処理し、適切な変形を適用した後、
    元のオブジェクトのままで結果を統合する
    
    Parameters:
        obj: 処理対象のメッシュオブジェクト
        field_data_path: Deformation Fieldのパス
        blend_shape_labels: 適用するブレンドシェイプのラベルリスト
        clothing_avatar_data: 衣装アバターデータ
        base_avatar_data: ベースアバターデータ
        clothing_armature: 衣装のアーマチュアオブジェクト
        cloth_metadata: クロスメタデータ（オプション）
    """

    # オブジェクト名を保存
    original_name = obj.name

    # 素体メッシュを取得
    base_obj = bpy.data.objects.get("Body.BaseAvatar")
    if not base_obj:
        raise Exception("Base avatar mesh (Body.BaseAvatar) not found")

    calculate_distance_based_weights(
        source_obj_name=original_name,
        target_obj_name=base_obj.name,
        vertex_group_name="DistanceWeight",
        min_distance=0.0,
        max_distance=0.1
    )
    
    # 連結成分を分離（アーマチュア設定等も保持）
    separated_objects, non_separated_objects = separate_and_combine_components(obj, clothing_armature, clustering=True)
    
    # 分離するコンポーネントがない場合は通常の処理を行う
    if not separated_objects or (cloth_metadata and obj.name in cloth_metadata):
        if cloth_metadata and obj.name in cloth_metadata:
            subdivision = False
        apply_symmetric_field_delta(obj, field_data_path, blend_shape_labels, clothing_avatar_data, base_avatar_data, subdivision, skip_blend_shape_generation=skip_blend_shape_generation, config_data=config_data)
        for sep_obj in non_separated_objects:
            if sep_obj == obj:
                continue  # 元のオブジェクト自体はスキップ
            bpy.data.objects.remove(sep_obj, do_unlink=True)
        for sep_obj in separated_objects:
            if sep_obj == obj:
                continue  # 元のオブジェクト自体はスキップ
            bpy.data.objects.remove(sep_obj, do_unlink=True)
        return
    
    # 進捗を報告
    print(f"Processing {original_name}: {len(separated_objects)} separated, {len(non_separated_objects)} non-separated")

    bpy.context.view_layer.objects.active = obj
    
    # 分離しないコンポーネントを記録するリスト
    do_not_separate = []
    
    # 処理対象のオブジェクトリスト
    processed_objects = []

    # 分離されたオブジェクトに剛体変換処理を適用
    for sep_obj in separated_objects:
        bpy.context.view_layer.objects.active = sep_obj
        _, config_blend_shape_labels = apply_field_delta_with_rigid_transform(sep_obj, field_data_path, blend_shape_labels, base_avatar_data, clothing_avatar_data, "RigidTransformed", config_data=None)
        
        # base_avatar_dataのblendShapeFieldsを処理するための準備
        if not skip_blend_shape_generation:
            process_blendshape_fields_with_rigid_transform(sep_obj, field_data_path, base_avatar_data, clothing_avatar_data, config_blend_shape_labels, influence_range=1.0, config_data=config_data)
        
        # OBBを計算
        obb = calculate_obb_from_object(sep_obj)

        print(f"Component {sep_obj.name} OBB: \n {obb}")
        
        # 素体メッシュとOBBの交差をチェック
        if check_mesh_obb_intersection(base_obj, obb):
            print(f"Component {sep_obj.name} intersects with base mesh, will not be separated")
            do_not_separate.append(sep_obj.name)
        
        processed_objects.append(sep_obj)
    
    bpy.context.view_layer.objects.active = obj
    
    # 分離されたオブジェクトを削除
    for sep_obj in separated_objects:
        print(f"Removing {sep_obj.name}")
        bpy.data.objects.remove(sep_obj, do_unlink=True)
    # 分離されていないオブジェクトを削除
    for sep_obj in non_separated_objects:
        print(f"Removing {sep_obj.name}")
        bpy.data.objects.remove(sep_obj, do_unlink=True)
    
    # 分離しないコンポーネントのリストを使用して再度分離を行う
    separated_objects, non_separated_objects = separate_and_combine_components(obj, clothing_armature, do_not_separate, clustering=True)
    
    # 処理対象のオブジェクトリストをリセット
    processed_objects = []
    
    # 分離されたオブジェクトに剛体変換処理を適用
    for sep_obj in separated_objects:
        bpy.context.view_layer.objects.active = sep_obj
        _, config_blend_shape_labels = apply_field_delta_with_rigid_transform(sep_obj, field_data_path, blend_shape_labels, base_avatar_data, clothing_avatar_data, "RigidTransformed", config_data=config_data)
        
        # base_avatar_dataのblendShapeFieldsを処理するための準備
        if not skip_blend_shape_generation:
            process_blendshape_fields_with_rigid_transform(sep_obj, field_data_path, base_avatar_data, clothing_avatar_data, config_blend_shape_labels, influence_range=1.0, config_data=config_data)
        processed_objects.append(sep_obj)
    
    # 分離されなかったオブジェクトに通常の変形処理を適用
    for non_sep_obj in non_separated_objects:
        if non_sep_obj is None:
            continue

        if cloth_metadata and non_sep_obj.name in cloth_metadata:
            subdivision = False
        
        bpy.context.view_layer.objects.active = non_sep_obj
        
        apply_symmetric_field_delta(non_sep_obj, field_data_path, blend_shape_labels, clothing_avatar_data, base_avatar_data, subdivision, skip_blend_shape_generation=skip_blend_shape_generation, config_data=config_data)
        processed_objects.append(non_sep_obj)
    
    # 元のオブジェクトのシェイプキー情報を保存
    original_shapekeys = {}
    if obj.data.shape_keys:
        for key_block in obj.data.shape_keys.key_blocks:
            original_shapekeys[key_block.name] = key_block.value
    
    # 各処理済みオブジェクトの面をマテリアル順にソート
    for proc_obj in processed_objects:
        if proc_obj is None:
            continue
            
        bpy.ops.object.mode_set(mode='OBJECT')
        
        bpy.ops.object.select_all(action='DESELECT')
        proc_obj.select_set(True)
        bpy.context.view_layer.objects.active = proc_obj
        
        # 編集モードに入る
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 面をマテリアル順にソート
        bpy.ops.mesh.sort_elements(type='MATERIAL', elements={'FACE'})
        
        # オブジェクトモードに戻る
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # 元のオブジェクトの頂点を削除するために編集モードに入る
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # すべての頂点を選択して削除
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete(type='VERT')
    
    # オブジェクトモードに戻る
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 各処理済みオブジェクトを順番に結合
    for proc_obj in processed_objects:
        if proc_obj == obj:
            continue  # 元のオブジェクト自体はスキップ
        
        # 選択を設定
        bpy.ops.object.select_all(action='DESELECT')
        proc_obj.select_set(True)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj  # 元のオブジェクトをアクティブに
        
        # 結合操作
        bpy.ops.object.join()
    
    # 元のオブジェクト名を復元（結合操作で変わる可能性があるため）
    obj.name = original_name
    
    # シェイプキーの値を復元
    if obj.data.shape_keys:
        for key_name, value in original_shapekeys.items():
            if key_name in obj.data.shape_keys.key_blocks:
                obj.data.shape_keys.key_blocks[key_name].value = value
    
    # 元のアクティブオブジェクトを復元
    bpy.context.view_layer.objects.active = obj
