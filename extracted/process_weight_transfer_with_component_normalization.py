import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
from algo_utils.component_utils import (
    group_components_by_weight_pattern,
)
from process_weight_transfer import process_weight_transfer
from weight_transfer_phases import (
    WeightTransferContext,
    _apply_blend_shape_settings,
    _collect_obb_data,
    _get_existing_target_groups,
    _normalize_component_patterns,
    _process_obb_groups,
    _store_original_vertex_weights,
    _synthesize_weights,
)


def process_weight_transfer_with_component_normalization(target_obj, armature, base_avatar_data, clothing_avatar_data, field_path, clothing_armature, blend_shape_settings, cloth_metadata=None):
    """
    ウェイト転送処理を行い、連結成分ごとにウェイトを正規化する
    
    Parameters:
        target_obj: 処理対象のメッシュオブジェクト
        armature: アーマチュアオブジェクト
        base_avatar_data: ベースアバターデータ
        clothing_avatar_data: 衣装アバターデータ
        field_path: フィールドパス
        clothing_armature: 衣装のアーマチュア
        cloth_metadata: クロスメタデータ
    """
    import time
    start_total = time.time()

    print(f"process_weight_transfer_with_component_normalization 処理開始: {target_obj.name}")

    ctx = WeightTransferContext(
        target_obj=target_obj,
        armature=armature,
        base_avatar_data=base_avatar_data,
        clothing_avatar_data=clothing_avatar_data,
        field_path=field_path,
        clothing_armature=clothing_armature,
        blend_shape_settings=blend_shape_settings,
        cloth_metadata=cloth_metadata,
    )

    start_time = time.time()
    ctx.base_obj = bpy.data.objects.get("Body.BaseAvatar")
    if not ctx.base_obj:
        raise Exception("Base avatar mesh (Body.BaseAvatar) not found")

    ctx.left_base_obj = bpy.data.objects["Body.BaseAvatar.LeftOnly"]
    ctx.right_base_obj = bpy.data.objects["Body.BaseAvatar.RightOnly"]

    print(f"Set blend_shape_settings: {blend_shape_settings}")
    _apply_blend_shape_settings(ctx)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_target_obj = target_obj.evaluated_get(depsgraph)
    eval_mesh = eval_target_obj.data

    existing_target_groups = _get_existing_target_groups(ctx)
    print(f"準備時間: {time.time() - start_time:.2f}秒")

    start_time = time.time()
    component_patterns = group_components_by_weight_pattern(target_obj, base_avatar_data, clothing_armature)
    ctx.component_patterns = component_patterns
    print(f"コンポーネントパターン抽出時間: {time.time() - start_time:.2f}秒")

    original_vertex_weights = _store_original_vertex_weights(ctx)

    start_time = time.time()
    process_weight_transfer(target_obj, armature, base_avatar_data, clothing_avatar_data, field_path, clothing_armature, cloth_metadata)
    print(f"通常ウェイト転送処理時間: {time.time() - start_time:.2f}秒")

    component_patterns = _normalize_component_patterns(ctx, component_patterns)

    if component_patterns:
        obb_data = _collect_obb_data(ctx)
        if not obb_data:
            print("警告: 有効なOBBデータがありません。処理をスキップします。")
            return

        _process_obb_groups(ctx)
        _synthesize_weights(ctx)

    print(f"総処理時間: {time.time() - start_total:.2f}秒")
