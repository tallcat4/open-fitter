"""BlendShapeApplicationStage: BlendShape変形フィールドの適用を担当するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from algo_utils.vertex_group_utils import remove_empty_vertex_groups
from apply_blendshape_deformation_fields import apply_blendshape_deformation_fields
from blender_utils.reset_utils import reset_shape_keys
from math_utils.weight_utils import normalize_vertex_weights


class BlendShapeApplicationStage:
    """BlendShape変形フィールドを衣装メッシュに適用するステージ
    
    責務:
        - BlendShapeラベルの解析
        - 各衣装メッシュへのDeformation Field適用
    
    前提:
        - AssetNormalizationStage が完了していること
    
    成果物:
        - blend_shape_labels リスト
        - BlendShape変形が適用された衣装メッシュ
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module

        print("Status: BlendShape用 Deformation Field適用中")
        print(f"Progress: {(p.pair_index + 0.33) / p.total_pairs * 0.9:.3f}")

        # BlendShapeラベルの解析
        p.blend_shape_labels = (
            p.config_pair['blend_shapes'].split(',')
            if p.config_pair['blend_shapes']
            else None
        )

        # BlendShapeラベルがある場合、各メッシュに変形フィールドを適用
        if p.blend_shape_labels:
            for obj in p.clothing_meshes:
                reset_shape_keys(obj)
                remove_empty_vertex_groups(obj)
                normalize_vertex_weights(obj)
                apply_blendshape_deformation_fields(
                    obj,
                    p.config_pair['field_data'],
                    p.blend_shape_labels,
                    p.clothing_avatar_data,
                    p.config_pair['blend_shape_values'],
                )

        blendshape_time = time.time()
        print(f"BlendShape用 Deformation Field適用: {blendshape_time - p.base_weights_time:.2f}秒")

        # 次のステージで使用するためのタイムスタンプを保存
        p.blendshape_time = blendshape_time
