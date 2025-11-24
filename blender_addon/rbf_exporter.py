bl_info = {
    "name": "OpenFitter RBF Exporter",
    "author": "OpenFitter",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > OpenFitter",
    "description": "Exports RBF deformation field from Shape Keys to JSON.",
    "category": "Import-Export",
}

import bpy
import json
import numpy as np
import os
import time

# ------------------------------------------------------------------------
# RBF Core Implementation (Embedded for portability)
# ------------------------------------------------------------------------

class RBFCore:
    """
    RBF (Radial Basis Function) interpolation core.
    Uses Multi-Quadratic Biharmonic Kernel: sqrt(r^2 + epsilon^2)
    """

    def __init__(self, epsilon=1.0, smoothing=0.0):
        self.epsilon = epsilon
        self.smoothing = smoothing
        self.weights = None
        self.polynomial_weights = None
        self.control_points = None
    
    def _kernel_func(self, r):
        return np.sqrt(r**2 + self.epsilon**2)

    def fit(self, source_points, target_points):
        """
        Fits the RBF to the source -> target deformation.
        source_points: (N, 3)
        target_points: (N, 3)
        """
        displacements = target_points - source_points
        self.control_points = source_points
        
        num_pts, dim = source_points.shape
        
        # Calculate distance matrix (using numpy broadcasting)
        # dists[i, j] = distance(source[i], source[j])
        # Memory efficient way for larger N might be needed, but for N=3000 it's fine (~80MB)
        d1 = source_points[:, np.newaxis, :]
        d2 = source_points[np.newaxis, :, :]
        dists = np.sqrt(np.sum((d1 - d2)**2, axis=2))
        
        # Kernel Matrix (Phi)
        phi = self._kernel_func(dists)
        
        # Smoothing
        if self.smoothing > 0:
            phi += np.eye(num_pts) * self.smoothing

        # Polynomial Matrix P (1, x, y, z)
        P = np.ones((num_pts, dim + 1))
        P[:, 1:] = source_points
        
        # Build System Matrix A
        # | Phi  P |
        # | P.T  0 |
        
        A_top = np.hstack([phi, P])
        A_bot = np.hstack([P.T, np.zeros((dim + 1, dim + 1))])
        A = np.vstack([A_top, A_bot])
        
        # RHS b
        # | displacements |
        # |       0       |
        
        b = np.zeros((num_pts + dim + 1, dim))
        b[:num_pts] = displacements
        
        # Solve Ax = b
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            # Fallback to least squares if singular
            reg = np.eye(A.shape[0]) * 1e-6
            x = np.linalg.lstsq(A + reg, b, rcond=None)[0]
            
        self.weights = x[:num_pts]
        self.polynomial_weights = x[num_pts:]

# ------------------------------------------------------------------------
# Blender Operator & Logic
# ------------------------------------------------------------------------

def get_shape_key_names(self, context):
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.data.shape_keys:
        return [(key.name, key.name, "") for key in obj.data.shape_keys.key_blocks]
    return []

class OPENFITTER_OT_estimate_epsilon(bpy.types.Operator):
    """Estimate optimal Epsilon based on average nearest neighbor distance"""
    bl_idname = "openfitter.estimate_epsilon"
    bl_label = "Estimate Epsilon"
    
    def execute(self, context):
        obj = context.active_object
        props = context.scene.openfitter_rbf_props
        
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            self.report({'ERROR'}, "Select a mesh with shape keys first.")
            return {'CANCELLED'}
            
        basis_name = props.basis_shape_key
        if basis_name not in obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, "Basis key not found.")
            return {'CANCELLED'}
            
        # Extract vertices
        basis_block = obj.data.shape_keys.key_blocks[basis_name]
        num_verts = len(basis_block.data)
        
        # Optimization: Use a random subset if too many vertices
        sample_size = min(num_verts, 1000)
        np.random.seed(42) # FIX: Deterministic Seed
        indices = np.random.choice(num_verts, sample_size, replace=False)
        
        verts = np.zeros((sample_size, 3), dtype=np.float32)
        # foreach_get doesn't support indices, so we have to get all and slice, or loop.
        # Getting all is faster in Python.
        all_verts = np.zeros((num_verts * 3), dtype=np.float32)
        basis_block.data.foreach_get("co", all_verts)
        all_verts = all_verts.reshape((-1, 3))
        verts = all_verts[indices]
        
        # Calculate average nearest neighbor distance
        # Brute force for 1000 points is 1M comparisons, fast enough.
        d1 = verts[:, np.newaxis, :]
        d2 = verts[np.newaxis, :, :]
        dists = np.sqrt(np.sum((d1 - d2)**2, axis=2))
        
        # Mask diagonal (self-distance 0)
        np.fill_diagonal(dists, np.inf)
        
        min_dists = np.min(dists, axis=1)
        avg_dist = np.mean(min_dists)
        
        # Heuristic: Epsilon should be around the average spacing.
        # A bit larger to ensure overlap.
        estimated = avg_dist * 1.5
        
        props.epsilon = estimated
        self.report({'INFO'}, f"Estimated Epsilon: {estimated:.4f} (Avg Dist: {avg_dist:.4f})")
        
        return {'FINISHED'}

class OPENFITTER_OT_export_rbf_json(bpy.types.Operator):
    """Export RBF Field to JSON based on active object's shape keys"""
    bl_idname = "openfitter.export_rbf_json"
    bl_label = "Export RBF JSON"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def invoke(self, context, event):
        if not self.filepath:
            blend_filepath = context.blend_data.filepath
            if blend_filepath:
                self.filepath = os.path.splitext(blend_filepath)[0] + "_rbf.json"
            else:
                self.filepath = "rbf_data.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj = context.active_object
        props = context.scene.openfitter_rbf_props
        
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a Mesh")
            return {'CANCELLED'}
            
        if not obj.data.shape_keys:
            self.report({'ERROR'}, "Object has no shape keys")
            return {'CANCELLED'}
            
        basis_name = props.basis_shape_key
        target_name = props.target_shape_key
        
        if basis_name not in obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"Basis Shape Key '{basis_name}' not found")
            return {'CANCELLED'}
            
        if target_name not in obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"Target Shape Key '{target_name}' not found")
            return {'CANCELLED'}
            
        # --- Extract Data ---
        print(f"Extracting vertices from {obj.name}...")
        
        # We use the raw shape key coordinates (Local Space)
        # If the user wants World Space, they should apply transforms, but usually Shape Keys are local.
        # However, RBF is often used in World Space or Local Space depending on the system.
        # profile_converter.py uses whatever was in the .npz.
        # bone_exporter.py exported World Space.
        # If we want to deform "nearby meshes", we probably want World Space relative to the object root, 
        # or just Local Space if the other meshes are children.
        # Let's stick to Local Space of the object for now, as Shape Keys are local.
        # If the object has scale/rotation, it might matter.
        # But usually, we want the field relative to the mesh.
        
        basis_block = obj.data.shape_keys.key_blocks[basis_name]
        target_block = obj.data.shape_keys.key_blocks[target_name]
        
        num_verts = len(basis_block.data)
        basis_verts = np.zeros((num_verts, 3), dtype=np.float32)
        target_verts = np.zeros((num_verts, 3), dtype=np.float32)
        
        basis_block.data.foreach_get("co", basis_verts.ravel())
        target_block.data.foreach_get("co", target_verts.ravel())
        
        deltas = target_verts - basis_verts
        
        # --- Filter Points ---
        # 1. Remove points with very small movement (optimization)
        # Calculate magnitude of deltas
        mags = np.linalg.norm(deltas, axis=1)
        mask = mags > 0.0001
        
        centers = basis_verts[mask]
        deltas_filtered = deltas[mask]
        
        print(f"Points with delta > 0.0001: {len(centers)} / {num_verts}")
        
        if len(centers) == 0:
            self.report({'WARNING'}, "No significant deformation found between keys.")
            return {'CANCELLED'}

        # 2. X-Mirroring
        if props.enable_x_mirror:
            print("Applying X-Mirroring...")
            # Assuming X is the symmetry axis (standard in Blender)
            # We mirror points with X > epsilon
            mirror_mask = centers[:, 0] > 0.0001
            
            mirror_centers = centers[mirror_mask].copy()
            mirror_deltas = deltas_filtered[mirror_mask].copy()
            
            mirror_centers[:, 0] *= -1
            mirror_deltas[:, 0] *= -1 # Mirror the delta vector too
            
            centers = np.vstack([centers, mirror_centers])
            deltas_filtered = np.vstack([deltas_filtered, mirror_deltas])
            print(f"Points after mirroring: {len(centers)}")

        # 3. Downsampling & Distribution
        # Use Voxel Grid Sampling to ensure uniform distribution and determinism
        
        # Calculate bounding box to estimate density
        min_b = np.min(centers, axis=0)
        max_b = np.max(centers, axis=0)
        diag = np.linalg.norm(max_b - min_b)
        
        # Grid spacing: Use a fraction of Epsilon if available, or bounding box
        # If points are closer than epsilon/2, they are redundant and cause instability.
        # Let's use epsilon * 0.2 as a safe minimum spacing.
        grid_spacing = props.epsilon * 0.2
        if grid_spacing < 0.001: grid_spacing = 0.001
        
        print(f"Voxel Grid Filter: spacing {grid_spacing:.4f}")
        
        grid = {}
        for i, p in enumerate(centers):
            # Quantize
            key = (int(p[0]/grid_spacing), int(p[1]/grid_spacing), int(p[2]/grid_spacing))
            if key not in grid:
                grid[key] = i
        
        indices = list(grid.values())
        indices.sort() # Ensure deterministic order
        
        centers = centers[indices]
        deltas_filtered = deltas_filtered[indices]
        
        print(f"Points after Grid Filter: {len(centers)}")

        # Then Hard Limit
        max_points = props.max_points
        if len(centers) > max_points:
            print(f"Downsampling to {max_points}...")
            np.random.seed(42) # FIX: Deterministic Seed
            indices = np.random.choice(len(centers), max_points, replace=False)
            centers = centers[indices]
            deltas_filtered = deltas_filtered[indices]
            
        # --- RBF Fit ---
        print("Fitting RBF...")
        target_points = centers + deltas_filtered
        
        rbf = RBFCore(epsilon=props.epsilon, smoothing=props.smoothing)
        start_time = time.time()
        rbf.fit(centers, target_points)
        print(f"RBF Fit finished in {time.time() - start_time:.4f}s")
        
        # --- Export ---
        export_data = {
            "epsilon": float(rbf.epsilon),
            "centers": centers.tolist(),
            "weights": rbf.weights.tolist(),
            "poly_weights": rbf.polynomial_weights.tolist()
        }
        
        with open(self.filepath, 'w') as f:
            json.dump(export_data, f)
            
        self.report({'INFO'}, f"Saved RBF data to {self.filepath}")
        return {'FINISHED'}

# ------------------------------------------------------------------------
# UI Panel & Properties
# ------------------------------------------------------------------------

class OpenFitterRBFProperties(bpy.types.PropertyGroup):
    basis_shape_key: bpy.props.StringProperty(
        name="Basis Key",
        description="The base shape key (usually Basis)",
        default="Basis"
    )
    target_shape_key: bpy.props.StringProperty(
        name="Target Key",
        description="The shape key representing the deformation",
        default=""
    )
    epsilon: bpy.props.FloatProperty(
        name="Epsilon",
        description="RBF Kernel Epsilon (Width)",
        default=0.5,
        min=0.001
    )
    smoothing: bpy.props.FloatProperty(
        name="Smoothing",
        description="Regularization parameter. Higher values make the deformation smoother but less accurate to the original points.",
        default=0.01,
        min=0.0,
        precision=4
    )
    max_points: bpy.props.IntProperty(
        name="Max Points",
        description="Maximum number of control points (downsampled randomly)",
        default=500,
        min=10
    )
    enable_x_mirror: bpy.props.BoolProperty(
        name="X Mirror",
        description="Mirror points across X axis (useful for symmetric meshes)",
        default=False
    )

class OPENFITTER_PT_rbf_export(bpy.types.Panel):
    bl_label = "RBF Field Export"
    bl_idname = "OPENFITTER_PT_rbf_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OpenFitter"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.openfitter_rbf_props
        obj = context.active_object
        
        layout.label(text="Active Mesh: " + (obj.name if obj else "None"))
        
        if obj and obj.type == 'MESH' and obj.data.shape_keys:
            layout.prop_search(props, "basis_shape_key", obj.data.shape_keys, "key_blocks", text="Basis")
            layout.prop_search(props, "target_shape_key", obj.data.shape_keys, "key_blocks", text="Target")
            
            layout.separator()
            
            row = layout.row(align=True)
            row.prop(props, "epsilon")
            row.operator("openfitter.estimate_epsilon", text="", icon='DRIVER')
            
            layout.prop(props, "smoothing")
            layout.prop(props, "max_points")
            layout.prop(props, "enable_x_mirror")
            
            layout.separator()
            layout.operator("openfitter.export_rbf_json", icon='EXPORT')
        else:
            layout.label(text="Select a Mesh with Shape Keys", icon='INFO')

# ------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------

classes = (
    OpenFitterRBFProperties,
    OPENFITTER_OT_estimate_epsilon,
    OPENFITTER_OT_export_rbf_json,
    OPENFITTER_PT_rbf_export,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.openfitter_rbf_props = bpy.props.PointerProperty(type=OpenFitterRBFProperties)

def unregister():
    del bpy.types.Scene.openfitter_rbf_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
