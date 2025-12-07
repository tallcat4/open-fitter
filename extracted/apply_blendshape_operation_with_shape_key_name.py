import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apply_blendshape_operation import apply_blendshape_operation
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state


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
