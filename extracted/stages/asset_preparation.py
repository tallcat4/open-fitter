import json
import os

from add_pose_from_json import add_pose_from_json
from algo_utils.remove_empty_vertex_groups import remove_empty_vertex_groups
from blender_utils.apply_bone_name_conversion import apply_bone_name_conversion
from blender_utils.process_clothing_avatar import process_clothing_avatar
from blender_utils.setup_weight_transfer import setup_weight_transfer
from common_utils.rename_shape_keys_from_mappings import rename_shape_keys_from_mappings
from common_utils.truncate_long_shape_key_names import truncate_long_shape_key_names
from io_utils.load_base_file import load_base_file
from io_utils.load_cloth_metadata import load_cloth_metadata
from io_utils.load_mesh_material_data import load_mesh_material_data
from is_A_pose import is_A_pose
from math_utils.normalize_bone_weights import normalize_bone_weights
from math_utils.normalize_clothing_bone_names import normalize_clothing_bone_names
from process_base_avatar import process_base_avatar
from update_base_avatar_weights import update_base_avatar_weights


class AssetPreparationStage:
    """Handles base/clothing loading and initial weight normalization."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            time = self.time_module

            print("Status: ベースファイル読み込み中")
            print(
                f"Progress: {(self.pair_index + 0.05) / self.total_pairs * 0.9:.3f}"
            )
            load_base_file(self.args.base)
            base_load_time = time.time()
            print(f"ベースファイル読み込み: {base_load_time - self.start_time:.2f}秒")

            print("Status: ベースアバター処理中")
            print(
                f"Progress: {(self.pair_index + 0.1) / self.total_pairs * 0.9:.3f}"
            )
            (
                self.base_mesh,
                self.base_armature,
                self.base_avatar_data,
            ) = process_base_avatar(
                self.config_pair['base_fbx'],
                self.config_pair['base_avatar_data'],
            )

            print("Status: 衣装データ処理中")
            print(
                f"Progress: {(self.pair_index + 0.15) / self.total_pairs * 0.9:.3f}"
            )
            (
                self.clothing_meshes,
                self.clothing_armature,
                self.clothing_avatar_data,
            ) = process_clothing_avatar(
                self.config_pair['input_clothing_fbx_path'],
                self.config_pair['clothing_avatar_data'],
                self.config_pair['hips_position'],
                self.config_pair['target_meshes'],
                self.config_pair['mesh_renderers'],
            )

            if self.config_pair.get('blend_shape_mappings'):
                rename_shape_keys_from_mappings(
                    self.clothing_meshes, self.config_pair['blend_shape_mappings']
                )

            truncate_long_shape_key_names(
                self.clothing_meshes, self.clothing_avatar_data
            )

            clothing_process_time = time.time()
            print(f"衣装データ処理: {clothing_process_time - base_load_time:.2f}秒")

            if self.pair_index == 0:
                self.is_A_pose = is_A_pose(
                    self.clothing_avatar_data,
                    self.clothing_armature,
                    init_pose_filepath=self.config_pair['init_pose'],
                    pose_filepath=self.config_pair['pose_data'],
                    clothing_avatar_data_filepath=self.config_pair[
                        'clothing_avatar_data'
                    ],
                )
                print(f"is_A_pose: {self.is_A_pose}")
            if (
                self.is_A_pose
                and self.base_avatar_data
                and self.base_avatar_data.get('basePoseA', None)
            ):
                print("AポーズのためAポーズ用ベースポーズを使用")
                self.base_avatar_data['basePose'] = self.base_avatar_data['basePoseA']

            base_pose_filepath = self.base_avatar_data.get('basePose', None)
            if (
                base_pose_filepath
                and self.config_pair.get('do_not_use_base_pose', 0) == 0
            ):
                pose_dir = os.path.dirname(
                    os.path.abspath(self.config_pair['base_avatar_data'])
                )
                base_pose_filepath = os.path.join(pose_dir, base_pose_filepath)
                print(f"Applying target avatar base pose from {base_pose_filepath}")
                add_pose_from_json(
                    self.base_armature,
                    base_pose_filepath,
                    self.base_avatar_data,
                    invert=False,
                )
            base_process_time = time.time()
            print(
                f"ベースアバター処理: {base_process_time - clothing_process_time:.2f}秒"
            )

            print("Status: クロスメタデータ読み込み中")
            print(
                f"Progress: {(self.pair_index + 0.2) / self.total_pairs * 0.9:.3f}"
            )
            (
                self.cloth_metadata,
                self.vertex_index_mapping,
            ) = load_cloth_metadata(self.args.cloth_metadata)
            metadata_load_time = time.time()
            print(
                f"クロスメタデータ読み込み: {metadata_load_time - base_process_time:.2f}秒"
            )

            if self.pair_index == 0:
                print("Status: メッシュマテリアルデータ読み込み中")
                print(
                    f"Progress: {(self.pair_index + 0.22) / self.total_pairs * 0.9:.3f}"
                )
                load_mesh_material_data(self.args.mesh_material_data)
                material_load_time = time.time()
                print(
                    f"メッシュマテリアルデータ読み込み: {material_load_time - metadata_load_time:.2f}秒"
                )
            else:
                material_load_time = metadata_load_time

            print("Status: ウェイト転送セットアップ中")
            print(
                f"Progress: {(self.pair_index + 0.25) / self.total_pairs * 0.9:.3f}"
            )
            setup_weight_transfer()
            setup_time = time.time()
            print(
                f"ウェイト転送セットアップ: {setup_time - metadata_load_time:.2f}秒"
            )

            print("Status: ベースアバターウェイト更新中")
            print(
                f"Progress: {(self.pair_index + 0.3) / self.total_pairs * 0.9:.3f}"
            )
            remove_empty_vertex_groups(self.base_mesh)

            if (
                self.pair_index == 0
                and hasattr(self.args, 'name_conv')
                and self.args.name_conv
            ):
                try:
                    with open(self.args.name_conv, 'r', encoding='utf-8') as f:
                        name_conv_data = json.load(f)
                    apply_bone_name_conversion(
                        self.clothing_armature, self.clothing_meshes, name_conv_data
                    )
                    print(f"ボーン名前変更処理完了: {self.args.name_conv}")
                except Exception as e:
                    print(
                        f"Warning: ボーン名前変更処理でエラーが発生しました: {e}"
                    )

            normalize_clothing_bone_names(
                self.clothing_armature,
                self.clothing_avatar_data,
                self.clothing_meshes,
            )
            update_base_avatar_weights(
                self.base_mesh,
                self.clothing_armature,
                self.base_avatar_data,
                self.clothing_avatar_data,
                preserve_optional_humanoid_bones=True,
            )
            normalize_bone_weights(self.base_mesh, self.base_avatar_data)
            self.base_weights_time = time.time()
            print(
                f"ベースアバターウェイト更新: {self.base_weights_time - setup_time:.2f}秒"
            )

        _run(self.processor)
