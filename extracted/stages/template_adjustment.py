import math
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bpy
import mathutils
from algo_utils.find_vertices_near_faces import find_vertices_near_faces

_CURR_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURR_DIR)
_GRANDPARENT_DIR = os.path.dirname(_PARENT_DIR)
for _p in (_PARENT_DIR, _GRANDPARENT_DIR):
    if _p not in sys.path:
        sys.path.append(_p)

from blender_utils.transfer_weights_from_nearest_vertex import (
    transfer_weights_from_nearest_vertex,
)
from io_utils.import_base_fbx import import_base_fbx
from io_utils.load_vertex_group import load_vertex_group


class TemplateAdjustmentStage:
    """Applies Template-specific corrections before further processing."""

    def __init__(self, processor):
        self.processor = processor

    def run(self):
        def _run(self):
            clothing_name = self.clothing_avatar_data.get("name", None)
            if clothing_name != "Template":
                return True

            print("Templateからの変換 股下の頂点グループを作成")
            current_active_object = bpy.context.view_layer.objects.active
            template_fbx_path = self.clothing_avatar_data.get("defaultFBXPath", None)
            clothing_avatar_data_path = self.config_pair['clothing_avatar_data']
            if template_fbx_path and not os.path.isabs(template_fbx_path):
                relative_parts = template_fbx_path.split(os.sep)
                if relative_parts:
                    top_dir = relative_parts[0]
                    clothing_path_parts = clothing_avatar_data_path.split(os.sep)
                    found_index = -1
                    for i in range(len(clothing_path_parts) - 1, -1, -1):
                        if clothing_path_parts[i] == top_dir:
                            found_index = i
                            break
                    if found_index != -1:
                        base_path = os.sep.join(clothing_path_parts[:found_index])
                        template_fbx_path = os.path.join(base_path, template_fbx_path)
                        template_fbx_path = os.path.normpath(template_fbx_path)
            print(f"template_fbx_path: {template_fbx_path}")
            import_base_fbx(template_fbx_path)
            template_obj = bpy.data.objects.get(
                self.clothing_avatar_data.get("meshName", None)
            )
            template_armature = None
            for modifier in template_obj.modifiers:
                if modifier.type == 'ARMATURE':
                    template_armature = modifier.object
                    break
            if template_armature is None:
                print("Warning: Armatureモディファイアが見つかりません")
                return False

            crotch_vertex_group_filepath = os.path.join(
                os.path.dirname(template_fbx_path), "vertex_group_weights_crotch.json"
            )
            crotch_group_name = load_vertex_group(
                template_obj, crotch_vertex_group_filepath
            )
            if crotch_group_name:
                print("  LeftUpperLegとRightUpperLegボーンにY軸回転を適用")
                bpy.context.view_layer.objects.active = template_armature
                bpy.ops.object.mode_set(mode='POSE')

                left_upper_leg_bone = None
                right_upper_leg_bone = None

                for bone_map in self.clothing_avatar_data.get("humanoidBones", []):
                    if bone_map.get("humanoidBoneName") == "LeftUpperLeg":
                        left_upper_leg_bone = bone_map.get("boneName")
                    elif bone_map.get("humanoidBoneName") == "RightUpperLeg":
                        right_upper_leg_bone = bone_map.get("boneName")

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.context.view_layer.update()

                for obj in self.clothing_meshes:
                    find_vertices_near_faces(
                        template_obj,
                        obj,
                        crotch_group_name,
                        0.01,
                        use_all_faces=True,
                        smooth_repeat=3,
                    )

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in template_armature.pose.bones
                ):
                    bone = template_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        template_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = template_armature.matrix_world @ bone.head
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        template_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    left_upper_leg_bone
                    and left_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[left_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                if (
                    right_upper_leg_bone
                    and right_upper_leg_bone in self.clothing_armature.pose.bones
                ):
                    bone = self.clothing_armature.pose.bones[right_upper_leg_bone]
                    current_world_matrix = (
                        self.clothing_armature.matrix_world @ bone.matrix
                    )
                    head_world_transformed = (
                        self.clothing_armature.matrix_world @ bone.head
                    )
                    offset_matrix = mathutils.Matrix.Translation(
                        head_world_transformed * -1.0
                    )
                    rotation_matrix = mathutils.Matrix.Rotation(
                        math.radians(-40), 4, 'Y'
                    )
                    bone.matrix = (
                        self.clothing_armature.matrix_world.inverted()
                        @ offset_matrix.inverted()
                        @ rotation_matrix
                        @ offset_matrix
                        @ current_world_matrix
                    )

                bpy.context.view_layer.update()

            blur_vertex_group_filepath = os.path.join(
                os.path.dirname(template_fbx_path), "vertex_group_weights_blur.json"
            )
            blur_group_name = load_vertex_group(
                template_obj, blur_vertex_group_filepath
            )
            if blur_group_name:
                for obj in self.clothing_meshes:
                    transfer_weights_from_nearest_vertex(
                        template_obj, obj, blur_group_name
                    )
            inpaint_vertex_group_filepath = os.path.join(
                os.path.dirname(template_fbx_path), "vertex_group_weights_inpaint.json"
            )
            inpaint_group_name = load_vertex_group(
                template_obj, inpaint_vertex_group_filepath
            )
            if inpaint_group_name:
                for obj in self.clothing_meshes:
                    transfer_weights_from_nearest_vertex(
                        template_obj, obj, inpaint_group_name
                    )
            bpy.data.objects.remove(bpy.data.objects["Body.Template"], do_unlink=True)
            bpy.data.objects.remove(
                bpy.data.objects["Body.Template.Eyes"], do_unlink=True
            )
            bpy.data.objects.remove(
                bpy.data.objects["Body.Template.Head"], do_unlink=True
            )
            bpy.data.objects.remove(
                bpy.data.objects["Armature.Template"], do_unlink=True
            )
            print("Templateからの変換 股下の頂点グループ作成完了")
            bpy.context.view_layer.objects.active = current_active_object
            return True

        return _run(self.processor)
