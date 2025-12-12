"""ExportPreparationStage: シェイプキー設定・エクスポート前処理・FBXエクスポートを担当するステージ"""

import json
import os
import re
import sys

import bpy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
for _p in (_PARENT_DIR,):
    if _p not in sys.path:
        sys.path.append(_p)

from blender_utils.blendshape_utils import (
    merge_and_clean_generated_shapekeys,
)
from blender_utils.bone_utils import round_bone_coordinates
from blender_utils.bone_utils import restore_original_bone_names
from blender_utils.blendshape_utils import set_highheel_shapekey_values
from io_utils.io_utils import export_fbx
from io_utils.io_utils import update_cloth_metadata


class ExportPreparationStage:
    """シェイプキー設定・エクスポート前処理・FBXエクスポートを担当するステージ
    
    責務:
        - ブレンドシェイプ設定適用
        - クロスメタデータ更新
        - シェイプキーのマージ・クリーンアップ
        - ハイヒールシェイプキー値設定
        - オブジェクト選択
        - ボーン座標の丸め
        - FBXエクスポート
    
    ベースメッシュ依存:
        - 不要（衣装データのみ使用）
        - Body.BaseAvatarの名前参照はあるが必須ではない
    
    前提:
        - BoneReplacementStage が完了していること
    
    成果物:
        - 出力FBXファイル
    """
    
    # ベースメッシュ依存フラグ: 不要
    REQUIRES_BASE_MESH = False

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def run(self):
        p = self.pipeline
        time = p.time_module

        # ブレンドシェイプ設定
        self._apply_blendshape_settings(p, time)

        # クロスメタデータ更新
        self._update_cloth_metadata(p, time)

        # エクスポート前処理
        self._preprocess_for_export(p, time)

        # FBXエクスポート
        self._export_fbx(p, time)

    def _apply_blendshape_settings(self, p, time):
        """ブレンドシェイプ設定を適用"""
        if "clothingBlendShapeSettings" in p.config_pair['config_data']:
            blend_shape_settings = p.config_pair['config_data']["clothingBlendShapeSettings"]

            for setting in blend_shape_settings:
                label = setting.get("label")
                if label in p.blend_shape_labels:
                    blendshapes = setting.get("blendshapes", [])
                    for bs in blendshapes:
                        shape_key_name = bs.get("name")
                        value = bs.get("value", 0)
                        for obj in p.clothing_meshes:
                            if (
                                obj.data.shape_keys
                                and shape_key_name in obj.data.shape_keys.key_blocks
                            ):
                                obj.data.shape_keys.key_blocks[shape_key_name].value = value / 100.0

    def _update_cloth_metadata(self, p, time):
        """クロスメタデータを更新"""
        if p.args.cloth_metadata and os.path.exists(p.args.cloth_metadata):
            try:
                with open(p.args.cloth_metadata, 'r', encoding='utf-8') as f:
                    metadata_dict = json.load(f)
                update_cloth_metadata(
                    metadata_dict,
                    p.args.cloth_metadata,
                    p.vertex_index_mapping,
                )
            except Exception as e:
                import traceback
                traceback.print_exc()

    def _preprocess_for_export(self, p, time):
        """エクスポート前処理"""
        # BlendShapeラベルの再設定
        p.blend_shape_labels = []
        if p.args.blend_shapes:
            p.blend_shape_labels = [label for label in p.args.blend_shapes.split(',')]

        # 生成されたシェイプキーのマージ・クリーンアップ
        merge_and_clean_generated_shapekeys(p.clothing_meshes, p.blend_shape_labels)

        # Template固有のシェイプキー削除
        if p.clothing_avatar_data.get("name", None) == "Template":
            pattern = re.compile(r'___\d+$')
            for obj in p.clothing_meshes:
                if obj.data.shape_keys:
                    keys_to_remove = []
                    for key_block in obj.data.shape_keys.key_blocks:
                        if pattern.search(key_block.name):
                            keys_to_remove.append(key_block.name)
                    for key_name in keys_to_remove:
                        key_block = obj.data.shape_keys.key_blocks.get(key_name)
                        if key_block:
                            obj.shape_key_remove(key_block)

        # 複数ペアの場合のシェイプキー削除
        if p.pair_index > 0:
            bpy.ops.object.mode_set(mode='OBJECT')
            clothing_blend_shape_labels = []
            for blend_shape_field in p.clothing_avatar_data['blendShapeFields']:
                clothing_blend_shape_labels.append(blend_shape_field['label'])
            base_blend_shape_labels = []
            for blend_shape_field in p.base_avatar_data['blendShapeFields']:
                base_blend_shape_labels.append(blend_shape_field['label'])
            for obj in p.clothing_meshes:
                if obj.data.shape_keys:
                    for key_block in obj.data.shape_keys.key_blocks:
                        if (
                            key_block.name in clothing_blend_shape_labels
                            and key_block.name not in base_blend_shape_labels
                        ):
                            prev_shape_key = obj.data.shape_keys.key_blocks.get(key_block.name)
                            obj.shape_key_remove(prev_shape_key)

        # ハイヒールシェイプキー値設定
        set_highheel_shapekey_values(
            p.clothing_meshes,
            p.blend_shape_labels,
            p.base_avatar_data,
        )

    def _export_fbx(self, p, time):
        """FBXエクスポート"""
        # ボーン名復元（--preserve-bone-namesが有効な場合）
        if getattr(p.args, 'preserve_bone_names', False):
            original_bone_mapping = p.config_pair.get('original_bone_mapping')
            if original_bone_mapping:
                print("[ExportPreparation] Restoring original bone names from first input FBX...")
                restore_original_bone_names(
                    p.clothing_armature,
                    p.clothing_meshes,
                    p.base_avatar_data,
                    original_bone_mapping,
                )
            else:
                print("[ExportPreparation] Warning: original_bone_mapping not found, skipping bone name restoration")
        
        # オブジェクト選択
        bpy.ops.object.select_all(action='DESELECT')
        for obj in bpy.data.objects:
            if obj.name not in [
                "Body.BaseAvatar",
                "Armature.BaseAvatar",
                "Body.BaseAvatar.RightOnly",
                "Body.BaseAvatar.LeftOnly",
            ]:
                obj.select_set(True)

        # ボーン座標の丸め
        round_bone_coordinates(p.clothing_armature, decimal_places=6)

        # FBXエクスポート
        export_fbx(p.args.output)
