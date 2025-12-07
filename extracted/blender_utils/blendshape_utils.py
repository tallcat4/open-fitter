import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from blender_utils.bone_utils import get_child_bones_recursive
from io_utils.load_deformation_field_num_steps import load_deformation_field_num_steps
import bpy
import numpy as np
import os
import sys

# Merged from apply_blendshape_values.py

def apply_blendshape_values(mesh_obj: bpy.types.Object, blendshapes: list) -> None:
    """Apply blendshape values from avatar data."""
    if not mesh_obj.data.shape_keys:
        return
        
    # Create a mapping of shape key names
    shape_keys = mesh_obj.data.shape_keys.key_blocks
    
    # Apply values
    for blendshape in blendshapes:
        shape_key_name = blendshape["name"]
        if shape_key_name in shape_keys:
            # Set value to 1% of the specified value
            shape_keys[shape_key_name].value = blendshape["value"] * 0.01

# Merged from get_blendshape_groups.py

def get_blendshape_groups(avatar_data: dict) -> dict:
    """
    アバターデータからBlendShapeGroupsを取得する
    
    Parameters:
        avatar_data: アバターデータ
        
    Returns:
        dict: BlendShapeGroup名をキーとし、そのグループに含まれるBlendShape名のリストを値とする辞書
    """
    groups = {}
    blend_shape_groups = avatar_data.get('blendShapeGroups', [])
    for group in blend_shape_groups:
        group_name = group.get('name', '')
        blend_shape_fields = group.get('blendShapeFields', [])
        groups[group_name] = blend_shape_fields
    return groups

# Merged from calculate_blendshape_settings_difference.py

def calculate_blendshape_settings_difference(settings1: list, settings2: list, 
                                           blend_shape_fields: dict, 
                                           config_dir: str) -> float:
    """
    BlendShapeSettings間の状態差異を計算する
    
    Parameters:
        settings1: 最初のBlendShapeSettings
        settings2: 次のBlendShapeSettings  
        blend_shape_fields: BlendShapeFieldsの辞書
        config_dir: 設定ファイルのディレクトリ
        
    Returns:
        float: 差異の量
    """
    # 設定を辞書形式に変換
    dict1 = {item['name']: item['value'] for item in settings1}
    dict2 = {item['name']: item['value'] for item in settings2}
    
    # すべてのBlendShape名を収集
    all_blend_shapes = set(dict1.keys()) | set(dict2.keys())
    
    total_difference = 0.0
    
    for blend_shape_name in all_blend_shapes:
        value1 = dict1.get(blend_shape_name, 0.0)
        value2 = dict2.get(blend_shape_name, 0.0)
        
        # 値の差の絶対値
        value_diff = abs(value1 - value2)
        
        if value_diff > 0.0 and blend_shape_name in blend_shape_fields:
            # 変形データのファイルパスを取得
            field_file_path = blend_shape_fields[blend_shape_name]['filePath']
            full_field_path = os.path.join(config_dir, field_file_path)
            
            try:
                # 変形データを読み込み
                data = np.load(full_field_path, allow_pickle=True)
                delta_positions = data['all_delta_positions']
                
                total_max_displacement = 0.0
                for i in range(len(delta_positions)):
                    max_displacement = np.max(np.linalg.norm(delta_positions[i], axis=1))
                    total_max_displacement += max_displacement
                
                # if len(delta_positions) > 0:
                #     first_step_deltas = delta_positions[0]
                #     max_displacement = np.max(np.linalg.norm(first_step_deltas, axis=1))
                
                # 差の絶対値に最大変位を掛けて加算
                total_difference += value_diff * total_max_displacement
                
            except Exception as e:
                print(f"Warning: Could not load deformation data for {blend_shape_name}: {e}")
                # データを読み込めない場合は値の差をそのまま使用
                total_difference += value_diff
    
    return total_difference

# Merged from create_blendshape_mask.py

def create_blendshape_mask(target_obj, mask_bones, clothing_avatar_data, field_name="", store_debug_mask=True):
    """
    指定されたボーンとその子ボーンのウェイトを合算したマスクを作成する

    Parameters:
        target_obj: 対象のメッシュオブジェクト
        mask_bones: マスクに使用するHumanoidボーンのリスト
        clothing_avatar_data: 衣装アバターのデータ（Humanoidボーン名の変換に使用）
        field_name: フィールド名（デバッグ用の頂点グループ名に使用）
        store_debug_mask: デバッグ用のマスク頂点グループを保存するかどうか

    Returns:
        numpy.ndarray: 各頂点のマスクウェイト値の配列
    """
    #print(f"mask_bones: {mask_bones}")
    
    mask_weights = np.zeros(len(target_obj.data.vertices))

    # アーマチュアを取得
    armature_obj = None
    for modifier in target_obj.modifiers:
        if modifier.type == 'ARMATURE':
            armature_obj = modifier.object
            break
            
    if not armature_obj:
        print(f"Warning: No armature found for {target_obj.name}")
        return mask_weights

    # Humanoidボーン名からボーン名への変換マップを作成
    humanoid_to_bone = {}
    for bone_map in clothing_avatar_data.get("humanoidBones", []):
        if "humanoidBoneName" in bone_map and "boneName" in bone_map:
            humanoid_to_bone[bone_map["humanoidBoneName"]] = bone_map["boneName"]
    
    # 補助ボーンのマッピングを作成
    auxiliary_bones = {}
    for aux_set in clothing_avatar_data.get("auxiliaryBones", []):
        humanoid_bone = aux_set["humanoidBoneName"]
        auxiliary_bones[humanoid_bone] = aux_set["auxiliaryBones"]
    
    # デバッグ用に処理したボーンの情報を収集
    processed_bones = set()
    
    # 対象となるすべてのボーンを収集（Humanoidボーン、補助ボーン、それらの子ボーン）
    target_bones = set()
    
    # 各Humanoidボーンに対して処理
    for humanoid_bone in mask_bones:
        # メインのボーンを追加
        bone_name = humanoid_to_bone.get(humanoid_bone)
        if bone_name:
            target_bones.add(bone_name)
            processed_bones.add(bone_name)
            # 子ボーンを追加
            target_bones.update(get_child_bones_recursive(bone_name, armature_obj, clothing_avatar_data))
        
        # 補助ボーンとその子ボーンを追加
        if humanoid_bone in auxiliary_bones:
            for aux_bone in auxiliary_bones[humanoid_bone]:
                target_bones.add(aux_bone)
                processed_bones.add(aux_bone)
                # 補助ボーンの子ボーンを追加
                target_bones.update(get_child_bones_recursive(aux_bone, armature_obj, clothing_avatar_data))
    
    #print(f"target_bones: {target_bones}")
    
    # 各頂点のウェイトを計算
    for vert in target_obj.data.vertices:
        for bone_name in target_bones:
            if bone_name in target_obj.vertex_groups:
                group = target_obj.vertex_groups[bone_name]
                for g in vert.groups:
                    if g.group == group.index:
                        mask_weights[vert.index] += g.weight
                        break
    
    # ウェイトを0-1の範囲にクランプ
    mask_weights = np.clip(mask_weights, 0.0, 1.0)
    
    # デバッグ用の頂点グループを作成
    if store_debug_mask:
        # 頂点グループ名を生成
        group_name = f"DEBUG_Mask_{field_name}" if field_name else "DEBUG_Mask"
        
        # 既存のグループがあれば削除
        if group_name in target_obj.vertex_groups:
            target_obj.vertex_groups.remove(target_obj.vertex_groups[group_name])
        
        # 新しいグループを作成
        debug_group = target_obj.vertex_groups.new(name=group_name)
        
        # ウェイトを設定
        for vert_idx, weight in enumerate(mask_weights):
            if weight > 0:
                debug_group.add([vert_idx], weight, 'REPLACE')
        
        print(f"Created debug mask group '{group_name}' using bones: {sorted(processed_bones)}")
    
    return mask_weights

# Merged from process_single_blendshape_transition_set.py

def process_single_blendshape_transition_set(current_settings: list, next_settings: list, 
                                           label: str, source_label: str, blend_shape_groups: dict, 
                                           blend_shape_fields: dict, inverted_blend_shape_fields: dict,
                                           current_config_dir: str, mask_bones: list = None) -> dict:
    """
    単一のBlendShape設定セット間の遷移を処理する
    
    Parameters:
        current_settings: 現在の設定リスト
        next_settings: 次の設定リスト
        label: ラベル名（'Basis'または具体的なblendShapeFieldsラベル）
        blend_shape_groups: BlendShapeGroupsの辞書
        blend_shape_fields: BlendShapeFieldsの辞書
        inverted_blend_shape_fields: invertedBlendShapeFieldsの辞書
        current_config_dir: 現在の設定ファイルのディレクトリ
        
    Returns:
        list: 遷移データのリスト
    """
    # 設定を辞書形式に変換
    current_dict = {item['name']: item['value'] for item in current_settings}
    next_dict = {item['name']: item['value'] for item in next_settings}
    
    # すべてのBlendShape名を収集
    all_blend_shapes = set(current_dict.keys()) | set(next_dict.keys())
    
    transitions = []

    processed_blend_shapes = set()
    
    for blend_shape_name in all_blend_shapes:

        if blend_shape_name in processed_blend_shapes:
            continue

        current_value = current_dict.get(blend_shape_name, 0.0)
        next_value = next_dict.get(blend_shape_name, 0.0)
        
        # 値に変化がある場合のみ処理
        if current_value != next_value:
            transition = {
                'label': label,
                'blend_shape_name': blend_shape_name,
                'from_value': current_value,
                'to_value': next_value,
                'operations': [],
            }
            
            # BlendShapeGroupsでの特別処理
            group_processed = False
            for group_name, group_blend_shapes in blend_shape_groups.items():
                if blend_shape_name in group_blend_shapes:
                    # グループ内の現在の非ゼロ値を探す
                    current_non_zero = None
                    for group_blend_shape in group_blend_shapes:
                        if current_dict.get(group_blend_shape, 0.0) != 0.0:
                            current_non_zero = group_blend_shape
                            break
                    
                    # グループ内の次の非ゼロ値を探す
                    next_non_zero = None
                    for group_blend_shape in group_blend_shapes:
                        if next_dict.get(group_blend_shape, 0.0) != 0.0:
                            next_non_zero = group_blend_shape
                            break
                    
                    # グループ内で異なるBlendShapeが正の値をとる場合
                    if current_non_zero and next_non_zero and current_non_zero != next_non_zero:
                        # 最初に前の値を0にする操作
                        field_file_path = inverted_blend_shape_fields[current_non_zero]['filePath']
                        num_steps = load_deformation_field_num_steps(field_file_path, current_config_dir)
                        current_value = current_dict.get(current_non_zero, 0.0)
                        from_step = int((1.0 - current_value) * num_steps + 0.5)
                        to_step = num_steps
                        transition['operations'].append({
                            'type': 'set_to_zero',
                            'blend_shape': current_non_zero,
                            'from_value': current_value,
                            'to_value': 0.0,
                            'file_path': os.path.join(current_config_dir, field_file_path),
                            'mask_bones': inverted_blend_shape_fields[current_non_zero]['maskBones'],
                            'num_steps': num_steps,
                            'from_step': from_step,
                            'to_step': to_step,
                            'field_type': 'inverted'
                        })
                        # 次に新しい値を設定する操作
                        field_file_path = blend_shape_fields[next_non_zero]['filePath']
                        num_steps = load_deformation_field_num_steps(field_file_path, current_config_dir)
                        next_value = next_dict.get(next_non_zero, 0.0)
                        from_step = 0
                        to_step = int(next_value * num_steps + 0.5)
                        transition['operations'].append({
                            'type': 'set_value',
                            'blend_shape': next_non_zero,
                            'from_value': 0.0,
                            'to_value': next_value,
                            'file_path': os.path.join(current_config_dir, field_file_path),
                            'mask_bones': blend_shape_fields[next_non_zero]['maskBones'],
                            'num_steps': num_steps,
                            'from_step': from_step,
                            'to_step': to_step,
                            'field_type': 'normal'
                        })
                        group_processed = True

                        processed_blend_shapes.add(current_non_zero)
                        processed_blend_shapes.add(next_non_zero)

                        break
            
            # グループ処理がされなかった場合は単純な値の変更として記録
            if not group_processed:
                if current_value > next_value:
                    # 値の減少
                    field_file_path = inverted_blend_shape_fields[blend_shape_name]['filePath']
                    num_steps = load_deformation_field_num_steps(field_file_path, current_config_dir)
                    from_step = int((1.0 - current_value) * num_steps + 0.5)
                    to_step = int((1.0 - next_value) * num_steps + 0.5)
                    transition['operations'].append({
                        'type': 'decrease',
                        'blend_shape': blend_shape_name,
                        'from_value': current_value,
                        'to_value': next_value,
                        'file_path': os.path.join(current_config_dir, field_file_path),
                        'mask_bones': inverted_blend_shape_fields[blend_shape_name]['maskBones'],
                        'num_steps': num_steps,
                        'from_step': from_step,
                        'to_step': to_step,
                        'field_type': 'inverted'
                    })
                else:
                    # 値の増加
                    field_file_path = blend_shape_fields[blend_shape_name]['filePath']
                    num_steps = load_deformation_field_num_steps(field_file_path, current_config_dir)
                    from_step = int(current_value * num_steps + 0.5)
                    to_step = int(next_value * num_steps + 0.5)
                    transition['operations'].append({
                        'type': 'increase',
                        'blend_shape': blend_shape_name,
                        'from_value': current_value,
                        'to_value': next_value,
                        'file_path': os.path.join(current_config_dir, field_file_path),
                        'mask_bones': blend_shape_fields[blend_shape_name]['maskBones'],
                        'num_steps': num_steps,
                        'from_step': from_step,
                        'to_step': to_step,
                        'field_type': 'normal'
                    })
            
            processed_blend_shapes.add(blend_shape_name)
            
            transitions.append(transition)
            print(f"  Transition detected [{label}]: {blend_shape_name} {current_value} -> {next_value}")
    
    transition_set = {
        'label': label,
        'source_label': source_label,  # 選ばれたtargetBlendShapeSettingsのlabelを記録
        'mask_bones': mask_bones,
        'current_settings': current_settings,
        'next_settings': next_settings,
        'transitions': transitions
    }
    
    return transition_set

# Merged from set_highheel_shapekey_values.py

def set_highheel_shapekey_values(clothing_meshes, blend_shape_labels=None, base_avatar_data=None):
    """
    Highheelを含むシェイプキーの値を1にする
    
    Parameters:
        clothing_meshes: 衣装メッシュのリスト
        blend_shape_labels: ブレンドシェイプラベルのリスト
        base_avatar_data: ベースアバターデータ
    """
    if not blend_shape_labels or not base_avatar_data:
        return
    
    # base_avatar_dataのblendShapeFieldsの存在確認
    if "blendShapeFields" not in base_avatar_data:
        return
    
    # まずHighheelを含むラベルを検索
    highheel_labels = [label for label in blend_shape_labels if "highheel" in label.lower() and "off" not in label.lower()]
    base_highheel_fields = [field for field in base_avatar_data["blendShapeFields"] 
                          if "highheel" in field.get("label", "").lower() and "off" not in field.get("label", "").lower()]
    
    # Highheelを含むラベルが無い場合は、Heelを含むラベルを検索
    if not highheel_labels:
        highheel_labels = [label for label in blend_shape_labels if "heel" in label.lower() and "off" not in label.lower()]
        base_highheel_fields = [field for field in base_avatar_data["blendShapeFields"] 
                              if "heel" in field.get("label", "").lower() and "off" not in field.get("label", "").lower()]
    
    # 条件：blend_shape_labelsに該当ラベルが一つだけ、かつbase_avatar_dataに該当フィールドが一つだけ
    if len(highheel_labels) != 1 or len(base_highheel_fields) != 1:
        return
    
    # 唯一のラベルとフィールドを取得
    target_label = highheel_labels[0]
    base_field = base_highheel_fields[0]
    base_label = base_field.get("label", "")
    
    # 各メッシュのシェイプキーをチェック
    for obj in clothing_meshes:
        if not obj.data.shape_keys:
            continue
        
        # base_avatar_dataのラベルでシェイプキーを探す
        if base_label in obj.data.shape_keys.key_blocks:
            shape_key = obj.data.shape_keys.key_blocks[base_label]
            shape_key.value = 1.0
            print(f"Set shape key '{base_label}' value to 1.0 on {obj.name}")

# Merged from merge_and_clean_generated_shapekeys.py

def merge_and_clean_generated_shapekeys(clothing_meshes, blend_shape_labels=None):
    """
    apply_blendshape_deformation_fieldsで作成されたシェイプキーを削除し、
    _generatedサフィックス付きシェイプキーを処理する
    
    _generatedで終わるシェイプキー名から_generatedを除いた名前のシェイプキーが存在する場合、
    そのシェイプキーを_generatedシェイプキーの内容で上書きして、_generatedシェイプキーを削除する
    
    Parameters:
        clothing_meshes: 衣装メッシュのリスト
        blend_shape_labels: ブレンドシェイプラベルのリスト
    """
    for obj in clothing_meshes:
        if not obj.data.shape_keys:
            continue
        
        # _generatedサフィックス付きシェイプキーの処理
        generated_shape_keys = []
        for shape_key in obj.data.shape_keys.key_blocks:
            if shape_key.name.endswith("_generated"):
                generated_shape_keys.append(shape_key.name)
        
        # _generatedシェイプキーを対応するベースシェイプキーに統合
        for generated_name in generated_shape_keys:
            base_name = generated_name[:-10]  # "_generated"を除去
            
            generated_key = obj.data.shape_keys.key_blocks.get(generated_name)
            base_key = obj.data.shape_keys.key_blocks.get(base_name)
            
            if generated_key and base_key:
                # generatedシェイプキーの内容でベースシェイプキーを上書き
                for i, point in enumerate(generated_key.data):
                    base_key.data[i].co = point.co
                print(f"Merged {generated_name} into {base_name} for {obj.name}")
                
                # generatedシェイプキーを削除
                obj.shape_key_remove(generated_key)
                print(f"Removed generated shape key: {generated_name} from {obj.name}")
        
        # 従来の機能: blend_shape_labelsで指定されたシェイプキーの削除
        if blend_shape_labels:
            shape_keys_to_remove = []
            for label in blend_shape_labels:
                shape_key_name = f"{label}_BaseShape"
                if shape_key_name in obj.data.shape_keys.key_blocks:
                    shape_keys_to_remove.append(shape_key_name)
            
            for label in blend_shape_labels:
                shape_key_name = f"{label}_temp"
                if shape_key_name in obj.data.shape_keys.key_blocks:
                    shape_keys_to_remove.append(shape_key_name)
            
            # シェイプキーを削除
            for shape_key_name in shape_keys_to_remove:
                shape_key = obj.data.shape_keys.key_blocks.get(shape_key_name)
                if shape_key:
                    obj.shape_key_remove(shape_key)
                    print(f"Removed shape key: {shape_key_name} from {obj.name}")

        # 不要なシェイプキーを削除
        shape_keys_to_remove = []
        for shape_key in obj.data.shape_keys.key_blocks:
            if shape_key.name.endswith(".MFTemp"):
                shape_keys_to_remove.append(shape_key.name)
        for shape_key_name in shape_keys_to_remove:
            shape_key = obj.data.shape_keys.key_blocks.get(shape_key_name)
            if shape_key:
                obj.shape_key_remove(shape_key)
                print(f"Removed shape key: {shape_key_name} from {obj.name}")