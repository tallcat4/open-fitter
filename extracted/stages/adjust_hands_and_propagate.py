import os
import sys

# Add the parent directory (extracted/) to sys.path to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from blender_utils.weight_processing_utils import adjust_hand_weights
from blender_utils.weight_processing_utils import (
    propagate_weights_to_side_vertices,
)


def adjust_hands_and_propagate(context):
    hand_weights_time_start = time.time()
    adjust_hand_weights(context.target_obj, context.armature, context.base_avatar_data)
    hand_weights_time = time.time() - hand_weights_time_start
    print(f"  手のウェイト調整: {hand_weights_time:.2f}秒")

    propagate_time_start = time.time()
    # Inline the wrapper logic here
    propagate_weights_to_side_vertices(
        target_obj=context.target_obj,
        bone_groups=context.bone_groups,
        original_humanoid_weights=context.original_humanoid_weights,
        clothing_armature=context.clothing_armature,
        max_iterations=100,
    )
    propagate_time = time.time() - propagate_time_start
    print(f"  側面頂点へのウェイト伝播: {propagate_time:.2f}秒")
