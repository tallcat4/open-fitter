import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from blendshape_operation import apply_blendshape_operation_with_shape_key_name
from blender_utils.create_blendshape_mask import create_blendshape_mask


def execute_transitions_with_cache(deferred_transitions, transition_cache, target_obj, rigid_transformation=False):
    """遅延されたTransitionをキャッシュシステムを使って実行"""
    print(f"Executing {len(deferred_transitions)} deferred transitions with caching...")
    
    # BlendShapeGroupsの情報を取得（最初のtransition_dataから）
    blendshape_groups = None
    if deferred_transitions:
        base_avatar_data = deferred_transitions[0].get('base_avatar_data')
        if base_avatar_data:
            blendshape_groups = base_avatar_data.get('blendShapeGroups', [])
    
    # labelに対応する初期シェイプキーの名前shape_key_nameを取得
    # 初期状態をキャッシュに保存
    target_shape_key_label_to_name = {}
    for transition_data in deferred_transitions:
        config_data = transition_data['config_data']
        shape_key_name = transition_data['target_shape_key_name']
        shape_key_label = transition_data['target_label']
        target_shape_key_label_to_name[shape_key_label] = shape_key_name

        target_shape_key = None
        if target_obj.data.shape_keys and shape_key_name and shape_key_name in target_obj.data.shape_keys.key_blocks:
            target_shape_key = target_obj.data.shape_keys.key_blocks.get(shape_key_name)
        
        if target_shape_key is None:
            print(f"Target shape key {shape_key_name} / {target_shape_key.name} not found")
            continue

        print(f"Target shape key {shape_key_name} / {target_shape_key.name} found")

        # 現在のtarget_shape_keyの位置を取得
        initial_vertices = np.array([v.co for v in target_shape_key.data])

        initial_settings = []
        if shape_key_label == 'Basis':
            initial_settings = config_data.get('targetBlendShapeSettings', [])
        else:
            blend_fields = config_data.get('blendShapeFields', [])
            for blend_field in blend_fields:
                if blend_field['label'] == shape_key_label:
                    initial_settings = blend_field.get('targetBlendShapeSettings', [])
                    break
            if not initial_settings:
                initial_settings = config_data.get('targetBlendShapeSettings', [])
        
        initial_blendshape_values = {}
        for setting in initial_settings:
            blend_shape_name = setting.get('name', '')
            blend_shape_value = setting.get('value', 0.0)
            if blend_shape_name:
                initial_blendshape_values[blend_shape_name] = blend_shape_value
        
        # 初期状態をキャッシュに保存
        transition_cache.store_result(initial_blendshape_values, initial_vertices, initial_blendshape_values)
        print(f"Cached initial state for {shape_key_label} with {len(initial_blendshape_values)} BlendShape values")
    
    initial_vertices_dict = {}
    
    # 各transition_dataのoperationsとtransition_setを事前に収集
    transition_operations = []
    for transition_data in deferred_transitions:
        config_data = transition_data['config_data']
        target_label = transition_data['target_label']
        target_shape_key_name = transition_data['target_shape_key_name']
        clothing_avatar_data = transition_data['clothing_avatar_data']
        
        # Transitionの詳細を取得
        transition_sets = config_data.get('blend_shape_transition_sets', [])
        target_transition_set = None
        target_shape_key_name = None
        for transition_set in transition_sets:
            source_label = transition_set.get('source_label', '')
            target_shape_key_name = target_shape_key_label_to_name.get(source_label, '')
            print(f"source_label: {source_label}, target_shape_key_name: {target_shape_key_name}")
            if transition_set.get('label', '') == target_label and target_shape_key_name in target_obj.data.shape_keys.key_blocks:
                target_transition_set = transition_set
                print(f"Found transition set for {target_label} with source label {source_label}")
                break
        
        if not target_transition_set:
            # デフォルトのTransitionを試行
            default_transition_sets = config_data.get('blend_shape_default_transition_sets', [])
            for default_transition_set in default_transition_sets:
                source_label = default_transition_set.get('source_label', '')
                target_shape_key_name = target_shape_key_label_to_name.get(source_label, '')
                print(f"source_label: {source_label}, target_shape_key_name: {target_shape_key_name}")
                if default_transition_set.get('label', '') == target_label and target_shape_key_name in target_obj.data.shape_keys.key_blocks:
                    target_transition_set = default_transition_set
                    print(f"Found default transition set for {target_label} with source label {source_label}")
                    break
        
        if not target_transition_set:
            print(f"No transition set found for {target_label}")
            continue
        
        # transition_setのcurrent_settingsから初期BlendShape値を取得
        current_settings = target_transition_set.get('current_settings', [])
        source_label = target_transition_set['source_label']
        initial_blendshape_values = {}
        
        # current_settingsからBlendShapeの値を設定
        for setting in current_settings:
            blend_shape_name = setting.get('name', '')
            blend_shape_value = setting.get('value', 0.0)
            if blend_shape_name:
                initial_blendshape_values[blend_shape_name] = blend_shape_value
        
        # 選択された最もTransition後の状態に近いShapeKeyを取得
        target_shape_key_name = target_shape_key_label_to_name.get(source_label, None)
        target_shape_key = None
        if target_obj.data.shape_keys and target_shape_key_name and target_shape_key_name in target_obj.data.shape_keys.key_blocks:
            target_shape_key = target_obj.data.shape_keys.key_blocks.get(target_shape_key_name)
        
        if target_shape_key is None:
            print(f"Target shape key {target_shape_key_name} not found")
            continue
        else:
            print(f"Target shape key {target_shape_key_name} / {target_shape_key.name} found")
            
        # 現在のtarget_shape_keyの位置を取得
        initial_vertices = np.array([v.co for v in target_shape_key.data])

        print(f"target_transition_set: {target_transition_set}")

        initial_vertices_dict[transition_data['target_shape_key_name']] = initial_vertices.copy()
        
        for transition in target_transition_set.get('transitions', []):
            operations = transition.get('operations', [])
            if not operations:
                print(f"No operations found for {target_label}")
                continue
            
            print(f"number of operations: {len(operations)}")
            print(f"operations: {operations}")
            
            # operationsとtransition_dataをセットで保存（初期BlendShape値も含める）
            transition_operations.append({
                'operations': operations,
                'transition_data': transition_data,
                'current_blendshape_values': initial_blendshape_values.copy(),
                'initial_vertices': initial_vertices.copy(),
                'current_vertices': initial_vertices.copy(),
                'mask_bones': target_transition_set.get("maskBones", [])
            })
        
        if target_transition_set.get('transitions', []) is None or len(target_transition_set.get('transitions', [])) == 0:
            print(f"No transitions found for {target_label}")
            # 空のoperationsとtransition_dataを保存（初期BlendShape値も含める）
            transition_operations.append({
                'operations': [],
                'transition_data': transition_data,
                'current_blendshape_values': initial_blendshape_values.copy(),
                'initial_vertices': initial_vertices.copy(),
                'current_vertices': initial_vertices.copy(),
                'mask_bones': target_transition_set.get("maskBones", [])
            })
    
    # 最大operation数を取得
    max_operations = 0
    for item in transition_operations:
        max_operations = max(max_operations, len(item['operations']))
    
    # operation順序別に実行
    for operation_index in range(max_operations):
        print(f"Executing operation index {operation_index + 1}")
        
        for item in transition_operations:
            operations = item['operations']
            transition_data = item['transition_data']
            target_label = transition_data['target_label']
            target_shape_key_name = transition_data['target_shape_key_name']
            clothing_avatar_data = transition_data['clothing_avatar_data']
            base_avatar_data = transition_data['base_avatar_data']
            current_blendshape_values = item['current_blendshape_values']

            print(f"target_label: {target_label}")
            
            # 現在のoperation_indexが存在するかチェック
            if operation_index >= len(operations):
                continue
            
            operation = operations[operation_index]
            changing_shape_key = operation.get('blend_shape', '')
            if not changing_shape_key:
                print(f"Warning: No target blend_shape found in operation for {operation_index}")
                continue
            
            # operationのto_valueを取得してBlendShape値を更新
            target_blendshape_values = current_blendshape_values.copy()
            if 'to_value' in operation:
                target_blendshape_values[changing_shape_key] = operation['to_value']
            else:
                print(f"Warning: No to_value found in operation for {changing_shape_key}")
                continue
            
            # ターゲットBlendShapeを取得
            target_shape_key = None
            if target_obj.data.shape_keys and target_shape_key_name in target_obj.data.shape_keys.key_blocks:
                target_shape_key = target_obj.data.shape_keys.key_blocks.get(target_shape_key_name)
            
            if target_shape_key is None:
                print(f"Target shape key {target_shape_key_name} not found")
                continue
            
            operation_label = operation['blend_shape']
            blendshape_fields = base_avatar_data.get('blendShapeFields', [])
            mask_weights = None
            for blend_field in blendshape_fields:
                if blend_field['label'] == operation_label:
                    mask_bones = blend_field.get("maskBones", [])
                    if mask_bones:
                        print(f"mask_bones is found for {operation_label} : {mask_bones}")
                        mask_weights = create_blendshape_mask(target_obj, mask_bones, clothing_avatar_data, field_name=operation_label, store_debug_mask=False)
                        break
            # mask_weightsがNoneの場合はmask_weightsを1.0にする
            if mask_weights is None:
                print(f"mask_weights is None for {operation_label}")
                mask_weights = [1.0] * len(target_obj.data.vertices)
            
            if mask_weights is not None and np.all(mask_weights == 0):
                print(f"Skipping operation for {operation_label} - all mask weights are zero")
                item['current_blendshape_values'] = target_blendshape_values.copy()
                continue
            
            # キャッシュから線形補間で結果を取得を試行
            interpolated_vertices = transition_cache.interpolate_result(target_blendshape_values, changing_shape_key, blendshape_groups)
            
            if interpolated_vertices is not None:
                print(f"Using cached interpolation for {changing_shape_key} = {target_blendshape_values[changing_shape_key]} (label: {transition_data['target_label']})")
                
                #現在のcurrent_verticesの位置を更新
                current_vertices = item['current_vertices']
                for i in range(len(target_obj.data.vertices)):
                    current_vertices[i] = (1.0 - mask_weights[i]) * current_vertices[i] + mask_weights[i] * interpolated_vertices[i]
                
                item['current_blendshape_values'] = target_blendshape_values.copy()
                continue
            
            # キャッシュにない場合は実際にoperationを実行してキャッシュに保存
            print(f"Executing and caching operation for {changing_shape_key} = {target_blendshape_values[changing_shape_key]} (label: {transition_data['target_label']})")

            current_vertices = item['current_vertices']

            # current_verticesから一時的なシェイプキーを作成
            temp_shape_key_name = f"{changing_shape_key}_transition_operation"
            temp_shape_key = None
            if temp_shape_key_name in target_obj.data.shape_keys.key_blocks:
                temp_shape_key = target_obj.data.shape_keys.key_blocks[temp_shape_key_name]
            else:
                temp_shape_key = target_obj.shape_key_add(name=temp_shape_key_name)
            for i in range(len(target_obj.data.vertices)):
                temp_shape_key.data[i].co = current_vertices[i] 

            # BlendShapeSettingsを適用
            # この時点でtemp_shape_key.dataの位置は変更されている
            apply_blendshape_operation_with_shape_key_name(target_obj, operation, temp_shape_key_name, rigid_transformation)
            
            # 現在のcurrent_verticesの位置を更新
            for i in range(len(target_obj.data.vertices)):
                current_vertices[i] = (1.0 - mask_weights[i]) * current_vertices[i] + mask_weights[i] * temp_shape_key.data[i].co

            # 一時的なシェイプキーを削除
            target_obj.shape_key_remove(temp_shape_key)
            
            # 結果をキャッシュに保存
            transition_cache.store_result(target_blendshape_values, current_vertices, target_blendshape_values)
            
            item['current_blendshape_values'] = target_blendshape_values.copy()
            print(f"Updated BlendShape values for {transition_data['target_label']}: {changing_shape_key} = {target_blendshape_values[changing_shape_key]}")
    
    for target_shape_key_name, initial_vertices in initial_vertices_dict.items():
        target_shape_key = None
        if target_obj.data.shape_keys and target_shape_key_name in target_obj.data.shape_keys.key_blocks:
            target_shape_key = target_obj.data.shape_keys.key_blocks.get(target_shape_key_name)
        
        if target_shape_key is None:
            print(f"Initialize: Target shape key {target_shape_key_name} / {target_shape_key.name} not found")
            continue
        else:
            print(f"Initialize: Target shape key {target_shape_key_name} / {target_shape_key.name} found")

        for i in range(len(target_obj.data.vertices)):
            target_shape_key.data[i].co = initial_vertices[i]
    
    #transition_operationsの最後のcurrent_verticesを取得し、それをtarget_labelと同じ名前のシェイプキーに適用する
    #その際にtransition_setのmask_weightsを適用する
    used_shape_key_names = set()
    created_shape_key_names = []
    created_shape_key_mask_weights = {}
    
    for item in transition_operations:
        target_shape_key_name = item['transition_data']['target_shape_key_name']
        clothing_avatar_data = item['transition_data']['clothing_avatar_data']
        target_label = item['transition_data']['target_label']

        # target_labelがBasisの場合はtarget_shape_key_nameを使用、それ以外はtarget_labelを使用
        shape_key_to_use = target_shape_key_name if target_label == 'Basis' else target_label
        shape_key_created = False
        
        # シェイプキーを取得または作成
        # target_obj.data.shape_keysが存在し、shape_key_to_useがtarget_obj.data.shape_keys.key_blocksに存在する場合はtarget_shape_keyを取得
        # ただし、末尾に{shape_key_to_use}_generatedがある場合はそちらを優先する
        target_shape_key = None
        generated_shape_key_name = f"{shape_key_to_use}_generated"
        if target_obj.data.shape_keys and generated_shape_key_name in target_obj.data.shape_keys.key_blocks:
            target_shape_key = target_obj.data.shape_keys.key_blocks.get(generated_shape_key_name)
            print(f"Generated target shape key {generated_shape_key_name} found")
        elif target_obj.data.shape_keys and shape_key_to_use in target_obj.data.shape_keys.key_blocks:
            target_shape_key = target_obj.data.shape_keys.key_blocks.get(shape_key_to_use)
            print(f"Target shape key {shape_key_to_use} found")
        else:
            # シェイプキーが存在しない場合は新規作成（Basisは作成しない）
            if target_label != 'Basis':
                if not target_obj.data.shape_keys:
                    # Basisシェイプキーがない場合は作成
                    target_obj.shape_key_add(name='Basis', from_mix=False)
                
                target_shape_key = target_obj.shape_key_add(name=shape_key_to_use, from_mix=False)
                print(f"Created new shape key: {shape_key_to_use}")
                created_shape_key_names.append(shape_key_to_use)
                shape_key_created = True
            else:
                print(f"Warning: Basis shape key {shape_key_to_use} not found")
        
        if target_shape_key is None:
            print(f"Failed to get or create shape key: {shape_key_to_use}")
            continue
        
        used_shape_key_names.add(target_shape_key.name)
        
        initial_vertices = item['initial_vertices']
        current_vertices = item['current_vertices']
        mask_bones = item['mask_bones']
        mask_weights = None
        if mask_bones:
            mask_weights = create_blendshape_mask(target_obj, mask_bones, clothing_avatar_data, field_name=target_label, store_debug_mask=False)
        if mask_weights is None:
            mask_weights = [1.0] * len(target_obj.data.vertices)
        
        if shape_key_created:
            created_shape_key_mask_weights[target_shape_key.name] = mask_weights
        
        for i in range(len(target_obj.data.vertices)):
            target_shape_key.data[i].co = mask_weights[i] * (current_vertices[i] - initial_vertices[i]) + target_shape_key.data[i].co
    
    print("Finished executing deferred transitions")
    print(f"Created shape keys: {created_shape_key_names}")

    return transition_operations, created_shape_key_mask_weights, used_shape_key_names
