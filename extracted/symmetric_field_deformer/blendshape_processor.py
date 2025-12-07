"""
blendshape_processor - BlendShape生成処理モジュール

Config/Clothing/BaseAvatar からのBlendShape生成を担当する。
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy
import numpy as np
from blender_utils.batch_process_vertices_multi_step import (
    batch_process_vertices_multi_step,
)
from blender_utils.create_blendshape_mask import create_blendshape_mask
from blender_utils.get_armature_from_modifier import get_armature_from_modifier
from common_utils.get_source_label import get_source_label
from io_utils.shape_key_state import restore_shape_key_state, save_shape_key_state
from math_utils.calculate_inverse_pose_matrix import calculate_inverse_pose_matrix
from mathutils import Matrix, Vector
from misc_utils.get_deformation_field_multi_step import get_deformation_field_multi_step
from process_field_deformation import process_field_deformation


def process_config_blendshapes(ctx):
    """
    Configファイルに基づくBlendShape処理を実行する。

    Args:
        ctx: SymmetricFieldDeformerContext インスタンス
    """
    if not (ctx.config_data and "blendShapeFields" in ctx.config_data):
        return

    print("Processing config blendShapeFields...")

    for blend_field in ctx.config_data["blendShapeFields"]:
        label = blend_field["label"]
        source_label = blend_field["sourceLabel"]
        field_path = os.path.join(
            os.path.dirname(ctx.field_data_path), blend_field["path"]
        )

        print(f"selected field_path: {field_path}")
        source_blend_shape_settings = blend_field.get("sourceBlendShapeSettings", [])

        if (
            ctx.blend_shape_labels is None or source_label not in ctx.blend_shape_labels
        ) and source_label not in ctx.target_obj.data.shape_keys.key_blocks:
            print(f"Skipping {label} - source label {source_label} not in shape keys")
            continue

        mask_bones = blend_field.get("maskBones", [])
        mask_weights = None
        if mask_bones:
            mask_weights = create_blendshape_mask(
                ctx.target_obj,
                mask_bones,
                ctx.clothing_avatar_data,
                field_name=label,
                store_debug_mask=True,
            )

        if mask_weights is not None and np.all(mask_weights == 0):
            print(f"Skipping {label} - all mask weights are zero")
            continue

        original_shape_key_state = save_shape_key_state(ctx.target_obj)

        if ctx.target_obj.data.shape_keys:
            for key_block in ctx.target_obj.data.shape_keys.key_blocks:
                key_block.value = 0.0

        if ctx.clothing_avatar_data["name"] == "Template":
            if ctx.target_obj.data.shape_keys:
                if source_label in ctx.target_obj.data.shape_keys.key_blocks:
                    source_shape_key = ctx.target_obj.data.shape_keys.key_blocks.get(
                        source_label
                    )
                    source_shape_key.value = 1.0
                    print(f"source_label: {source_label} is found in shape keys")
                else:
                    temp_shape_key_name = f"{source_label}_temp"
                    if temp_shape_key_name in ctx.target_obj.data.shape_keys.key_blocks:
                        ctx.target_obj.data.shape_keys.key_blocks[
                            temp_shape_key_name
                        ].value = 1.0
                        print(
                            f"temp_shape_key_name: {temp_shape_key_name} is found in shape keys"
                        )
        else:
            for source_blend_shape_setting in source_blend_shape_settings:
                source_blend_shape_name = source_blend_shape_setting.get("name", "")
                source_blend_shape_value = source_blend_shape_setting.get("value", 0.0)
                if (
                    source_blend_shape_name
                    in ctx.target_obj.data.shape_keys.key_blocks
                ):
                    source_blend_shape_key = (
                        ctx.target_obj.data.shape_keys.key_blocks.get(
                            source_blend_shape_name
                        )
                    )
                    source_blend_shape_key.value = source_blend_shape_value
                    print(
                        f"source_blend_shape_name: {source_blend_shape_name} is found in shape keys"
                    )
                else:
                    temp_blend_shape_key_name = f"{source_blend_shape_name}_temp"
                    if (
                        temp_blend_shape_key_name
                        in ctx.target_obj.data.shape_keys.key_blocks
                    ):
                        ctx.target_obj.data.shape_keys.key_blocks[
                            temp_blend_shape_key_name
                        ].value = source_blend_shape_value
                        print(
                            f"temp_blend_shape_key_name: {temp_blend_shape_key_name} is found in shape keys"
                        )

        blend_shape_key_name = label
        if (
            ctx.target_obj.data.shape_keys
            and label in ctx.target_obj.data.shape_keys.key_blocks
        ):
            blend_shape_key_name = f"{label}_generated"

        if os.path.exists(field_path):
            print(
                f"Processing config blend shape field: {label} -> {blend_shape_key_name}"
            )
            generated_shape_key = process_field_deformation(
                ctx.target_obj,
                field_path,
                ctx.blend_shape_labels,
                ctx.clothing_avatar_data,
                blend_shape_key_name,
                ctx.ignore_blendshape,
            )

            if ctx.config_data and generated_shape_key:
                ctx.deferred_transitions.append(
                    {
                        "target_obj": ctx.target_obj,
                        "config_data": ctx.config_data,
                        "target_label": label,
                        "target_shape_key_name": generated_shape_key.name,
                        "base_avatar_data": ctx.base_avatar_data,
                        "clothing_avatar_data": ctx.clothing_avatar_data,
                        "save_original_shape_key": False,
                    }
                )

            if generated_shape_key:
                generated_shape_key.value = 0.0
                ctx.config_generated_shape_keys[generated_shape_key.name] = mask_weights
                ctx.non_relative_shape_keys.add(generated_shape_key.name)

            ctx.config_blend_shape_labels.add(label)
            ctx.label_to_target_shape_key_name[label] = generated_shape_key.name
        else:
            print(f"Warning: Config blend shape field file not found: {field_path}")

        restore_shape_key_state(ctx.target_obj, original_shape_key_state)


def process_skipped_transitions(ctx):
    """
    スキップされた遷移の処理を実行する。

    Args:
        ctx: SymmetricFieldDeformerContext インスタンス
    """
    if not (
        ctx.config_data and ctx.config_data.get("blend_shape_transition_sets", [])
    ):
        return

    transition_sets = ctx.config_data.get("blend_shape_transition_sets", [])
    print("Processing skipped config blendShapeFields...")

    for transition_set in transition_sets:
        label = transition_set["label"]
        if label in ctx.config_blend_shape_labels or label == "Basis":
            continue

        source_label = get_source_label(label, ctx.config_data)
        if source_label not in ctx.label_to_target_shape_key_name:
            print(
                f"Skipping {label} - source label {source_label} not in label_to_target_shape_key_name"
            )
            continue

        print(f"Processing skipped config blendShapeField: {label}")

        mask_bones = transition_set.get("mask_bones", [])
        print(f"mask_bones: {mask_bones}")
        mask_weights = None
        if mask_bones:
            mask_weights = create_blendshape_mask(
                ctx.target_obj,
                mask_bones,
                ctx.clothing_avatar_data,
                field_name=label,
                store_debug_mask=True,
            )

        if mask_weights is not None and np.all(mask_weights == 0):
            print(f"Skipping {label} - all mask weights are zero")
            continue

        target_shape_key_name = ctx.label_to_target_shape_key_name[source_label]
        target_shape_key = ctx.target_obj.data.shape_keys.key_blocks.get(
            target_shape_key_name
        )

        if not target_shape_key:
            print(
                f"Skipping {label} - target shape key {target_shape_key_name} not found"
            )
            continue

        blend_shape_key_name = label
        if (
            ctx.target_obj.data.shape_keys
            and label in ctx.target_obj.data.shape_keys.key_blocks
        ):
            blend_shape_key_name = f"{label}_generated"

        skipped_blend_shape_key = ctx.target_obj.shape_key_add(name=blend_shape_key_name)

        for i in range(len(skipped_blend_shape_key.data)):
            skipped_blend_shape_key.data[i].co = target_shape_key.data[i].co.copy()

        print(f"skipped_blend_shape_key: {skipped_blend_shape_key.name}")

        if ctx.config_data and skipped_blend_shape_key:
            ctx.deferred_transitions.append(
                {
                    "target_obj": ctx.target_obj,
                    "config_data": ctx.config_data,
                    "target_label": label,
                    "target_shape_key_name": skipped_blend_shape_key.name,
                    "base_avatar_data": ctx.base_avatar_data,
                    "clothing_avatar_data": ctx.clothing_avatar_data,
                    "save_original_shape_key": False,
                }
            )

            print(
                f"Added deferred transition: {label} -> {skipped_blend_shape_key.name}"
            )

            ctx.config_generated_shape_keys[skipped_blend_shape_key.name] = mask_weights
            ctx.non_relative_shape_keys.add(skipped_blend_shape_key.name)
            ctx.config_blend_shape_labels.add(label)
            ctx.label_to_target_shape_key_name[label] = skipped_blend_shape_key.name


def process_clothing_blendshapes(ctx):
    """
    Clothing由来のBlendShape処理を実行する。

    Args:
        ctx: SymmetricFieldDeformerContext インスタンス
    """
    if not ctx.target_obj.data.shape_keys:
        return

    clothing_blendshapes = set()
    if ctx.clothing_avatar_data and "blendshapes" in ctx.clothing_avatar_data:
        for blendshape in ctx.clothing_avatar_data["blendshapes"]:
            clothing_blendshapes.add(blendshape["name"])

    current_shape_key_blocks = [
        key_block for key_block in ctx.target_obj.data.shape_keys.key_blocks
    ]

    for key_block in current_shape_key_blocks:
        if (
            key_block.name == "Basis"
            or key_block.name in clothing_blendshapes
            or key_block == ctx.shape_key
            or key_block.name.endswith("_BaseShape")
            or key_block.name in ctx.config_generated_shape_keys.keys()
            or key_block.name in ctx.config_blend_shape_labels
            or key_block.name.endswith("_original")
            or key_block.name.endswith("_generated")
            or key_block.name.endswith("_temp")
        ):
            continue

        print(f"Processing additional shape key: {key_block.name}")

        original_shape_key_state = save_shape_key_state(ctx.target_obj)

        for sk in ctx.target_obj.data.shape_keys.key_blocks:
            sk.value = 0.0

        basis_field_path2 = os.path.join(
            os.path.dirname(ctx.field_data_path), ctx.field_data_path
        )
        source_label = get_source_label("Basis", ctx.config_data)
        if (
            source_label is not None
            and source_label != "Basis"
            and ctx.target_obj.data.shape_keys
        ):
            source_field_path = None
            source_shape_name = None
            if ctx.config_data and "blendShapeFields" in ctx.config_data:
                for blend_field in ctx.config_data["blendShapeFields"]:
                    if blend_field["label"] == source_label:
                        source_field_path = os.path.join(
                            os.path.dirname(ctx.field_data_path), blend_field["path"]
                        )
                        source_shape_name = blend_field["sourceLabel"]
                        break
            if source_field_path is not None and source_shape_name is not None:
                if source_shape_name in ctx.target_obj.data.shape_keys.key_blocks:
                    source_shape_key = ctx.target_obj.data.shape_keys.key_blocks.get(
                        source_shape_name
                    )
                    source_shape_key.value = 1.0
                    basis_field_path2 = source_field_path
                    print(f"source_label: {source_shape_name} is found in shape keys")
                else:
                    temp_shape_key_name = f"{source_shape_name}_temp"
                    if temp_shape_key_name in ctx.target_obj.data.shape_keys.key_blocks:
                        ctx.target_obj.data.shape_keys.key_blocks[
                            temp_shape_key_name
                        ].value = 1.0
                        basis_field_path2 = source_field_path
                        print(
                            f"temp_shape_key_name: {temp_shape_key_name} is found in shape keys"
                        )

        print(f"basis_field_path2: {basis_field_path2}")

        key_block.value = 1.0

        temp_blend_shape_key_name = f"{key_block.name}_generated"

        temp_shape_key = process_field_deformation(
            ctx.target_obj,
            basis_field_path2,
            ctx.blend_shape_labels,
            ctx.clothing_avatar_data,
            temp_blend_shape_key_name,
            ctx.ignore_blendshape,
        )

        ctx.additional_shape_keys.add(temp_shape_key.name)
        ctx.non_relative_shape_keys.add(temp_shape_key.name)

        key_block.value = 0.0

        restore_shape_key_state(ctx.target_obj, original_shape_key_state)


def process_base_avatar_blendshapes(ctx):
    """
    BaseAvatar由来のBlendShape処理を実行する。

    Args:
        ctx: SymmetricFieldDeformerContext インスタンス
    """
    if not (
        ctx.base_avatar_data
        and "blendShapeFields" in ctx.base_avatar_data
        and not ctx.skip_blend_shape_generation
    ):
        return

    armature_obj = get_armature_from_modifier(ctx.target_obj)
    if not armature_obj:
        raise ValueError("Armatureモディファイアが見つかりません")

    original_shape_key_state = save_shape_key_state(ctx.target_obj)

    if ctx.target_obj.data.shape_keys:
        for key_block in ctx.target_obj.data.shape_keys.key_blocks:
            key_block.value = 0.0

    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    eval_obj = ctx.target_obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.data
    vertices = np.array([v.co for v in ctx.target_obj.data.vertices])
    deformed_vertices = np.array([v.co for v in eval_mesh.vertices])

    for blend_field in ctx.base_avatar_data["blendShapeFields"]:
        label = blend_field["label"]

        if label in ctx.config_blend_shape_labels:
            print(
                f"Skipping base avatar blend shape field '{label}' (already processed from config)"
            )
            continue

        field_path = os.path.join(
            os.path.dirname(ctx.field_data_path), blend_field["filePath"]
        )

        if os.path.exists(field_path):
            print(f"Applying blend shape field for {label}")
            field_info_blend = get_deformation_field_multi_step(field_path)
            blend_points = field_info_blend["all_field_points"]
            blend_deltas = field_info_blend["all_delta_positions"]
            blend_field_weights = field_info_blend["field_weights"]
            blend_matrix = field_info_blend["world_matrix"]
            blend_matrix_inv = field_info_blend["world_matrix_inv"]
            blend_k_neighbors = field_info_blend["kdtree_query_k"]

            mask_weights = None
            if "maskBones" in blend_field:
                mask_weights = create_blendshape_mask(
                    ctx.target_obj,
                    blend_field["maskBones"],
                    ctx.clothing_avatar_data,
                    field_name=label,
                    store_debug_mask=True,
                )

            deformed_positions = batch_process_vertices_multi_step(
                deformed_vertices,
                blend_points,
                blend_deltas,
                blend_field_weights,
                blend_matrix,
                blend_matrix_inv,
                ctx.target_obj.matrix_world,
                ctx.target_obj.matrix_world.inverted(),
                mask_weights,
                batch_size=1000,
                k=blend_k_neighbors,
            )

            has_displacement = False
            for i in range(len(deformed_vertices)):
                displacement = deformed_positions[i] - (
                    ctx.target_obj.matrix_world @ Vector(deformed_vertices[i])
                )
                if np.any(np.abs(displacement) > 1e-5):
                    print(f"blendShapeFields {label} world_displacement: {displacement}")
                    has_displacement = True
                    break

            if has_displacement:
                blend_shape_key_name = label
                if (
                    ctx.target_obj.data.shape_keys
                    and label in ctx.target_obj.data.shape_keys.key_blocks
                ):
                    blend_shape_key_name = f"{label}_generated"

                shape_key_b = ctx.target_obj.shape_key_add(name=blend_shape_key_name)
                shape_key_b.value = 0.0

                matrix_armature_inv_fallback = Matrix.Identity(4)
                for i in range(len(vertices)):
                    matrix_armature_inv = calculate_inverse_pose_matrix(
                        ctx.target_obj, armature_obj, i
                    )
                    if matrix_armature_inv is None:
                        matrix_armature_inv = matrix_armature_inv_fallback
                    deformed_world_pos = matrix_armature_inv @ Vector(
                        deformed_positions[i]
                    )
                    deformed_local_pos = (
                        ctx.target_obj.matrix_world.inverted() @ deformed_world_pos
                    )
                    shape_key_b.data[i].co = deformed_local_pos
                    matrix_armature_inv_fallback = matrix_armature_inv
            else:
                print(
                    f"Skipping creation of shape key '{label}' as it has no displacement"
                )

        else:
            print(f"Warning: Field file not found for blend shape {label}")

    restore_shape_key_state(ctx.target_obj, original_shape_key_state)
