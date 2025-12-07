"""MeshDeformationStage: メッシュ変形処理（サイクル1）を担当するステージ"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from algo_utils.vertex_group_utils import remove_empty_vertex_groups
from blender_utils.create_deformation_mask import create_deformation_mask
from blender_utils.merge_auxiliary_to_humanoid_weights import (
    merge_auxiliary_to_humanoid_weights,
)
from blender_utils.process_bone_weight_consolidation import (
    process_bone_weight_consolidation,
)
from blender_utils.propagate_bone_weights import propagate_bone_weights
from blender_utils.reset_utils import reset_shape_keys
from blender_utils.subdivision_utils import subdivide_breast_faces
from blender_utils.subdivision_utils import subdivide_long_edges
from blender_utils.triangulate_mesh import triangulate_mesh
from io_utils.vertex_weights_io import restore_vertex_weights, save_vertex_weights
from math_utils.weight_utils import normalize_vertex_weights
from process_mesh_with_connected_components_inline import (
    process_mesh_with_connected_components_inline,
)


class MeshDeformationStage:
    """メッシュ変形処理（サイクル1）を担当するステージ
    
    責務:
        - ウェイト正規化・統合
        - 微小ウェイト除外
        - サブディビジョン・三角形化
        - 連結成分ベースのメッシュ処理
        - シェイプキーのマージ
    
    前提:
        - PoseApplicationStage が完了していること
    
    成果物:
        - propagated_groups_map
        - cycle1_end_time タイムスタンプ
        - 変形処理が完了した衣装メッシュ
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module

        print("Status: メッシュ変形処理中")
        print(f"Progress: {(p.pair_index + 0.45) / p.total_pairs * 0.9:.3f}")

        p.propagated_groups_map = {}
        cycle1_start = time.time()

        for obj in p.clothing_meshes:
            self._process_single_mesh(obj, p, time)

        cycle1_end = time.time()
        p.cycle1_end_time = cycle1_end
        print(f"サイクル1全体: {cycle1_end - cycle1_start:.2f}秒")

        # シェイプキーのデバッグ出力
        self._print_shape_key_summary(p)

    def _process_single_mesh(self, obj, p, time):
        """単一メッシュの変形処理"""
        obj_start = time.time()
        print("cycle1 " + obj.name)

        # ウェイト初期化
        reset_shape_keys(obj)
        remove_empty_vertex_groups(obj)
        normalize_vertex_weights(obj)
        merge_auxiliary_to_humanoid_weights(obj, p.clothing_avatar_data)

        # ボーンウェイト伝播
        temp_group_name = propagate_bone_weights(obj)
        if temp_group_name:
            p.propagated_groups_map[obj.name] = temp_group_name

        # 微小ウェイト除外
        self._cleanup_small_weights(obj, time)

        # 変形マスク作成
        create_deformation_mask(obj, p.clothing_avatar_data)

        # サブディビジョン（条件付き）
        if (
            p.pair_index == 0
            and p.use_subdivision
            and obj.name not in p.cloth_metadata
        ):
            subdivide_long_edges(obj)
            subdivide_breast_faces(obj, p.clothing_avatar_data)

        # 三角形化（条件付き）
        if (
            p.use_triangulation
            and not p.use_subdivision
            and obj.name not in p.cloth_metadata
            and p.pair_index == p.total_pairs - 1
        ):
            triangulate_mesh(obj)

        # ウェイト保存・統合・連結成分処理・復元
        original_weights = save_vertex_weights(obj)

        process_bone_weight_consolidation(obj, p.clothing_avatar_data)

        process_mesh_with_connected_components_inline(
            obj,
            p.config_pair['field_data'],
            p.blend_shape_labels,
            p.clothing_avatar_data,
            p.base_avatar_data,
            p.clothing_armature,
            p.cloth_metadata,
            subdivision=p.use_subdivision,
            skip_blend_shape_generation=p.config_pair['skip_blend_shape_generation'],
            config_data=p.config_pair['config_data'],
        )

        restore_vertex_weights(obj, original_weights)

        # 生成されたシェイプキーのマージ
        self._merge_generated_shape_keys(obj)

        print(f"  {obj.name}の処理: {time.time() - obj_start:.2f}秒")

    def _cleanup_small_weights(self, obj, time):
        """微小ウェイト（0.0005未満）を除外"""
        cleanup_weights_time_start = time.time()
        for vert in obj.data.vertices:
            groups_to_remove = []
            for g in vert.groups:
                if g.weight < 0.0005:
                    groups_to_remove.append(g.group)
            for group_idx in groups_to_remove:
                try:
                    obj.vertex_groups[group_idx].remove([vert.index])
                except RuntimeError:
                    continue
        cleanup_weights_time = time.time() - cleanup_weights_time_start
        print(f"  微小ウェイト除外: {cleanup_weights_time:.2f}秒")

    def _merge_generated_shape_keys(self, obj):
        """_generated サフィックスのシェイプキーを元のキーにマージ"""
        if not obj.data.shape_keys:
            return

        generated_shape_keys = []
        for shape_key in obj.data.shape_keys.key_blocks:
            if shape_key.name.endswith("_generated"):
                generated_shape_keys.append(shape_key.name)

        for generated_name in generated_shape_keys:
            base_name = generated_name[:-10]  # "_generated" を除去
            generated_key = obj.data.shape_keys.key_blocks.get(generated_name)
            base_key = obj.data.shape_keys.key_blocks.get(base_name)

            if generated_key and base_key:
                for i, point in enumerate(generated_key.data):
                    base_key.data[i].co = point.co
                print(f"Merged {generated_name} into {base_name} for {obj.name}")
                obj.shape_key_remove(generated_key)
                print(f"Removed generated shape key: {generated_name} from {obj.name}")

    def _print_shape_key_summary(self, p):
        """シェイプキーのサマリーを出力"""
        for obj in p.clothing_meshes:
            if obj.data.shape_keys:
                for key_block in obj.data.shape_keys.key_blocks:
                    print(
                        f"Shape key: {key_block.name} / {key_block.value} found on {obj.name}"
                    )
