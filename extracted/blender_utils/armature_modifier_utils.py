"""
Armatureモディファイア関連のユーティリティ

- set_armature_modifier_target_armature: ターゲットアーマチュアを設定
- set_armature_modifier_visibility: 表示設定
- store_armature_modifier_settings: 設定を保存
- restore_armature_modifier: 設定を復元
"""


def set_armature_modifier_target_armature(obj, target_armature):
    """Armatureモディファイアのターゲットアーマチュアを設定"""
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE':
            modifier.object = target_armature


def set_armature_modifier_visibility(obj, show_viewport, show_render):
    """Armatureモディファイアの表示を設定"""
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE':
            modifier.show_viewport = show_viewport
            modifier.show_render = show_render


def store_armature_modifier_settings(obj):
    """Armatureモディファイアの設定を保存"""
    armature_settings = []
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE':
            settings = {
                'name': modifier.name,
                'object': modifier.object,
                'vertex_group': modifier.vertex_group,
                'invert_vertex_group': modifier.invert_vertex_group,
                'use_vertex_groups': modifier.use_vertex_groups,
                'use_bone_envelopes': modifier.use_bone_envelopes,
                'use_deform_preserve_volume': modifier.use_deform_preserve_volume,
                'use_multi_modifier': modifier.use_multi_modifier,
                'show_viewport': modifier.show_viewport,
                'show_render': modifier.show_render,
            }
            armature_settings.append(settings)
    return armature_settings


def restore_armature_modifier(obj, settings):
    """Armatureモディファイアを復元"""
    for modifier_settings in settings:
        modifier = obj.modifiers.new(name=modifier_settings['name'], type='ARMATURE')
        modifier.object = modifier_settings['object']
        modifier.vertex_group = modifier_settings['vertex_group']
        modifier.invert_vertex_group = modifier_settings['invert_vertex_group']
        modifier.use_vertex_groups = modifier_settings['use_vertex_groups']
        modifier.use_bone_envelopes = modifier_settings['use_bone_envelopes']
        modifier.use_deform_preserve_volume = modifier_settings['use_deform_preserve_volume']
        modifier.use_multi_modifier = modifier_settings['use_multi_modifier']
        modifier.show_viewport = modifier_settings['show_viewport']
        modifier.show_render = modifier_settings['show_render']
