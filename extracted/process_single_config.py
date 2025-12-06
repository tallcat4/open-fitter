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


class SingleConfigProcessor:
    def __init__(self, args, config_pair, pair_index, total_pairs, overall_start_time):
        self.args = args
        self.config_pair = config_pair
        self.pair_index = pair_index
        self.total_pairs = total_pairs
        self.overall_start_time = overall_start_time
        self.ctx = ProcessingContext()

    @property
    def base_mesh(self):
        return self.ctx.base_mesh

    @base_mesh.setter
    def base_mesh(self, value):
        self.ctx.base_mesh = value

    @property
    def base_armature(self):
        return self.ctx.base_armature

    @base_armature.setter
    def base_armature(self, value):
        self.ctx.base_armature = value

    @property
    def base_avatar_data(self):
        return self.ctx.base_avatar_data

    @base_avatar_data.setter
    def base_avatar_data(self, value):
        self.ctx.base_avatar_data = value

    @property
    def clothing_meshes(self):
        return self.ctx.clothing_meshes

    @clothing_meshes.setter
    def clothing_meshes(self, value):
        self.ctx.clothing_meshes = value

    @property
    def clothing_armature(self):
        return self.ctx.clothing_armature

    @clothing_armature.setter
    def clothing_armature(self, value):
        self.ctx.clothing_armature = value

    @property
    def clothing_avatar_data(self):
        return self.ctx.clothing_avatar_data

    @clothing_avatar_data.setter
    def clothing_avatar_data(self, value):
        self.ctx.clothing_avatar_data = value

    @property
    def cloth_metadata(self):
        return self.ctx.cloth_metadata

    @cloth_metadata.setter
    def cloth_metadata(self, value):
        self.ctx.cloth_metadata = value

    @property
    def vertex_index_mapping(self):
        return self.ctx.vertex_index_mapping

    @vertex_index_mapping.setter
    def vertex_index_mapping(self, value):
        self.ctx.vertex_index_mapping = value

    @property
    def use_subdivision(self):
        return self.ctx.use_subdivision

    @use_subdivision.setter
    def use_subdivision(self, value):
        self.ctx.use_subdivision = value

    @property
    def use_triangulation(self):
        return self.ctx.use_triangulation

    @use_triangulation.setter
    def use_triangulation(self, value):
        self.ctx.use_triangulation = value

    @property
    def propagated_groups_map(self):
        return self.ctx.propagated_groups_map

    @propagated_groups_map.setter
    def propagated_groups_map(self, value):
        self.ctx.propagated_groups_map = value

    @property
    def original_humanoid_bones(self):
        return self.ctx.original_humanoid_bones

    @original_humanoid_bones.setter
    def original_humanoid_bones(self, value):
        self.ctx.original_humanoid_bones = value

    @property
    def original_auxiliary_bones(self):
        return self.ctx.original_auxiliary_bones

    @original_auxiliary_bones.setter
    def original_auxiliary_bones(self, value):
        self.ctx.original_auxiliary_bones = value

    @property
    def is_A_pose(self):
        return self.ctx.is_A_pose

    @is_A_pose.setter
    def is_A_pose(self, value):
        self.ctx.is_A_pose = value

    @property
    def blend_shape_labels(self):
        return self.ctx.blend_shape_labels

    @blend_shape_labels.setter
    def blend_shape_labels(self, value):
        self.ctx.blend_shape_labels = value

    @property
    def base_weights_time(self):
        return self.ctx.base_weights_time

    @base_weights_time.setter
    def base_weights_time(self, value):
        self.ctx.base_weights_time = value

    @property
    def cycle1_end_time(self):
        return self.ctx.cycle1_end_time

    @cycle1_end_time.setter
    def cycle1_end_time(self, value):
        self.ctx.cycle1_end_time = value

    @property
    def cycle2_post_end(self):
        return self.ctx.cycle2_post_end

    @cycle2_post_end.setter
    def cycle2_post_end(self, value):
        self.ctx.cycle2_post_end = value

    @property
    def time_module(self):
        return self.ctx.time_module

    @time_module.setter
    def time_module(self, value):
        self.ctx.time_module = value

    @property
    def start_time(self):
        return self.ctx.start_time

    @start_time.setter
    def start_time(self, value):
        self.ctx.start_time = value

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

            self._load_and_prepare_assets()  # ベース・衣装データの読み込みと初期準備
            if not self._apply_template_specific_adjustments():  # Template専用の調整処理
                return None
            self._execute_mesh_preparation_cycle()  # サイクル1: メッシュ前処理と形状調整
            self._perform_weight_transfer_cycle()  # サイクル2: ウェイト転送と後処理
            self._finalize_scene_and_export()  # 最終仕上げとFBXエクスポート

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

    def _load_and_prepare_assets(self):
        AssetPreparationStage(self).run()

    def _apply_template_specific_adjustments(self):
        return TemplateAdjustmentStage(self).run()

    def _execute_mesh_preparation_cycle(self):
        MeshPreparationStage(self).run()

    def _perform_weight_transfer_cycle(self):
        WeightTransferStage(self).run()

    def _finalize_scene_and_export(self):
        SceneFinalizationStage(self).run()


def process_single_config(args, config_pair, pair_index, total_pairs, overall_start_time):
    processor = SingleConfigProcessor(args, config_pair, pair_index, total_pairs, overall_start_time)
    return processor.execute()