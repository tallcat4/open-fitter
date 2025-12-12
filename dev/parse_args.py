import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import argparse
import json

from mathutils import Vector
from process_blendshape_transitions import process_blendshape_transitions


def parse_args():
    parser = argparse.ArgumentParser()
    
    # 既存の引数
    parser.add_argument('--input', required=True, help='Input clothing FBX file path')
    parser.add_argument('--output', required=True, help='Output FBX file path')
    parser.add_argument('--base', required=True, help='Base Blender file path')
    parser.add_argument('--base-fbx', required=True, help='Semicolon-separated list of base avatar FBX file paths')
    parser.add_argument('--config', required=True, help='Semicolon-separated list of config file paths')
    parser.add_argument('--hips-position', type=str, help='Target Hips bone world position (x,y,z format)')
    parser.add_argument('--blend-shapes', type=str, help='Semicolon-separated list of blend shape labels to apply')
    parser.add_argument('--cloth-metadata', type=str, help='Path to cloth metadata JSON file')
    parser.add_argument('--mesh-material-data', type=str, help='Path to mesh material data JSON file')
    parser.add_argument('--init-pose', required=True, help='Initial pose data JSON file path')
    parser.add_argument('--target-meshes', required=False, help='Semicolon-separated list of mesh names to process')
    parser.add_argument('--no-subdivision', action='store_true', help='Disable subdivision during DeformationField deformation')
    parser.add_argument('--no-triangle', action='store_true', help='Disable mesh triangulation')
    parser.add_argument('--blend-shape-values', type=str, help='Semicolon-separated list of float values for blend shape intensities')
    parser.add_argument('--blend-shape-mappings', type=str, help='Semicolon-separated mappings of label,customName pairs')
    parser.add_argument('--name-conv', type=str, help='Path to bone name conversion JSON file')
    parser.add_argument('--mesh-renderers', type=str, help='Semicolon-separated list of meshObject,parentObject pairs')
    parser.add_argument('--preserve-bone-names', action='store_true', help='Preserve original input FBX bone names in output (do not rename to target avatar bone names)')
    
    print(sys.argv)
    

    # Get all args after "--"
    argv = sys.argv
    if "--" not in argv:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args(argv[argv.index("--") + 1:])
    
    # Fallback markers - paths starting with these are not validated
    # Template.fbx, pose_basis_template.json, avatar_data_template.json use fallback
    def is_fallback_marker(path):
        """Check if path is a fallback marker (not a real file path)."""
        if not path:
            return False
        markers = ['UNUSED', 'FALLBACK', 'NONE', 'SKIP', '__']
        upper_path = path.upper()
        return any(upper_path.startswith(m) or m in upper_path for m in markers)
    
    # Parse semicolon-separated base-fbx and config paths
    base_fbx_paths = [path.strip() for path in args.base_fbx.split(';')]
    config_paths = [path.strip() for path in args.config.split(';')]
    
    # Validate that base-fbx and config have the same number of entries
    if len(base_fbx_paths) != len(config_paths):
        print(f"Error: Number of base-fbx files ({len(base_fbx_paths)}) must match number of config files ({len(config_paths)})")
        sys.exit(1)
    
    # Validate basic file paths
    required_paths = [
        args.input, args.base
    ]
    for path in required_paths:
        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            sys.exit(1)
    
    # Validate init_pose (allow fallback markers for identity matrix case)
    if not is_fallback_marker(args.init_pose) and not os.path.exists(args.init_pose):
        print(f"Error: Init pose file not found: {args.init_pose}")
        sys.exit(1)
    
    # Validate base-fbx files:
    # - Fallback markers (UNUSED_TEMPLATE, etc.) are allowed without validation
    # - If only 1 config pair: validate the single base_fbx (unless fallback marker)
    # - If multiple config pairs: only validate the last base_fbx (intermediate ones use fallback)
    if len(base_fbx_paths) == 1:
        # Single config pair: validate the base_fbx unless it's a fallback marker
        if not is_fallback_marker(base_fbx_paths[0]) and not os.path.exists(base_fbx_paths[0]):
            print(f"Error: Base FBX file not found: {base_fbx_paths[0]}")
            sys.exit(1)
    elif len(base_fbx_paths) >= 2:
        # Multiple config pairs: only validate the last base_fbx
        last_base_fbx = base_fbx_paths[-1]
        if not is_fallback_marker(last_base_fbx) and not os.path.exists(last_base_fbx):
            print(f"Error: Base FBX file not found: {last_base_fbx}")
            sys.exit(1)
    
    # Validate all config files exist
    for path in config_paths:
        if not os.path.exists(path):
            print(f"Error: Config file not found: {path}")
            sys.exit(1)
    
    # Process each config file and create configuration pairs
    config_pairs = []
    for i, (base_fbx_path, config_path) in enumerate(zip(base_fbx_paths, config_paths)):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # blendShapeFieldsの重複するlabelとsourceLabelに___idを付加
            if 'blendShapeFields' in config_data:
                blend_shape_fields = config_data['blendShapeFields']
                
                # labelの重複をチェックして___idを付加
                label_counts = {}
                for field in blend_shape_fields:
                    label = field.get('label', '')
                    if label:
                        label_counts[label] = label_counts.get(label, 0) + 1
                
                label_ids = {}
                for field in blend_shape_fields:
                    label = field.get('label', '')
                    if label and label_counts[label] > 1:
                        current_id = label_ids.get(label, 0)
                        field['label'] = f"{label}___{current_id}"
                        label_ids[label] = current_id + 1
                
                # sourceLabelの重複をチェックして___idを付加
                source_label_counts = {}
                for field in blend_shape_fields:
                    source_label = field.get('sourceLabel', '')
                    if source_label:
                        source_label_counts[source_label] = source_label_counts.get(source_label, 0) + 1
                
                source_label_ids = {}
                for field in blend_shape_fields:
                    source_label = field.get('sourceLabel', '')
                    if source_label and source_label_counts[source_label] > 1:
                        current_id = source_label_ids.get(source_label, 0)
                        field['sourceLabel'] = f"{source_label}___{current_id}"
                        source_label_ids[source_label] = current_id + 1
            
            # Get config file directory
            config_dir = os.path.dirname(os.path.abspath(config_path))
            
            # Extract and resolve avatar data paths
            pose_data_path = config_data.get('poseDataPath')
            field_data_path = config_data.get('fieldDataPath')
            base_avatar_data_path = config_data.get('baseAvatarDataPath')
            clothing_avatar_data_path = config_data.get('clothingAvatarDataPath')
            
            if not pose_data_path:
                print(f"Error: poseDataPath not found in config file: {config_path}")
                sys.exit(1)
            if not field_data_path:
                print(f"Error: fieldDataPath not found in config file: {config_path}")
                sys.exit(1)
            if not base_avatar_data_path:
                print(f"Error: baseAvatarDataPath not found in config file: {config_path}")
                sys.exit(1)
            if not clothing_avatar_data_path:
                print(f"Error: clothingAvatarDataPath not found in config file: {config_path}")
                sys.exit(1)
            
            # Convert relative paths to absolute paths
            if not os.path.isabs(pose_data_path):
                pose_data_path = os.path.join(config_dir, pose_data_path)
            if not os.path.isabs(field_data_path):
                field_data_path = os.path.join(config_dir, field_data_path)
            if not os.path.isabs(base_avatar_data_path):
                base_avatar_data_path = os.path.join(config_dir, base_avatar_data_path)
            if not os.path.isabs(clothing_avatar_data_path):
                clothing_avatar_data_path = os.path.join(config_dir, clothing_avatar_data_path)
            
            # Helper to check if path is Template avatar data (allows fallback)
            def is_template_avatar_path(path):
                return "avatar_data_template" in os.path.basename(path).lower()
            
            # Validate data file paths (fallback markers and Template paths skip validation)
            if not is_fallback_marker(pose_data_path) and not os.path.exists(pose_data_path):
                print(f"Error: Pose data file not found: {pose_data_path} (from config {config_path})")
                sys.exit(1)
            if not is_fallback_marker(field_data_path) and not os.path.exists(field_data_path):
                print(f"Error: Field data file not found: {field_data_path} (from config {config_path})")
                sys.exit(1)
            # Template avatar data uses fallback generation
            if not is_fallback_marker(base_avatar_data_path) and not is_template_avatar_path(base_avatar_data_path) and not os.path.exists(base_avatar_data_path):
                print(f"Error: Base avatar data file not found: {base_avatar_data_path} (from config {config_path})")
                sys.exit(1)
            if not is_fallback_marker(clothing_avatar_data_path) and not is_template_avatar_path(clothing_avatar_data_path) and not os.path.exists(clothing_avatar_data_path):
                print(f"Error: Clothing avatar data file not found: {clothing_avatar_data_path} (from config {config_path})")
                sys.exit(1)
            
            hips_position = None
            target_meshes = None
            init_pose = None
            blend_shapes = None
            blend_shape_values = None
            blend_shape_mappings = None
            mesh_renderers = None
            input_clothing_fbx_path = args.output
            if i == 0:
                if args.hips_position:
                    x, y, z = map(float, args.hips_position.split(','))
                    hips_position = Vector((x, y, z))
                target_meshes = args.target_meshes
                init_pose = args.init_pose
                blend_shapes = args.blend_shapes
                # Parse blend shape values if provided
                if args.blend_shape_values:
                    try:
                        blend_shape_values = [float(v.strip()) for v in args.blend_shape_values.split(';')]
                    except ValueError as e:
                        print(f"Error: Invalid blend shape values format: {e}")
                        sys.exit(1)
                # Parse blend shape mappings if provided
                if args.blend_shape_mappings:
                    try:
                        blend_shape_mappings = {}
                        pairs = args.blend_shape_mappings.split(';')
                        for pair in pairs:
                            if pair.strip():
                                label, custom_name = pair.split(',', 1)
                                blend_shape_mappings[label.strip()] = custom_name.strip()
                    except ValueError as e:
                        print(f"Error: Invalid blend shape mappings format: {e}")
                        sys.exit(1)
                # Parse mesh renderers if provided
                if args.mesh_renderers:
                    try:
                        mesh_renderers = {}
                        pairs = args.mesh_renderers.split(';')
                        for pair in pairs:
                            if pair.strip():
                                mesh_name, parent_name = pair.split(':', 1)
                                mesh_renderers[mesh_name.strip()] = parent_name.strip()
                        print(f"Parsed mesh renderers: {mesh_renderers}")
                    except ValueError as e:
                        print(f"Error: Invalid mesh renderers format: {e}")
                        sys.exit(1)
                input_clothing_fbx_path = args.input
            
            skip_blend_shape_generation = True
            if i == len(config_paths) - 1:
                skip_blend_shape_generation = False

            do_not_use_base_pose = config_data.get('doNotUseBasePose', 0)
            
            # Create configuration pair
            config_pair = {
                'base_fbx': base_fbx_path,
                'config_path': config_path,
                'config_data': config_data,
                'pose_data': pose_data_path,
                'field_data': field_data_path,
                'base_avatar_data': base_avatar_data_path,
                'clothing_avatar_data': clothing_avatar_data_path,
                'hips_position': hips_position,
                'target_meshes': target_meshes,
                'init_pose': init_pose,
                'blend_shapes': blend_shapes,
                'blend_shape_values': blend_shape_values,
                'blend_shape_mappings': blend_shape_mappings,
                'mesh_renderers': mesh_renderers,
                'input_clothing_fbx_path': input_clothing_fbx_path,
                'skip_blend_shape_generation': skip_blend_shape_generation,
                'do_not_use_base_pose': do_not_use_base_pose
            }
            config_pairs.append(config_pair)
            
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in config file {config_path}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading config file {config_path}: {e}")
            sys.exit(1)
    
    # Process BlendShape transitions for consecutive config pairs
    if len(config_pairs) >= 2:
        for i in range(len(config_pairs) - 1):
            process_blendshape_transitions(config_pairs[i], config_pairs[i + 1])
        config_pairs[len(config_pairs) - 1]['next_blendshape_settings'] = config_pairs[len(config_pairs) - 1]['config_data'].get('targetBlendShapeSettings', [])
    
    # 中間pairではbase_fbxを使用しない（最終pairでのみターゲットアバターFBXをロード）
    # Template.fbx依存を排除するため、中間pairのbase_fbxをNoneに設定
    if len(config_pairs) >= 2:
        for i in range(len(config_pairs) - 1):
            config_pairs[i]['base_fbx'] = None
    
    # Store configuration pairs in args for later use
    args.config_pairs = config_pairs
    
    # --preserve-bone-namesが有効な場合、最初のペアのclothing_avatar_dataから
    # 元のボーン名マッピングを作成して全ペアに共有
    if args.preserve_bone_names and len(config_pairs) > 0:
        first_clothing_avatar_data_path = config_pairs[0]['clothing_avatar_data']
        try:
            from io_utils.io_utils import load_avatar_data
            first_clothing_avatar_data = load_avatar_data(first_clothing_avatar_data_path)
            
            # 元のボーン名マッピングを作成
            original_bone_mapping = {
                'humanoidBones': {
                    b['humanoidBoneName']: b['boneName']
                    for b in first_clothing_avatar_data.get('humanoidBones', [])
                },
                'auxiliaryBones': {}
            }
            # Auxiliaryボーンのマッピングも保存
            for aux_set in first_clothing_avatar_data.get('auxiliaryBones', []):
                humanoid_name = aux_set.get('humanoidBoneName')
                aux_bones = aux_set.get('auxiliaryBones', [])
                if humanoid_name:
                    original_bone_mapping['auxiliaryBones'][humanoid_name] = aux_bones
            
            # 全ペアに共有
            for pair in config_pairs:
                pair['original_bone_mapping'] = original_bone_mapping
            
            print(f"[preserve-bone-names] Original bone mapping created from: {first_clothing_avatar_data_path}")
            print(f"[preserve-bone-names] Humanoid bones: {len(original_bone_mapping['humanoidBones'])}")
            print(f"[preserve-bone-names] Auxiliary bone groups: {len(original_bone_mapping['auxiliaryBones'])}")
        except Exception as e:
            print(f"Warning: Failed to create original bone mapping: {e}")
            for pair in config_pairs:
                pair['original_bone_mapping'] = None
            
    # Parse hips position if provided
    if args.hips_position:
        try:
            x, y, z = map(float, args.hips_position.split(','))
            args.hips_position = Vector((x, y, z))
        except:
            print("Error: Invalid hips position format. Use x,y,z")
            sys.exit(1)
            
    return args, config_pairs
