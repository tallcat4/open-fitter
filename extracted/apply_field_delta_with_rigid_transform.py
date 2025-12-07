import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
import numpy as np
from apply_field_delta_with_rigid_transform_single import (
    apply_field_delta_with_rigid_transform_single,
)
from blender_utils.create_blendshape_mask import create_blendshape_mask
from common_utils.get_source_label import get_source_label
from execute_transitions_with_cache import execute_transitions_with_cache
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state
from misc_utils.TransitionCache import TransitionCache


def apply_field_delta_with_rigid_transform(obj, field_data_path, blend_shape_labels=None, base_avatar_data=None, clothing_avatar_data=None, shape_key_name="RigidTransformed", influence_range=1.0, config_data=None, overwrite_base_shape_key=True):
    """
    保存された対称Deformation Field差分データを読み込み、最適な剛体変換として適用する（多段階対応）
    
    Parameters:
        obj: 対象メッシュオブジェクト
        field_data_path: Deformation Fieldのパス
        blend_shape_labels: 適用するブレンドシェイプのラベルリスト（オプション）
        base_avatar_data: ベースアバターデータ（オプション）
        clothing_avatar_data: 衣装アバターデータ（オプション）
        shape_key_name: 作成するシェイプキーの名前
        influence_range: DistanceWeight頂点グループによる影響度の範囲（0.0-1.0、デフォルト0.5）
        
    Returns:
        シェイプキー
    """
    # Transitionキャッシュを初期化
    transition_cache = TransitionCache()
    deferred_transitions = []  # 遅延実行するTransitionのリスト
    
    original_shape_key_state = save_shape_key_state(obj)

    if obj.data.shape_keys:
        for sk in obj.data.shape_keys.key_blocks:
            sk.value = 0.0
        
    basis_field_path = os.path.join(os.path.dirname(field_data_path), field_data_path)
    print(f"selected field_data_path: {basis_field_path}")
    
    shape_key = apply_field_delta_with_rigid_transform_single(obj, basis_field_path, blend_shape_labels, clothing_avatar_data, shape_key_name)
    
    # Basis遷移を遅延実行リストに追加
    if config_data:
        deferred_transitions.append({
            'target_obj': obj,
            'config_data': config_data,
            'target_label': 'Basis',
            'target_shape_key_name': shape_key_name,
            'base_avatar_data': base_avatar_data,
            'clothing_avatar_data': clothing_avatar_data,
            'base_avatar_data': base_avatar_data,
            'save_original_shape_key': True
        })
    
    restore_shape_key_state(obj, original_shape_key_state)
    
    # configファイルのblendShapeFieldsを処理するためのラベルセットを作成
    config_blend_shape_labels = set()
    config_generated_shape_keys = {}  # 後続処理の対象外にするシェイプキー名を保存
    non_relative_shape_keys = set() # 相対的な変位を持たないシェイプキー名を保存

    skipped_shape_keys = set()
    label_to_target_shape_key_name = {'Basis': shape_key_name}
    
    # 1. configファイルのblendShapeFieldsを先に処理
    if config_data and "blendShapeFields" in config_data:
        print("Processing config blendShapeFields (rigid transform)...")
        
        for blend_field in config_data["blendShapeFields"]:
            label = blend_field["label"]
            source_label = blend_field["sourceLabel"]
            field_path = os.path.join(os.path.dirname(field_data_path), blend_field["path"])

            print(f"selected field_path: {field_path}")
            source_blend_shape_settings = blend_field.get("sourceBlendShapeSettings", [])

            if (blend_shape_labels is None or source_label not in blend_shape_labels) and source_label not in obj.data.shape_keys.key_blocks:
                print(f"Skipping {label} - source label {source_label} not in shape keys")
                skipped_shape_keys.add(label)
                continue
            
            # マスクウェイトを取得
            mask_bones = blend_field.get("maskBones", [])
            mask_weights = None
            if mask_bones:
                mask_weights = create_blendshape_mask(obj, mask_bones, clothing_avatar_data, field_name=label, store_debug_mask=True)
            
            if mask_weights is not None and np.all(mask_weights == 0):
                print(f"Skipping {label} - all mask weights are zero")
                continue
            
            # 対象メッシュオブジェクトの元のシェイプキー設定を保存
            original_shape_key_state = save_shape_key_state(obj)
            
            # すべてのシェイプキーの値を0にする
            if obj.data.shape_keys:
                for key_block in obj.data.shape_keys.key_blocks:
                    key_block.value = 0.0
            
            # 最初のConfig Pairでの対象シェイプキー（1が前提）もしくは前のConfig PairでTransition後のシェイプキーの値を1にする
            if clothing_avatar_data["name"] == "Template":
                if obj.data.shape_keys:
                    if source_label in obj.data.shape_keys.key_blocks:
                        source_shape_key = obj.data.shape_keys.key_blocks.get(source_label)
                        source_shape_key.value = 1.0
                        print(f"source_label: {source_label} is found in shape keys")
                    else:
                        temp_shape_key_name = f"{source_label}_temp"
                        if temp_shape_key_name in obj.data.shape_keys.key_blocks:
                            obj.data.shape_keys.key_blocks[temp_shape_key_name].value = 1.0
                            print(f"temp_shape_key_name: {temp_shape_key_name} is found in shape keys")
            else:
                # source_blend_shape_settingsを適用
                for source_blend_shape_setting in source_blend_shape_settings:
                    source_blend_shape_name = source_blend_shape_setting.get("name", "")
                    source_blend_shape_value = source_blend_shape_setting.get("value", 0.0)
                    if source_blend_shape_name in obj.data.shape_keys.key_blocks:
                        source_blend_shape_key = obj.data.shape_keys.key_blocks.get(source_blend_shape_name)
                        source_blend_shape_key.value = source_blend_shape_value
                        print(f"source_blend_shape_name: {source_blend_shape_name} is found in shape keys")
                    else:
                        temp_blend_shape_key_name = f"{source_blend_shape_name}_temp"
                        if temp_blend_shape_key_name in obj.data.shape_keys.key_blocks:
                            obj.data.shape_keys.key_blocks[temp_blend_shape_key_name].value = source_blend_shape_value
                            print(f"temp_blend_shape_key_name: {temp_blend_shape_key_name} is found in shape keys")
            
            # blend_shape_key_nameを設定（同名のシェイプキーがある場合は_generatedを付ける）
            blend_shape_key_name = label
            if obj.data.shape_keys and label in obj.data.shape_keys.key_blocks:
                blend_shape_key_name = f"{label}_generated"

            if os.path.exists(field_path):
                print(f"Processing config blend shape field with rigid transform: {label} -> {blend_shape_key_name}")
                generated_shape_key = apply_field_delta_with_rigid_transform_single(obj, field_path, blend_shape_labels, clothing_avatar_data, blend_shape_key_name)
                
                # 該当するラベルの遷移を遅延実行リストに追加
                if config_data and generated_shape_key:
                    deferred_transitions.append({
                        'target_obj': obj,
                        'config_data': config_data,
                        'target_label': label,
                        'target_shape_key_name': generated_shape_key.name,
                        'base_avatar_data': base_avatar_data,
                        'clothing_avatar_data': clothing_avatar_data,
                        'base_avatar_data': base_avatar_data,
                        'save_original_shape_key': False
                    })
                
                # 生成されたシェイプキーの値を0にする
                if generated_shape_key:
                    generated_shape_key.value = 0.0
                    config_generated_shape_keys[generated_shape_key.name] = mask_weights
                    non_relative_shape_keys.add(generated_shape_key.name)
                
                config_blend_shape_labels.add(label)

                label_to_target_shape_key_name[label] = generated_shape_key.name
            else:
                print(f"Warning: Config blend shape field file not found: {field_path}")
            
            # 元のシェイプキー設定を復元
            restore_shape_key_state(obj, original_shape_key_state)
    
    # transition_setsに含まれるがconfig_blend_shape_labelsに含まれないシェイプキーに対して処理
    if config_data and config_data.get('blend_shape_transition_sets', []):
        print("Processing skipped config blendShapeFields...")
        
        transition_sets = config_data.get('blend_shape_transition_sets', [])
        for transition_set in transition_sets:
            label = transition_set["label"]
            if label in config_blend_shape_labels or label == 'Basis':
                continue

            source_label = get_source_label(label, config_data)
            if source_label not in label_to_target_shape_key_name:
                print(f"Skipping {label} - source label {source_label} not in label_to_target_shape_key_name")
                continue

            print(f"Processing skipped config blendShapeField: {label}")
            
            # マスクウェイトを取得
            mask_bones = transition_set.get("mask_bones", [])
            print(f"mask_bones: {mask_bones}")
            mask_weights = None
            if mask_bones:
                mask_weights = create_blendshape_mask(obj, mask_bones, clothing_avatar_data, field_name=label, store_debug_mask=True)
            
            if mask_weights is not None and np.all(mask_weights == 0):
                print(f"Skipping {label} - all mask weights are zero")
                continue
            
            target_shape_key_name = label_to_target_shape_key_name[source_label]
            target_shape_key = obj.data.shape_keys.key_blocks.get(target_shape_key_name)

            if not target_shape_key:
                print(f"Skipping {label} - target shape key {target_shape_key_name} not found")
                continue

            # target_shape_key_nameで指定されるシェイプキーのコピーを作成
            blend_shape_key_name = label
            if obj.data.shape_keys and label in obj.data.shape_keys.key_blocks:
                blend_shape_key_name = f"{label}_generated"
            
            skipped_blend_shape_key = obj.shape_key_add(name=blend_shape_key_name)
        
            for i in range(len(skipped_blend_shape_key.data)):
                skipped_blend_shape_key.data[i].co = target_shape_key.data[i].co.copy()

            print(f"skipped_blend_shape_key: {skipped_blend_shape_key.name}")
            
            if config_data and skipped_blend_shape_key:
                deferred_transitions.append({
                    'target_obj': obj,
                    'config_data': config_data,
                    'target_label': label,
                    'target_shape_key_name': skipped_blend_shape_key.name,
                    'base_avatar_data': base_avatar_data,
                    'clothing_avatar_data': clothing_avatar_data,
                    'save_original_shape_key': False
                })

                print(f"Added deferred transition: {label} -> {skipped_blend_shape_key.name}")

                config_generated_shape_keys[skipped_blend_shape_key.name] = mask_weights
                non_relative_shape_keys.add(skipped_blend_shape_key.name)
                config_blend_shape_labels.add(label)
                label_to_target_shape_key_name[label] = skipped_blend_shape_key.name
    

    # 2. clothing_avatar_dataのblendshapesに含まれないシェイプキーに対して処理　(現在はコピーのみ行う)
    if obj.data.shape_keys:
        # clothing_avatar_dataからblendshapeのリストを作成
        clothing_blendshapes = set()
        if clothing_avatar_data and "blendshapes" in clothing_avatar_data:
            for blendshape in clothing_avatar_data["blendshapes"]:
                clothing_blendshapes.add(blendshape["name"])
        
        # 無限ループ回避のため事前にシェイプキーのリストを取得
        current_shape_key_blocks = [key_block for key_block in obj.data.shape_keys.key_blocks]
        
        # 各シェイプキーについて処理
        for key_block in current_shape_key_blocks:
            if (key_block.name == "Basis" or 
                key_block.name in clothing_blendshapes or 
                key_block == shape_key or 
                key_block.name.endswith("_BaseShape") or
                key_block.name in config_generated_shape_keys.keys() or
                key_block.name in config_blend_shape_labels or
                key_block.name.endswith("_original") or 
                key_block.name.endswith("_generated") or
                key_block.name.endswith("_temp")):
                continue  # Basisまたはclothing_avatar_dataのblendshapesに含まれるもの、または_BaseShapeで終わるもの、またはconfigで生成されたものはスキップ
            
            print(f"Processing additional shape key: {key_block.name}")

            temp_blend_shape_key_name = f"{key_block.name}_generated"
            if temp_blend_shape_key_name in obj.data.shape_keys.key_blocks:
                temp_shape_key = obj.data.shape_keys.key_blocks[temp_blend_shape_key_name]
            else:
                print(f"Creating new shape key: {temp_blend_shape_key_name}")
                temp_shape_key = obj.shape_key_add(name=temp_blend_shape_key_name)
                print(f"temp_shape_key name: {temp_shape_key.name}")
            for i, vertex in enumerate(temp_shape_key.data):
                vertex.co = key_block.data[i].co.copy()
    
    # 遅延されたTransitionをキャッシュシステムと共に実行
    created_shape_key_mask_weights = {}
    shape_keys_to_remove = []
    if deferred_transitions:
        transition_operations, created_shape_key_mask_weights, used_shape_key_names = execute_transitions_with_cache(deferred_transitions, transition_cache, obj, rigid_transformation=True)
        if used_shape_key_names:
            for config_shape_key_name in config_generated_shape_keys:
                if config_shape_key_name not in used_shape_key_names and config_shape_key_name in obj.data.shape_keys.key_blocks:
                    shape_keys_to_remove.append(config_shape_key_name)
    
    for created_shape_key_name, mask_weights in created_shape_key_mask_weights.items():
        if created_shape_key_name in obj.data.shape_keys.key_blocks:
            config_generated_shape_keys[created_shape_key_name] = mask_weights
            non_relative_shape_keys.add(created_shape_key_name)
            config_blend_shape_labels.add(created_shape_key_name)
            label_to_target_shape_key_name[created_shape_key_name] = created_shape_key_name
            print(f"Added created shape key: {created_shape_key_name}")
    
    if overwrite_base_shape_key:
        # base_avatar_dataのblendShapeFieldsを処理する前の準備
        basis_name = 'Basis'
        basis_index = obj.data.shape_keys.key_blocks.find(basis_name)

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        print(f"Shape keys in {obj.name}:")
        for key_block in obj.data.shape_keys.key_blocks:
            print(f"- {key_block.name} (value: {key_block.value})")
        
        original_shape_key_name = f"{shape_key_name}_original"
        for sk in obj.data.shape_keys.key_blocks:
            if sk.name in non_relative_shape_keys and sk.name != basis_name:
                if shape_key_name in obj.data.shape_keys.key_blocks:
                    obj.active_shape_key_index = obj.data.shape_keys.key_blocks.find(sk.name)
                    bpy.ops.mesh.blend_from_shape(shape=shape_key_name, blend=-1, add=True)
                else:
                    print(f"Warning: {shape_key_name} or {shape_key_name}_original is not found in shape keys")

        bpy.context.object.active_shape_key_index = basis_index
        bpy.ops.mesh.blend_from_shape(shape=shape_key_name, blend=1, add=True)

        bpy.ops.object.mode_set(mode='OBJECT')

        if original_shape_key_name in obj.data.shape_keys.key_blocks:
            original_shape_key = obj.data.shape_keys.key_blocks.get(original_shape_key_name)
            obj.shape_key_remove(original_shape_key)
            print(f"Removed shape key: {original_shape_key_name} from {obj.name}")
        
        # 不要なシェイプキーを削除
        if shape_key:
            obj.shape_key_remove(shape_key)

        # configファイルのblendShapeFieldsで生成されたシェイプキーの変位にmask_weightsを適用
        if config_generated_shape_keys:
            print(f"Applying mask weights to generated shape keys: {list(config_generated_shape_keys.keys())}")
            
            # ベースシェイプの頂点位置を取得
            basis_shape_key = obj.data.shape_keys.key_blocks.get(basis_name)
            if basis_shape_key:
                basis_positions = np.array([v.co for v in basis_shape_key.data])
                
                # 各生成されたシェイプキーに対してマスクを適用
                for shape_key_name_to_mask, mask_weights in config_generated_shape_keys.items():
                    if shape_key_name_to_mask == basis_name:
                        continue
                        
                    shape_key_to_mask = obj.data.shape_keys.key_blocks.get(shape_key_name_to_mask)
                    if shape_key_to_mask:
                        # 現在のシェイプキーの頂点位置を取得
                        shape_positions = np.array([v.co for v in shape_key_to_mask.data])
                        
                        # 変位を計算
                        displacement = shape_positions - basis_positions
                        
                        # マスクを適用（変位にmask_weightsを掛ける）
                        if mask_weights is not None:
                            masked_displacement = displacement * mask_weights[:, np.newaxis]
                        else:
                            masked_displacement = displacement
                        
                        # マスク適用後の位置を計算
                        new_positions = basis_positions + masked_displacement
                        
                        # シェイプキーの頂点位置を更新
                        for i, vertex in enumerate(shape_key_to_mask.data):
                            vertex.co = new_positions[i]
                        
                        print(f"Applied mask weights to shape key: {shape_key_name_to_mask}")

    for unused_shape_key_name in shape_keys_to_remove:
        if unused_shape_key_name in obj.data.shape_keys.key_blocks:
            unused_shape_key = obj.data.shape_keys.key_blocks.get(unused_shape_key_name)
            if unused_shape_key:
                obj.shape_key_remove(unused_shape_key)
                print(f"Removed shape key: {unused_shape_key_name} from {obj.name}")
            else:
                print(f"Warning: {unused_shape_key_name} is not found in shape keys")
        else:
            print(f"Warning: {unused_shape_key_name} is not found in shape keys")
    
    return shape_key, config_blend_shape_labels
