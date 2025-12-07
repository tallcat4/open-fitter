"""WeightTransferPostProcessStage: ウェイト転送後の後処理を担当するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from blender_utils.armature_modifier_utils import (
    set_armature_modifier_target_armature,
    set_armature_modifier_visibility,
)


class WeightTransferPostProcessStage:
    """ウェイト転送後の後処理を担当するステージ
    
    責務:
        - アーマチュアモディファイアの可視性復元
        - アーマチュアターゲットの復元（衣装アーマチュアに戻す）
    
    前提:
        - WeightTransferExecutionStage が完了していること
    
    成果物:
        - cycle2_post_end タイムスタンプ
        - アーマチュア設定が復元された衣装メッシュ
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module

        print("Status: サイクル2後処理中")
        print(f"Progress: {(p.pair_index + 0.65) / p.total_pairs * 0.9:.3f}")

        cycle2_post_start = time.time()

        for obj in p.clothing_meshes:
            obj_start = time.time()
            print("cycle2 (post-weight transfer) " + obj.name)

            # アーマチュアモディファイアの可視性を復元
            set_armature_modifier_visibility(obj, True, True)

            # アーマチュアターゲットを衣装アーマチュアに戻す
            set_armature_modifier_target_armature(obj, p.clothing_armature)

            print(f"  {obj.name}の後処理: {time.time() - obj_start:.2f}秒")

        cycle2_post_end = time.time()
        p.cycle2_post_end = cycle2_post_end
        print(f"サイクル2後処理全体: {cycle2_post_end - cycle2_post_start:.2f}秒")
