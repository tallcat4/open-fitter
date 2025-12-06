import os
import sys
import json
import bpy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
_GRANDPARENT_DIR = os.path.dirname(_PARENT_DIR)
for _p in (_PARENT_DIR, _GRANDPARENT_DIR):
    if _p not in sys.path:
        sys.path.append(_p)

from blender_utils.apply_all_transforms import apply_all_transforms
from blender_utils.apply_bone_field_delta import apply_bone_field_delta
from blender_utils.apply_pose_as_rest import apply_pose_as_rest
from blender_utils.merge_and_clean_generated_shapekeys import (
    merge_and_clean_generated_shapekeys,
)
from blender_utils.remove_propagated_weights import remove_propagated_weights
from blender_utils.round_bone_coordinates import round_bone_coordinates
from blender_utils.set_highheel_shapekey_values import set_highheel_shapekey_values
from io_utils.export_fbx import export_fbx
from misc_utils.update_cloth_metadata import update_cloth_metadata
from replace_humanoid_bones import replace_humanoid_bones


class SceneFinalizationStage:
    """Executes the final scene prep and FBX export."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            time = self.time_module

            print("Status: ポーズ適用中")
            print(
                f"Progress: {(self.pair_index + 0.7) / self.total_pairs * 0.9:.3f}"
            )
            apply_pose_as_rest(self.clothing_armature)
            pose_rest_time = time.time()
            print(
                f"ポーズをレストポーズとして適用: {pose_rest_time - self.cycle2_post_end:.2f}秒"
            )

            print("Status: ボーンフィールドデルタ適用中")
            print(
                f"Progress: {(self.pair_index + 0.75) / self.total_pairs * 0.9:.3f}"
            )
            apply_bone_field_delta(
                self.clothing_armature,
                self.config_pair['field_data'],
                self.clothing_avatar_data,
            )
            bone_delta_time = time.time()
            print(f"ボーンフィールドデルタ適用: {bone_delta_time - pose_rest_time:.2f}秒")

            print("Status: ポーズ適用中")
            print(
                f"Progress: {(self.pair_index + 0.85) / self.total_pairs * 0.9:.3f}"
            )
            apply_pose_as_rest(self.clothing_armature)
            second_pose_rest_time = time.time()
            print(
                f"2回目のポーズをレストポーズとして適用: {second_pose_rest_time - bone_delta_time:.2f}秒"
            )

            print("Status: すべての変換を適用中")
            print(
                f"Progress: {(self.pair_index + 0.9) / self.total_pairs * 0.9:.3f}"
            )
            apply_all_transforms()
            transforms_time = time.time()
            print(f"すべての変換を適用: {transforms_time - second_pose_rest_time:.2f}秒")

            print("Status: 伝播ウェイト削除中")
            print(
                f"Progress: {(self.pair_index + 0.95) / self.total_pairs * 0.9:.3f}"
            )
            propagated_start = time.time()
            for obj in self.clothing_meshes:
                if obj.name in self.propagated_groups_map:
                    remove_propagated_weights(
                        obj, self.propagated_groups_map[obj.name]
                    )
            propagated_end = time.time()
            print(f"伝播ウェイト削除: {propagated_end - propagated_start:.2f}秒")

            if (
                self.original_humanoid_bones is not None
                or self.original_auxiliary_bones is not None
            ):
                print("元のhumanoidBonesとauxiliaryBonesを復元中...")
                if self.original_humanoid_bones is not None:
                    self.base_avatar_data['humanoidBones'] = (
                        self.original_humanoid_bones
                    )
                if self.original_auxiliary_bones is not None:
                    self.base_avatar_data['auxiliaryBones'] = (
                        self.original_auxiliary_bones
                    )
                print("元のボーンデータの復元完了")

            print("Status: ヒューマノイドボーン置換中")
            print(
                f"Progress: {(self.pair_index + 0.95) / self.total_pairs * 0.9:.3f}"
            )
            base_pose_filepath = None
            if self.config_pair.get('do_not_use_base_pose', 0) == 0:
                base_pose_filepath = self.base_avatar_data.get('basePose', None)
                if base_pose_filepath:
                    pose_dir = os.path.dirname(
                        os.path.abspath(self.config_pair['base_avatar_data'])
                    )
                    base_pose_filepath = os.path.join(pose_dir, base_pose_filepath)
            if self.pair_index == 0:
                replace_humanoid_bones(
                    self.base_armature,
                    self.clothing_armature,
                    self.base_avatar_data,
                    self.clothing_avatar_data,
                    True,
                    base_pose_filepath,
                    self.clothing_meshes,
                    False,
                )
            else:
                replace_humanoid_bones(
                    self.base_armature,
                    self.clothing_armature,
                    self.base_avatar_data,
                    self.clothing_avatar_data,
                    False,
                    base_pose_filepath,
                    self.clothing_meshes,
                    True,
                )
            bones_replace_time = time.time()
            print(f"ヒューマノイドボーン置換: {bones_replace_time - propagated_end:.2f}秒")

            print("Status: ブレンドシェイプ設定中")
            print(
                f"Progress: {(self.pair_index + 0.96) / self.total_pairs * 0.9:.3f}"
            )
            blendshape_start = time.time()
            if "clothingBlendShapeSettings" in self.config_pair['config_data']:
                blend_shape_settings = self.config_pair['config_data'][
                    "clothingBlendShapeSettings"
                ]

                for setting in blend_shape_settings:
                    label = setting.get("label")
                    if label in self.blend_shape_labels:
                        blendshapes = setting.get("blendshapes", [])
                        for bs in blendshapes:
                            shape_key_name = bs.get("name")
                            value = bs.get("value", 0)
                            for obj in self.clothing_meshes:
                                if (
                                    obj.data.shape_keys
                                    and shape_key_name in obj.data.shape_keys.key_blocks
                                ):
                                    obj.data.shape_keys.key_blocks[
                                        shape_key_name
                                    ].value = value / 100.0
                                    print(
                                        f"Set blendshape '{shape_key_name}' on {obj.name} to {value/100.0}"
                                    )
            blendshape_end = time.time()
            print(f"ブレンドシェイプ設定: {blendshape_end - blendshape_start:.2f}秒")

            print("Status: クロスメタデータ更新中")
            print(
                f"Progress: {(self.pair_index + 0.97) / self.total_pairs * 0.9:.3f}"
            )
            metadata_update_start = time.time()
            if self.args.cloth_metadata and os.path.exists(self.args.cloth_metadata):
                try:
                    with open(self.args.cloth_metadata, 'r', encoding='utf-8') as f:
                        metadata_dict = json.load(f)
                    update_cloth_metadata(
                        metadata_dict,
                        self.args.cloth_metadata,
                        self.vertex_index_mapping,
                    )

                except Exception as e:
                    print(f"Error processing cloth metadata: {e}")
                    import traceback

                    traceback.print_exc()
            metadata_update_end = time.time()
            print(
                f"クロスメタデータ更新: {metadata_update_end - metadata_update_start:.2f}秒"
            )

            print("Status: FBXエクスポート前処理中")
            print(
                f"Progress: {(self.pair_index + 0.975) / self.total_pairs * 0.9:.3f}"
            )
            preprocess_start = time.time()

            self.blend_shape_labels = []
            if self.args.blend_shapes:
                self.blend_shape_labels = [
                    label for label in self.args.blend_shapes.split(',')
                ]

            for obj in self.clothing_meshes:
                if obj.data.shape_keys:
                    for key_block in obj.data.shape_keys.key_blocks:
                        print(
                            f"Shape key: {key_block.name} / {key_block.value} found on {obj.name}"
                        )

            merge_and_clean_generated_shapekeys(
                self.clothing_meshes, self.blend_shape_labels
            )
            if self.clothing_avatar_data.get("name", None) == "Template":
                import re

                pattern = re.compile(r'___\d+$')
                for obj in self.clothing_meshes:
                    if obj.data.shape_keys:
                        keys_to_remove = []
                        for key_block in obj.data.shape_keys.key_blocks:
                            if pattern.search(key_block.name):
                                keys_to_remove.append(key_block.name)
                        for key_name in keys_to_remove:
                            key_block = obj.data.shape_keys.key_blocks.get(key_name)
                            if key_block:
                                obj.shape_key_remove(key_block)
                                print(f"Removed shape key: {key_name} from {obj.name}")

            if self.pair_index > 0:
                bpy.ops.object.mode_set(mode='OBJECT')
                clothing_blend_shape_labels = []
                for blend_shape_field in self.clothing_avatar_data[
                    'blendShapeFields'
                ]:
                    clothing_blend_shape_labels.append(blend_shape_field['label'])
                base_blend_shape_labels = []
                for blend_shape_field in self.base_avatar_data['blendShapeFields']:
                    base_blend_shape_labels.append(blend_shape_field['label'])
                for obj in self.clothing_meshes:
                    if obj.data.shape_keys:
                        for key_block in obj.data.shape_keys.key_blocks:
                            if (
                                key_block.name in clothing_blend_shape_labels
                                and key_block.name not in base_blend_shape_labels
                            ):
                                prev_shape_key = obj.data.shape_keys.key_blocks.get(
                                    key_block.name
                                )
                                obj.shape_key_remove(prev_shape_key)
                                print(
                                    f"Removed shape key: {key_block.name} from {obj.name}"
                                )

            set_highheel_shapekey_values(
                self.clothing_meshes,
                self.blend_shape_labels,
                self.base_avatar_data,
            )

            preprocess_end = time.time()
            print(f"FBXエクスポート前処理: {preprocess_end - preprocess_start:.2f}秒")

            bpy.ops.object.select_all(action='DESELECT')
            for obj in bpy.data.objects:
                if obj.name not in [
                    "Body.BaseAvatar",
                    "Armature.BaseAvatar",
                    "Body.BaseAvatar.RightOnly",
                    "Body.BaseAvatar.LeftOnly",
                ]:
                    obj.select_set(True)

            round_bone_coordinates(self.clothing_armature, decimal_places=6)

            print("Status: FBXエクスポート中")
            print(
                f"Progress: {(self.pair_index + 0.98) / self.total_pairs * 0.9:.3f}"
            )
            export_start = time.time()
            export_fbx(self.args.output)
            export_end = time.time()
            print(f"FBXエクスポート: {export_end - export_start:.2f}秒")

        _run(self.processor)
