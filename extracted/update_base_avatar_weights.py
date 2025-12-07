import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
from blender_utils.weight_processing_utils import process_missing_bone_weights


def update_base_avatar_weights(base_mesh: bpy.types.Object, clothing_armature: bpy.types.Object,
                             base_avatar_data: dict, clothing_avatar_data: dict, preserve_optional_humanoid_bones: bool) -> None:
    """
    Update base avatar weights based on clothing armature structure.
    
    Parameters:
        base_mesh: Base avatar mesh object
        clothing_armature: Clothing armature object
        base_avatar_data: Base avatar data
        clothing_avatar_data: Clothing avatar data
    """
    # Then process missing bone weights
    process_missing_bone_weights(base_mesh, clothing_armature, base_avatar_data, clothing_avatar_data, preserve_optional_humanoid_bones)
