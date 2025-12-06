from dataclasses import dataclass, field


@dataclass
class ProcessingContext:
    base_mesh: object = None
    base_armature: object = None
    base_avatar_data: dict = None
    clothing_meshes: list = None
    clothing_armature: object = None
    clothing_avatar_data: dict = None
    cloth_metadata: dict = None
    vertex_index_mapping: dict = None
    use_subdivision: bool = None
    use_triangulation: bool = None
    propagated_groups_map: dict = field(default_factory=dict)
    original_humanoid_bones: list = None
    original_auxiliary_bones: list = None
    is_A_pose: bool = False
    blend_shape_labels: list = None
    base_weights_time: float = None
    cycle1_end_time: float = None
    cycle2_post_end: float = None
    time_module: object = None
    start_time: float = None
