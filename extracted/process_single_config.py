import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import bpy
from processing_context import ProcessingContext
from stages.asset_preparation import AssetPreparationStage
from stages.mesh_preparation import MeshPreparationStage
from stages.scene_finalization import SceneFinalizationStage
from stages.template_adjustment import TemplateAdjustmentStage
from stages.weight_transfer import WeightTransferStage


class OutfitRetargetPipeline:
    """衣装リターゲティングパイプライン (OutfitRetargetingSystem のコア処理)
    
    ベースアバターから衣装メッシュへウェイト・形状・ポーズを転送し、
    最終的なFBXファイルを出力する。
    
    Stages:
        1. AssetPreparation: アセット読み込み・初期化
        2. TemplateAdjustment: Template固有補正（条件付き）
        3. MeshPreparation: メッシュ変形・サイクル1
        4. WeightTransfer: ウェイト転送・サイクル2
        5. SceneFinalization: 仕上げ・FBXエクスポート
    """
    
    # ProcessingContextに委譲する属性のリスト
    _CTX_ATTRS = frozenset({
        'base_mesh', 'base_armature', 'base_avatar_data',
        'clothing_meshes', 'clothing_armature', 'clothing_avatar_data',
        'cloth_metadata', 'vertex_index_mapping',
        'use_subdivision', 'use_triangulation', 'propagated_groups_map',
        'original_humanoid_bones', 'original_auxiliary_bones',
        'is_A_pose', 'blend_shape_labels',
        'base_weights_time', 'cycle1_end_time', 'cycle2_post_end',
        'time_module', 'start_time'
    })

    def __init__(self, args, config_pair, pair_index, total_pairs, overall_start_time):
        object.__setattr__(self, 'args', args)
        object.__setattr__(self, 'config_pair', config_pair)
        object.__setattr__(self, 'pair_index', pair_index)
        object.__setattr__(self, 'total_pairs', total_pairs)
        object.__setattr__(self, 'overall_start_time', overall_start_time)
        object.__setattr__(self, 'ctx', ProcessingContext())

    def __getattr__(self, name):
        if name in OutfitRetargetPipeline._CTX_ATTRS:
            return getattr(self.ctx, name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __setattr__(self, name, value):
        if name in OutfitRetargetPipeline._CTX_ATTRS:
            setattr(self.ctx, name, value)
        else:
            object.__setattr__(self, name, value)

    def execute(self):
        try:
            import time

            self.time_module = time
            self.start_time = time.time()

            self.use_subdivision = not self.args.no_subdivision
            if self.pair_index != 0:
                self.use_subdivision = False

            self.use_triangulation = not self.args.no_triangle

            bpy.ops.object.mode_set(mode='OBJECT')

            # ベース・衣装データの読み込みと初期準備
            AssetPreparationStage(self).run()
            # Template専用の調整処理
            if not TemplateAdjustmentStage(self).run():
                return None
            # サイクル1: メッシュ前処理と形状調整
            MeshPreparationStage(self).run()
            # サイクル2: ウェイト転送と後処理
            WeightTransferStage(self).run()
            # 最終仕上げとFBXエクスポート
            SceneFinalizationStage(self).run()

            total_time = time.time() - self.start_time
            print(f"Progress: {(self.pair_index + 1.0) / self.total_pairs * 0.9:.3f}")
            print(f"処理完了: 合計 {total_time:.2f}秒")
            return True

        except Exception as e:
            import traceback

            print("============= Error Details =============")
            print(f"Error message: {str(e)}")
            print("\n============= Full Stack Trace =============")
            print(traceback.format_exc())
            print("==========================================")

            output_blend = self.args.output.rsplit('.', 1)[0] + '.blend'
            bpy.ops.wm.save_as_mainfile(filepath=output_blend)

            return False


# 後方互換性のためのエイリアス
SingleConfigProcessor = OutfitRetargetPipeline
ClothingRetargetPipeline = OutfitRetargetPipeline


def process_single_config(args, config_pair, pair_index, total_pairs, overall_start_time):
    """後方互換性のためのラッパー関数。OutfitRetargetPipelineを直接使用することを推奨。"""
    pipeline = OutfitRetargetPipeline(args, config_pair, pair_index, total_pairs, overall_start_time)
    return pipeline.execute()