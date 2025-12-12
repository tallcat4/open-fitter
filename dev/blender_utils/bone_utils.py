import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common_utils.strip_numeric_suffix import strip_numeric_suffix
from io_utils.io_utils import load_avatar_data
from typing import Dict
from typing import Dict, Tuple
import bpy
import os
import sys

# Merged from build_bone_hierarchy.py

def build_bone_hierarchy(bone_node: dict, bone_parents: Dict[str, str], current_path: list):
    """
    ボーン階層から親子関係のマッピングを再帰的に構築する

    Parameters:
        bone_node (dict): 現在のボーンノード
        bone_parents (Dict[str, str]): ボーン名から親ボーン名へのマッピング
        current_path (list): 現在のパス上のボーン名のリスト
    """
    bone_name = bone_node['name']
    if current_path:
        bone_parents[bone_name] = current_path[-1]
    
    current_path.append(bone_name)
    for child in bone_node.get('children', []):
        build_bone_hierarchy(child, bone_parents, current_path)
    current_path.pop()

# Merged from get_bone_name_from_humanoid.py

def get_bone_name_from_humanoid(avatar_data: dict, humanoid_bone_name: str) -> str:
    """
    humanoidBoneNameから実際のボーン名を取得する
    
    Parameters:
        avatar_data: アバターデータ
        humanoid_bone_name: ヒューマノイドボーン名
        
    Returns:
        実際のボーン名、見つからない場合はNone
    """
    for bone_map in avatar_data.get("humanoidBones", []):
        if bone_map["humanoidBoneName"] == humanoid_bone_name:
            return bone_map["boneName"]
    return None

# Merged from get_bone_parent_map.py

def get_bone_parent_map(bone_hierarchy: dict) -> dict:
    """
    Create a map of bones to their parents from the hierarchy.
    
    Parameters:
        bone_hierarchy: Bone hierarchy data from avatar data
    
    Returns:
        Dictionary mapping bone names to their parent bone names
    """
    parent_map = {}
    
    def traverse_hierarchy(node, parent=None):
        current_bone = node["name"]
        parent_map[current_bone] = parent
        
        for child in node.get("children", []):
            traverse_hierarchy(child, current_bone)
    
    traverse_hierarchy(bone_hierarchy)
    return parent_map

# Merged from get_child_bones_recursive.py

def get_child_bones_recursive(bone_name: str, armature_obj: bpy.types.Object, clothing_avatar_data: dict = None, is_root: bool = True) -> set:
    """
    指定されたボーンのすべての子ボーンを再帰的に取得する
    最初に指定されたボーンではないHumanoidボーンとそれ以降の子ボーンは除外する
    
    Parameters:
        bone_name: 親ボーンの名前
        armature_obj: アーマチュアオブジェクト
        clothing_avatar_data: 衣装のアバターデータ（Humanoidボーンの判定に使用）
        is_root: 最初に指定されたボーンかどうか
        
    Returns:
        set: 子ボーンの名前のセット
    """
    children = set()
    if bone_name not in armature_obj.data.bones:
        return children
    
    # Humanoidボーンの判定用マッピングを作成
    humanoid_bones = set()
    if clothing_avatar_data:
        for bone_map in clothing_avatar_data.get("humanoidBones", []):
            if "boneName" in bone_map:
                humanoid_bones.add(bone_map["boneName"])
    
    bone = armature_obj.data.bones[bone_name]
    for child in bone.children:
        # 最初に指定されたボーンではないHumanoidボーンの場合、そのボーンとその子ボーンを除外
        if not is_root and child.name in humanoid_bones:
            # このボーンとその子ボーンをスキップ
            continue
        
        children.add(child.name)
        children.update(get_child_bones_recursive(child.name, armature_obj, clothing_avatar_data, False))
    
    return children

# Merged from get_deformation_bones.py

def get_deformation_bones(armature_obj: bpy.types.Object, avatar_data: dict) -> list:
    """
    アバターデータを参照し、HumanoidボーンとAuxiliaryボーン以外のボーンを取得
    
    Parameters:
        armature_obj: アーマチュアオブジェクト
        avatar_data: アバターデータ
        
    Returns:
        変形対象のボーン名のリスト
    """
    # HumanoidボーンとAuxiliaryボーンのセットを作成
    excluded_bones = set()
    
    # Humanoidボーンを追加
    for bone_map in avatar_data.get("humanoidBones", []):
        if "boneName" in bone_map:
            excluded_bones.add(bone_map["boneName"])
    
    # 補助ボーンを追加
    for aux_set in avatar_data.get("auxiliaryBones", []):
        for aux_bone in aux_set.get("auxiliaryBones", []):
            excluded_bones.add(aux_bone)
    
    # 除外ボーン以外のすべてのボーンを取得
    deform_bones = []
    for bone in armature_obj.data.bones:
        if bone.name not in excluded_bones:
            deform_bones.append(bone.name)
    
    return deform_bones

# Merged from get_humanoid_bone_hierarchy.py

def get_humanoid_bone_hierarchy(avatar_data: dict) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    アバターデータからHumanoidボーンの階層関係を抽出する

    Parameters:
        avatar_data (dict): アバターデータ

    Returns:
        Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]: 
            (ボーン名から親への辞書, Humanoidボーン名からボーン名への辞書, ボーン名からHumanoidボーン名への辞書)
    """
    # ボーンの親子関係を構築
    bone_parents = {}
    build_bone_hierarchy(avatar_data['boneHierarchy'], bone_parents, [])

    # Humanoidボーン名とボーン名の対応マップを作成
    humanoid_to_bone = {bone_map['humanoidBoneName']: bone_map['boneName'] 
                       for bone_map in avatar_data['humanoidBones']}
    bone_to_humanoid = {bone_map['boneName']: bone_map['humanoidBoneName'] 
                       for bone_map in avatar_data['humanoidBones']}
    
    return bone_parents, humanoid_to_bone, bone_to_humanoid

# Merged from build_bone_maps.py

def build_bone_maps(base_avatar_data):
    """
    ヒューマノイドボーンと補助ボーンのマッピングを構築する。

    Args:
        base_avatar_data: ベースアバターのデータ（humanoidBones, auxiliaryBones を含む）

    Returns:
        tuple: (humanoid_to_bone, bone_to_humanoid, auxiliary_bones, auxiliary_bones_to_humanoid)
            - humanoid_to_bone: ヒューマノイドボーン名 -> 実際のボーン名
            - bone_to_humanoid: 実際のボーン名 -> ヒューマノイドボーン名
            - auxiliary_bones: ヒューマノイドボーン名 -> 補助ボーンリスト
            - auxiliary_bones_to_humanoid: 補助ボーン名 -> ヒューマノイドボーン名
    """
    humanoid_to_bone = {}
    bone_to_humanoid = {}
    auxiliary_bones = {}
    auxiliary_bones_to_humanoid = {}

    for bone_map in base_avatar_data.get("humanoidBones", []):
        if "humanoidBoneName" in bone_map and "boneName" in bone_map:
            humanoid_to_bone[bone_map["humanoidBoneName"]] = bone_map["boneName"]
            bone_to_humanoid[bone_map["boneName"]] = bone_map["humanoidBoneName"]

    for aux_set in base_avatar_data.get("auxiliaryBones", []):
        humanoid_bone = aux_set["humanoidBoneName"]
        auxiliary_bones[humanoid_bone] = aux_set["auxiliaryBones"]
        for aux_bone in aux_set["auxiliaryBones"]:
            auxiliary_bones_to_humanoid[aux_bone] = humanoid_bone

    return humanoid_to_bone, bone_to_humanoid, auxiliary_bones, auxiliary_bones_to_humanoid

# Merged from round_bone_coordinates.py

def round_bone_coordinates(armature: bpy.types.Object, decimal_places: int = 6) -> None:
    """
    アーマチュアのすべてのボーンのhead、tail座標およびRoll値を指定された小数点位置で四捨五入する。
    
    Args:
        armature: 対象のアーマチュアオブジェクト
        decimal_places: 四捨五入する小数点以下の桁数 (デフォルト: 6)
    """
    if not armature or armature.type != 'ARMATURE':
        print(f"[Warning] Invalid armature object for rounding bone coordinates")
        return
    
    # エディットモードに切り替え
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    
    try:
        edit_bones = armature.data.edit_bones
        rounded_count = 0
        
        for bone in edit_bones:
            # headの座標を四捨五入
            bone.head.x = round(bone.head.x, decimal_places)
            bone.head.y = round(bone.head.y, decimal_places)
            bone.head.z = round(bone.head.z, decimal_places)
            
            # tailの座標を四捨五入
            bone.tail.x = round(bone.tail.x, decimal_places)
            bone.tail.y = round(bone.tail.y, decimal_places)
            bone.tail.z = round(bone.tail.z, decimal_places)
            
            # Roll値を四捨五入
            bone.roll = round(bone.roll, decimal_places - 3)
            
            rounded_count += 1
        
    finally:
        # 元のモードに戻す
        bpy.ops.object.mode_set(mode='OBJECT')

# Merged from clear_humanoid_bone_relations_preserve_pose.py

def clear_humanoid_bone_relations_preserve_pose(armature_obj, clothing_avatar_data_filepath, base_avatar_data_filepath):
    """
    Humanoidボーンの親子関係を解除しながらワールド空間でのポーズを保持する。
    ベースアバターのアバターデータにないHumanoidボーンの親子関係は保持する。
    
    Args:
        armature_obj: bpy.types.Object - アーマチュアオブジェクト
        clothing_avatar_data_filepath: str - 衣装のアバターデータのJSONファイル名
        base_avatar_data_filepath: str - ベースアバターのアバターデータのJSONファイル名
    """
    if armature_obj.type != 'ARMATURE':
        raise ValueError("Selected object must be an armature")
    
    # アバターデータを読み込む
    clothing_avatar_data = load_avatar_data(clothing_avatar_data_filepath)
    base_avatar_data = load_avatar_data(base_avatar_data_filepath)
    
    # 衣装のHumanoidボーンのセットを作成
    clothing_humanoid_bones = {bone_map['boneName'] for bone_map in clothing_avatar_data['humanoidBones']}
    
    # ベースアバターのHumanoidボーンのセットを作成
    base_humanoid_bones = {bone_map['humanoidBoneName'] for bone_map in base_avatar_data['humanoidBones']}
    
    # 衣装のHumanoidボーン名からHumanoidボーン名への変換マップを作成
    clothing_bone_to_humanoid = {bone_map['boneName']: bone_map['humanoidBoneName'] 
                                for bone_map in clothing_avatar_data['humanoidBones']}
    
    # 親子関係を解除するボーンを特定（ベースアバターにも存在するHumanoidボーンのみ）
    bones_to_unparent = set()
    for bone_name in clothing_humanoid_bones:
        humanoid_name = clothing_bone_to_humanoid.get(bone_name)
        if humanoid_name == "UpperChest" or humanoid_name == "LeftBreast" or humanoid_name == "RightBreast" or humanoid_name == "LeftToes" or humanoid_name == "RightToes":
            continue
        bones_to_unparent.add(bone_name)
        #if humanoid_name in base_humanoid_bones:
        #    bones_to_unparent.add(bone_name)
    
    # Get the armature data
    armature = armature_obj.data
    
    # Store original world space matrices for bones to unparent
    original_matrices = {}
    for bone in armature.bones:
        if bone.name in bones_to_unparent:
            pose_bone = armature_obj.pose.bones[bone.name]
            original_matrices[bone.name] = armature_obj.matrix_world @ pose_bone.matrix
    
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    
    # Switch to edit mode to modify bone relations
    bpy.context.view_layer.objects.active = armature_obj
    original_mode = bpy.context.object.mode
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Clear parent relationships for specified bones only
    for edit_bone in armature.edit_bones:
        if edit_bone.name in bones_to_unparent:
            edit_bone.parent = None
    
    # Return to pose mode
    bpy.ops.object.mode_set(mode='POSE')
    
    # Restore original world space positions for unparented bones
    for bone_name, original_matrix in original_matrices.items():
        pose_bone = armature_obj.pose.bones[bone_name]
        pose_bone.matrix = armature_obj.matrix_world.inverted() @ original_matrix
    
    # Return to original mode
    bpy.ops.object.mode_set(mode=original_mode)

# Merged from apply_bone_name_conversion.py

def apply_bone_name_conversion(clothing_armature: bpy.types.Object, clothing_meshes: list, name_conv_data: dict) -> None:
    """
    JSONファイルで指定されたボーンの名前変更マッピングに従って、
    clothing_armatureのボーンとclothing_meshesの頂点グループの名前を変更する
    
    Parameters:
        clothing_armature: 服のアーマチュアオブジェクト
        clothing_meshes: 服のメッシュオブジェクトのリスト
        name_conv_data: ボーン名前変更マッピングのJSONデータ
    """
    if not name_conv_data or 'boneMapping' not in name_conv_data:
        return
    
    bone_mappings = name_conv_data['boneMapping']
    renamed_bones = {}
    
    # 1. アーマチュアのボーン名を変更
    if clothing_armature and clothing_armature.type == 'ARMATURE':
        # Edit modeに入ってボーン名を変更
        bpy.context.view_layer.objects.active = clothing_armature
        bpy.ops.object.mode_set(mode='EDIT')
        
        for mapping in bone_mappings:
            fbx_bone = mapping.get('fbxBone')
            prefab_bone = mapping.get('prefabBone')
            
            if not fbx_bone or not prefab_bone or fbx_bone == prefab_bone:
                continue
                
            # アーマチュア内でfbxBoneに対応するボーンを探す
            if fbx_bone in clothing_armature.data.edit_bones:
                edit_bone = clothing_armature.data.edit_bones[fbx_bone]
                edit_bone.name = prefab_bone
                renamed_bones[fbx_bone] = prefab_bone
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # 2. メッシュの頂点グループ名を変更
    for mesh_obj in clothing_meshes:
        if not mesh_obj or mesh_obj.type != 'MESH':
            continue
            
        for mapping in bone_mappings:
            fbx_bone = mapping.get('fbxBone')
            prefab_bone = mapping.get('prefabBone')
            
            if not fbx_bone or not prefab_bone or fbx_bone == prefab_bone:
                continue
                
            # 頂点グループの名前を変更
            if fbx_bone in mesh_obj.vertex_groups:
                vertex_group = mesh_obj.vertex_groups[fbx_bone]
                vertex_group.name = prefab_bone
def restore_original_bone_names(
    clothing_armature: bpy.types.Object,
    clothing_meshes: list,
    base_avatar_data: dict,
    original_bone_mapping: dict,
) -> dict:
    """
    ボーン置換後のボーン名を、最初の入力FBXの元のボーン名に復元する。
    humanoidBoneNameをキーにして、base_avatar_dataのボーン名から
    original_bone_mappingのボーン名へリネームする。
    
    Parameters:
        clothing_armature: 服のアーマチュアオブジェクト
        clothing_meshes: 服のメッシュオブジェクトのリスト
        base_avatar_data: ターゲットアバターのアバターデータ（現在のボーン名を含む）
        original_bone_mapping: 最初の入力FBXから取得した元のボーン名マッピング
            {
                'humanoidBones': {humanoidBoneName: boneName, ...},
                'auxiliaryBones': {humanoidBoneName: [aux_bone_names], ...}
            }
    
    Returns:
        dict: リネームされたボーンのマッピング {現在の名前: 元の名前}
    """
    if not original_bone_mapping:
        print("[restore_original_bone_names] No original bone mapping provided")
        return {}
    
    # original_bone_mappingから元のボーン名を取得
    original_humanoid_to_bone = original_bone_mapping.get('humanoidBones', {})
    original_aux_mapping = original_bone_mapping.get('auxiliaryBones', {})
    
    # base_avatar_dataから現在のボーン名を取得
    base_humanoid_to_bone = {
        b["humanoidBoneName"]: b["boneName"]
        for b in base_avatar_data.get("humanoidBones", [])
    }
    
    base_aux_mapping = {}  # humanoidBoneName -> [aux_bone_names]
    for aux_set in base_avatar_data.get("auxiliaryBones", []):
        humanoid_name = aux_set.get("humanoidBoneName")
        aux_bones = aux_set.get("auxiliaryBones", [])
        if humanoid_name:
            base_aux_mapping[humanoid_name] = aux_bones
    
    # リネームマッピングを構築: 現在のボーン名 -> 元のボーン名
    rename_mapping = {}
    
    # Humanoidボーンのマッピング
    for humanoid_name, original_bone in original_humanoid_to_bone.items():
        if humanoid_name in base_humanoid_to_bone:
            current_bone = base_humanoid_to_bone[humanoid_name]
            if current_bone != original_bone:
                rename_mapping[current_bone] = original_bone
    
    # Auxiliaryボーンのマッピング（インデックスベースでマッチング）
    for humanoid_name, original_aux_bones in original_aux_mapping.items():
        if humanoid_name in base_aux_mapping:
            base_aux = base_aux_mapping[humanoid_name]
            for i, original_bone in enumerate(original_aux_bones):
                if i < len(base_aux):
                    current_bone = base_aux[i]
                    if current_bone != original_bone:
                        rename_mapping[current_bone] = original_bone
    
    if not rename_mapping:
        print("[restore_original_bone_names] No bones to rename")
        return {}
    
    print(f"[restore_original_bone_names] Renaming {len(rename_mapping)} bones")
    
    # 1. アーマチュアのボーン名を変更
    renamed_bones = {}
    if clothing_armature and clothing_armature.type == 'ARMATURE':
        bpy.context.view_layer.objects.active = clothing_armature
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 名前の衝突を避けるため、一時的な名前に変更してから最終名前に変更
        temp_names = {}
        for current_name, original_name in rename_mapping.items():
            if current_name in clothing_armature.data.edit_bones:
                temp_name = f"__temp_rename_{current_name}"
                edit_bone = clothing_armature.data.edit_bones[current_name]
                edit_bone.name = temp_name
                temp_names[temp_name] = original_name
        
        # 一時名から最終名へ
        for temp_name, original_name in temp_names.items():
            if temp_name in clothing_armature.data.edit_bones:
                edit_bone = clothing_armature.data.edit_bones[temp_name]
                edit_bone.name = original_name
                renamed_bones[temp_name.replace("__temp_rename_", "")] = original_name
                print(f"  Bone renamed: {temp_name.replace('__temp_rename_', '')} -> {original_name}")
        
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # 2. メッシュの頂点グループ名を変更
    for mesh_obj in clothing_meshes:
        if not mesh_obj or mesh_obj.type != 'MESH':
            continue
        
        # 一時名に変更
        temp_groups = {}
        for current_name, original_name in rename_mapping.items():
            if current_name in mesh_obj.vertex_groups:
                temp_name = f"__temp_rename_{current_name}"
                vertex_group = mesh_obj.vertex_groups[current_name]
                vertex_group.name = temp_name
                temp_groups[temp_name] = original_name
        
        # 最終名に変更
        for temp_name, original_name in temp_groups.items():
            if temp_name in mesh_obj.vertex_groups:
                vertex_group = mesh_obj.vertex_groups[temp_name]
                vertex_group.name = original_name
    
    print(f"[restore_original_bone_names] Completed: {len(renamed_bones)} bones renamed")
    return renamed_bones


# Merged from bone_side_utils.py

def is_left_side_bone(bone_name: str, humanoid_name: str = None) -> bool:
    """
    ボーンが左側かどうかを判定
    
    Parameters:
        bone_name: ボーン名
        humanoid_name: Humanoidボーン名（オプション）
        
    Returns:
        bool: 左側のボーンの場合True
    """
    # Humanoidボーン名での判定
    if humanoid_name and any(k in humanoid_name for k in ["Left", "left"]):
        return True
        
    # 末尾の数字を削除
    cleaned_name = strip_numeric_suffix(bone_name)
        
    # ボーン名での判定
    if any(k in cleaned_name for k in ["Left", "left"]):
        return True
        
    # 末尾での判定（スペースを含む場合も考慮）
    suffixes = ["_L", ".L", " L"]
    return any(cleaned_name.endswith(suffix) for suffix in suffixes)


def is_right_side_bone(bone_name: str, humanoid_name: str = None) -> bool:
    """
    ボーンが右側かどうかを判定
    
    Parameters:
        bone_name: ボーン名
        humanoid_name: Humanoidボーン名（オプション）
        
    Returns:
        bool: 右側のボーンの場合True
    """
    # Humanoidボーン名での判定
    if humanoid_name and any(k in humanoid_name for k in ["Right", "right"]):
        return True
        
    # 末尾の数字を削除
    cleaned_name = strip_numeric_suffix(bone_name)
        
    # ボーン名での判定
    if any(k in cleaned_name for k in ["Right", "right"]):
        return True
        
    # 末尾での判定（スペースを含む場合も考慮）
    suffixes = ["_R", ".R", " R"]
    return any(cleaned_name.endswith(suffix) for suffix in suffixes)