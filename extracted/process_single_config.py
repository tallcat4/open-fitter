import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import bpy
from processing_context import ProcessingContext
from add_clothing_pose_from_json import add_clothing_pose_from_json
from add_pose_from_json import add_pose_from_json
from algo_utils.create_hinge_bone_group import create_hinge_bone_group
from algo_utils.remove_empty_vertex_groups import remove_empty_vertex_groups
from apply_blendshape_deformation_fields import apply_blendshape_deformation_fields
from blender_utils.apply_bone_name_conversion import apply_bone_name_conversion
from blender_utils.create_deformation_mask import create_deformation_mask
from blender_utils.create_overlapping_vertices_attributes import (
    create_overlapping_vertices_attributes,
)
from blender_utils.merge_auxiliary_to_humanoid_weights import (
    merge_auxiliary_to_humanoid_weights,
)
from blender_utils.process_bone_weight_consolidation import (
    process_bone_weight_consolidation,
)
from blender_utils.process_clothing_avatar import process_clothing_avatar
from blender_utils.propagate_bone_weights import propagate_bone_weights
from blender_utils.reset_shape_keys import reset_shape_keys
from blender_utils.setup_weight_transfer import setup_weight_transfer
from blender_utils.subdivide_breast_faces import subdivide_breast_faces
from blender_utils.subdivide_long_edges import subdivide_long_edges
from blender_utils.triangulate_mesh import triangulate_mesh
from common_utils.rename_shape_keys_from_mappings import rename_shape_keys_from_mappings
from common_utils.truncate_long_shape_key_names import truncate_long_shape_key_names
from io_utils.import_base_fbx import import_base_fbx
from io_utils.load_base_file import load_base_file
from io_utils.load_cloth_metadata import load_cloth_metadata
from io_utils.load_mesh_material_data import load_mesh_material_data
from is_A_pose import is_A_pose
from math_utils.normalize_bone_weights import normalize_bone_weights
from math_utils.normalize_clothing_bone_names import normalize_clothing_bone_names
from math_utils.normalize_vertex_weights import normalize_vertex_weights
from process_base_avatar import process_base_avatar
from process_mesh_with_connected_components_inline import (
    process_mesh_with_connected_components_inline,
)
from update_base_avatar_weights import update_base_avatar_weights
from stages.asset_preparation import AssetPreparationStage
from stages.template_adjustment import TemplateAdjustmentStage
from stages.mesh_preparation import MeshPreparationStage
from stages.weight_transfer import WeightTransferStage
from stages.scene_finalization import SceneFinalizationStage

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