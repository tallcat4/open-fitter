"""
シェイプキー状態の保存・復元ユーティリティ
"""

import bpy


def save_shape_key_state(mesh_obj: bpy.types.Object) -> dict:
    """
    メッシュオブジェクトのシェイプキー状態を保存する
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        
    Returns:
        保存されたシェイプキー状態のディクショナリ
    """
    if not mesh_obj or not mesh_obj.data.shape_keys:
        return {}
    
    shape_key_state = {}
    for key_block in mesh_obj.data.shape_keys.key_blocks:
        shape_key_state[key_block.name] = key_block.value
    
    return shape_key_state


def restore_shape_key_state(mesh_obj: bpy.types.Object, shape_key_state: dict) -> None:
    """
    メッシュオブジェクトのシェイプキー状態を復元する
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        shape_key_state: 復元するシェイプキー状態のディクショナリ
    """
    if not mesh_obj or not mesh_obj.data.shape_keys or not shape_key_state:
        return
    
    for key_name, value in shape_key_state.items():
        if key_name in mesh_obj.data.shape_keys.key_blocks:
            mesh_obj.data.shape_keys.key_blocks[key_name].value = value
