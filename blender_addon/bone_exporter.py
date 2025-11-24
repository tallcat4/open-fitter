bl_info = {
    "name": "OpenFitter Bone Exporter",
    "author": "OpenFitter",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > OpenFitter",
    "description": "Exports bone pose differences for Unity BoneDeformer.",
    "category": "Import-Export",
}

import bpy
import json
import math
import os
from mathutils import Matrix, Vector

def matrix_to_list(matrix):
    return [list(row) for row in matrix]

def save_armature_pose(armature_obj, filepath):
    """
    Saves the pose of the bones of the active Armature to a JSON file.
    Exports the Local Basis (Pose Mode) values which represent the delta from Rest Pose.
    """
    if not armature_obj:
        raise ValueError("No armature object found")
    
    if armature_obj.type != 'ARMATURE':
        raise ValueError(f"Active object '{armature_obj.name}' is not an armature")

    pose_data = {}
    
    # Iterate over all pose bones
    for bone in armature_obj.pose.bones:
        bone_name = bone.name
        
        # 1. Get Local Basis Values (Delta from Rest Pose)
        # These correspond to the values in the Transform panel in Pose Mode.
        
        # Location: Translation from Rest Head in Bone's Rest Frame
        loc = bone.location
        
        # Rotation: Rotation relative to Rest Orientation
        if bone.rotation_mode == 'QUATERNION':
            rot = bone.rotation_quaternion.to_euler('XYZ')
        elif bone.rotation_mode == 'AXIS_ANGLE':
            # axis_angle is [angle, x, y, z]
            rot = Quaternion(bone.rotation_axis_angle[1:], bone.rotation_axis_angle[0]).to_euler('XYZ')
        else:
            # Euler modes
            rot = bone.rotation_euler
            
        # Scale: Scale factor relative to Rest Scale (1.0)
        scale = bone.scale
        
        # 2. Calculate World Space info for reference/compatibility
        # (We keep these fields to maintain structure compatibility, though Unity might not use them all)
        
        # Get the rest pose matrix (Local space relative to Armature)
        base_matrix = armature_obj.data.bones[bone_name].matrix_local
        
        # Calculate World Space matrices
        world_matrix = armature_obj.matrix_world @ bone.matrix
        base_world_matrix = armature_obj.matrix_world @ base_matrix
        
        # Calculate Delta Matrix (World Space)
        try:
            delta_matrix = world_matrix @ base_world_matrix.inverted()
        except ValueError:
            delta_matrix = Matrix.Identity(4)

        # Calculate Head positions
        head_local = armature_obj.data.bones[bone_name].head_local
        head_world = armature_obj.matrix_world @ head_local
        head_world_transformed = armature_obj.matrix_world @ bone.head
        
        # Calculate values from Delta Matrix (World Space Delta)
        # This matches the original MochiFitter specification.
        # Note: This includes parent transformations (accumulated delta).
        
        # Location: Translation component of the delta matrix? 
        # Original code used: location = head_world_transformed - head_world
        # Let's stick to that as it's robust.
        location = head_world_transformed - head_world
        
        # Rotation: Euler angles from delta matrix
        rot = delta_matrix.to_euler('XYZ')
        
        # Scale: Scale from delta matrix
        scale = delta_matrix.to_scale()
        
        pose_data[bone_name] = {
            'location': [location.x, location.y, location.z],
            'rotation': [math.degrees(rot.x), 
                        math.degrees(rot.y), 
                        math.degrees(rot.z)],
            'scale': [scale.x, scale.y, scale.z],
            
            # Keep World Space reference data
            'head_world': [head_world.x, head_world.y, head_world.z],
            'head_world_transformed': [head_world_transformed.x, head_world_transformed.y, head_world_transformed.z],
            'delta_matrix': matrix_to_list(delta_matrix)
        }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(pose_data, f, indent=4)
        
    return len(pose_data)

class ExportBonePose(bpy.types.Operator):
    """Export Bone Pose to JSON"""
    bl_idname = "export_pose.json"
    bl_label = "Export Bone Pose JSON"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        if not self.filepath:
            self.filepath = os.path.join(os.path.dirname(bpy.data.filepath), "pose_data.json")
            
        if not self.filepath.lower().endswith(".json"):
            self.filepath += ".json"
            
        try:
            count = save_armature_pose(context.active_object, self.filepath)
            self.report({'INFO'}, f"Exported {count} bones to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
            
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class OPENFITTER_PT_bone_export(bpy.types.Panel):
    bl_label = "Bone Pose Export"
    bl_idname = "OPENFITTER_PT_bone_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OpenFitter"
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        layout.label(text="Active Armature: " + (obj.name if obj else "None"))
        
        if obj and obj.type == 'ARMATURE':
            layout.operator(ExportBonePose.bl_idname, icon='EXPORT')
        else:
            layout.label(text="Select an Armature", icon='INFO')

def register():
    bpy.utils.register_class(ExportBonePose)
    bpy.utils.register_class(OPENFITTER_PT_bone_export)
    # bpy.types.TOPBAR_MT_file_export.append(menu_func_export) # Removed menu entry

def unregister():
    # bpy.types.TOPBAR_MT_file_export.remove(menu_func_export) # Removed menu entry
    bpy.utils.unregister_class(OPENFITTER_PT_bone_export)
    bpy.utils.unregister_class(ExportBonePose)

if __name__ == "__main__":
    register()