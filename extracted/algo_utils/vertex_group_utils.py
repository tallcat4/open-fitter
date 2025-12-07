import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from blender_utils.mesh_utils import get_evaluated_mesh
from scipy.spatial import cKDTree
import bpy
import numpy as np
import os
import sys
import time

# Merged from get_vertex_groups_and_weights.py

def get_vertex_groups_and_weights(mesh_obj, vertex_index):
    """頂点の所属する頂点グループとウェイトを取得"""
    groups = {}
    vertex = mesh_obj.data.vertices[vertex_index]

    for g in vertex.groups:
        group_name = mesh_obj.vertex_groups[g.group].name
        groups[group_name] = g.weight
        
    return groups

# Merged from remove_empty_vertex_groups.py

def remove_empty_vertex_groups(mesh_obj: bpy.types.Object) -> None:
    """Remove vertex groups that are empty or have zero weights for all vertices."""
    if not mesh_obj.type == 'MESH' or not mesh_obj.vertex_groups:
        return
        
    groups_to_remove = []
    for vgroup in mesh_obj.vertex_groups:
        has_weights = False
        for vert in mesh_obj.data.vertices:
            weight_index = vgroup.index
            for g in vert.groups:
                if g.group == weight_index and g.weight > 0.0005:
                    has_weights = True
                    break
            if has_weights:
                break
        if not has_weights:
            groups_to_remove.append(vgroup.name)

    for group_name in groups_to_remove:
        if group_name in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.remove(mesh_obj.vertex_groups[group_name])
            print(f"Removed empty vertex group: {group_name}")

# Merged from merge_vertex_group_weights.py

def merge_vertex_group_weights(mesh_obj: bpy.types.Object, source_group_name: str, target_group_name: str) -> None:
    """
    指定された頂点グループのウェイトを別のグループに統合する
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        source_group_name: 統合元のグループ名
        target_group_name: 統合先のグループ名
    """
    if source_group_name not in mesh_obj.vertex_groups or target_group_name not in mesh_obj.vertex_groups:
        return
        
    source_group = mesh_obj.vertex_groups[source_group_name]
    target_group = mesh_obj.vertex_groups[target_group_name]
    
    # 各頂点のウェイトを統合
    for vert in mesh_obj.data.vertices:
        source_weight = 0
        for group in vert.groups:
            if group.group == source_group.index:
                source_weight = group.weight
                break
        
        if source_weight > 0:
            # ターゲットグループにウェイトを加算
            target_group.add([vert.index], source_weight, 'ADD')

# Merged from check_uniform_weights.py

def check_uniform_weights(mesh_obj, component_verts, armature_obj):
    """
    指定されたコンポーネント内の頂点が一様なボーンウェイトを持つか確認する
    
    Parameters:
        mesh_obj: メッシュオブジェクト
        component_verts: コンポーネントに含まれる頂点インデックスのセット
        armature_obj: ウェイト確認対象のアーマチュア
        
    Returns:
        (bool, dict): 一様なウェイトを持つかどうかのフラグと、ボーン名:ウェイト値の辞書
    """
    if not armature_obj:
        return False, {}
    
    # アーマチュアの全ボーン名を取得
    target_bones = {bone.name for bone in armature_obj.data.bones}
    
    # 最初の頂点のウェイトパターンを取得
    first_vert_idx = next(iter(component_verts))
    first_weights = {}
    
    for group in mesh_obj.vertex_groups:
        if group.name in target_bones:
            weight = 0.0
            try:
                for g in mesh_obj.data.vertices[first_vert_idx].groups:
                    if g.group == group.index:
                        weight = g.weight
                        break
            except RuntimeError:
                pass
            
            if weight > 0:
                first_weights[group.name] = weight
    
    # 他の全頂点が同じウェイトパターンを持つか確認
    for vert_idx in component_verts:
        if vert_idx == first_vert_idx:
            continue
        
        for bone_name, weight in first_weights.items():
            group = mesh_obj.vertex_groups.get(bone_name)
            if not group:
                return False, {}
            
            current_weight = 0.0
            try:
                for g in mesh_obj.data.vertices[vert_idx].groups:
                    if g.group == group.index:
                        current_weight = g.weight
                        break
            except RuntimeError:
                pass
            
            # ウェイト値が異なる場合は一様でない
            if abs(current_weight - weight) >= 0.001:
                return False, {}
        
        # 追加のボーングループがないか確認
        for group in mesh_obj.vertex_groups:
            if group.name in target_bones and group.name not in first_weights:
                weight = 0.0
                try:
                    for g in mesh_obj.data.vertices[vert_idx].groups:
                        if g.group == group.index:
                            weight = g.weight
                            break
                except RuntimeError:
                    pass
                
                if weight > 0:
                    return False, {}
    
    return True, first_weights

# Merged from apply_max_filter_to_vertex_group.py

def apply_max_filter_to_vertex_group(cloth_obj, vertex_group_name, filter_radius=0.02, filter_mask=None):
    """
    頂点グループに対してMaxフィルターを適用します
    各頂点から一定距離内にある頂点のウェイトの最大値を取得し、その値を新しいウェイトとして設定します
    
    Parameters:
    cloth_obj (obj): 衣装メッシュのオブジェクト
    vertex_group_name (str): 対象の頂点グループ名
    filter_radius (float): フィルター適用半径
    filter_mask (obj): フィルタリングに使用する頂点グループ
    """
    start_time = time.time()
    
    if vertex_group_name not in cloth_obj.vertex_groups:
        print(f"エラー: 頂点グループ '{vertex_group_name}' が見つかりません")
        return
    
    vertex_group = cloth_obj.vertex_groups[vertex_group_name]
    
    # 現在のモードを保存
    current_mode = bpy.context.object.mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # モディファイア適用後のメッシュを取得
    cloth_bm = get_evaluated_mesh(cloth_obj)
    cloth_bm.verts.ensure_lookup_table()
    
    # 頂点座標をnumpy配列に変換
    vertex_coords = np.array([v.co for v in cloth_bm.verts])
    num_vertices = len(vertex_coords)
    
    # 現在のウェイト値を取得
    current_weights = np.zeros(num_vertices, dtype=np.float32)
    for i, vertex in enumerate(cloth_bm.verts):
        # 頂点グループのウェイトを取得
        weight = 0.0
        for group in cloth_obj.data.vertices[i].groups:
            if group.group == vertex_group.index:
                weight = group.weight
                break
        current_weights[i] = weight
    
    # cKDTreeを使用して近傍検索を効率化
    kdtree = cKDTree(vertex_coords)
    
    # 新しいウェイト配列を初期化
    new_weights = np.copy(current_weights)
    
    print(f"  Maxフィルター処理開始 (半径: {filter_radius})")
    
    # 各頂点に対してMaxフィルターを適用
    for i in range(num_vertices):
        # 一定半径内の近傍頂点のインデックスを取得
        neighbor_indices = kdtree.query_ball_point(vertex_coords[i], filter_radius)
        
        if neighbor_indices:
            # 近傍頂点のウェイトの最大値を取得
            neighbor_weights = current_weights[neighbor_indices]
            max_weight = np.max(neighbor_weights)
            if filter_mask is not None:
                new_weights[i] = filter_mask[i] * max_weight + (1 - filter_mask[i]) * current_weights[i]
            else:
                new_weights[i] = max_weight
    
    # 新しいウェイトを頂点グループに適用
    for i in range(num_vertices):
        vertex_group.add([i], new_weights[i], 'REPLACE')
    
    # BMeshをクリーンアップ
    cloth_bm.free()
    
    # 元のモードに戻す
    bpy.ops.object.mode_set(mode=current_mode)
    
    total_time = time.time() - start_time
    print(f"  Maxフィルター完了: {total_time:.2f}秒")

# Merged from apply_min_filter_to_vertex_group.py

def apply_min_filter_to_vertex_group(cloth_obj, vertex_group_name, filter_radius=0.02, filter_mask=None):
    """
    頂点グループに対してMinフィルターを適用します
    各頂点から一定距離内にある頂点のウェイトの最小値を取得し、その値を新しいウェイトとして設定します
    
    Parameters:
    cloth_obj (obj): 衣装メッシュのオブジェクト
    vertex_group_name (str): 対象の頂点グループ名
    filter_radius (float): フィルター適用半径
    filter_mask (obj): フィルタリングに使用する頂点グループ
    """
    start_time = time.time()
    
    if vertex_group_name not in cloth_obj.vertex_groups:
        print(f"エラー: 頂点グループ '{vertex_group_name}' が見つかりません")
        return
    
    vertex_group = cloth_obj.vertex_groups[vertex_group_name]
    
    # 現在のモードを保存
    current_mode = bpy.context.object.mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # モディファイア適用後のメッシュを取得
    cloth_bm = get_evaluated_mesh(cloth_obj)
    cloth_bm.verts.ensure_lookup_table()
    
    # 頂点座標をnumpy配列に変換
    vertex_coords = np.array([v.co for v in cloth_bm.verts])
    num_vertices = len(vertex_coords)
    
    # 現在のウェイト値を取得
    current_weights = np.zeros(num_vertices, dtype=np.float32)
    for i, vertex in enumerate(cloth_bm.verts):
        # 頂点グループのウェイトを取得
        weight = 0.0
        for group in cloth_obj.data.vertices[i].groups:
            if group.group == vertex_group.index:
                weight = group.weight
                break
        current_weights[i] = weight
    
    # cKDTreeを使用して近傍検索を効率化
    kdtree = cKDTree(vertex_coords)
    
    # 新しいウェイト配列を初期化
    new_weights = np.copy(current_weights)
    
    print(f"  Minフィルター処理開始 (半径: {filter_radius})")
    
    # 各頂点に対してMinフィルターを適用
    for i in range(num_vertices):
        # 一定半径内の近傍頂点のインデックスを取得
        neighbor_indices = kdtree.query_ball_point(vertex_coords[i], filter_radius)
        
        if neighbor_indices:
            # 近傍頂点のウェイトの最小値を取得
            neighbor_weights = current_weights[neighbor_indices]
            min_weight = np.min(neighbor_weights)
            if filter_mask is not None:
                new_weights[i] = filter_mask[i] * min_weight + (1 - filter_mask[i]) * current_weights[i]
            else:
                new_weights[i] = min_weight
    
    # 新しいウェイトを頂点グループに適用
    for i in range(num_vertices):
        vertex_group.add([i], new_weights[i], 'REPLACE')
    
    # BMeshをクリーンアップ
    cloth_bm.free()
    
    # 元のモードに戻す
    bpy.ops.object.mode_set(mode=current_mode)
    
    total_time = time.time() - start_time
    print(f"  Minフィルター完了: {total_time:.2f}秒")

# Merged from apply_smoothing_to_vertex_group.py

def apply_smoothing_to_vertex_group(cloth_obj, vertex_group_name, smoothing_radius=0.02, iteration=1, use_distance_weighting=True, gaussian_falloff=True, neighbors_cache=None):
    """
    指定された頂点グループに対してスムージング処理を適用します
    距離による重み付きスムージングを使用して、頂点密度の偏りに対して頑健な結果を得ます
    
    Parameters:
    cloth_obj (obj): 衣装メッシュのオブジェクト
    vertex_group_name (str): 対象の頂点グループ名
    smoothing_radius (float): スムージング適用半径
    use_distance_weighting (bool): 距離による重み付けを使用するかどうか
    gaussian_falloff (bool): ガウシアン減衰を使用するかどうか
    """
    start_time = time.time()
    
    if vertex_group_name not in cloth_obj.vertex_groups:
        print(f"エラー: 頂点グループ '{vertex_group_name}' が見つかりません")
        return
    
    vertex_group = cloth_obj.vertex_groups[vertex_group_name]
    
    # 現在のモードを保存
    current_mode = bpy.context.object.mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # モディファイア適用後のメッシュを取得
    cloth_bm = get_evaluated_mesh(cloth_obj)
    cloth_bm.verts.ensure_lookup_table()
    
    # 頂点座標をnumpy配列に変換
    vertex_coords = np.array([v.co for v in cloth_bm.verts])
    num_vertices = len(vertex_coords)
    
    # 現在のウェイト値を取得
    current_weights = np.zeros(num_vertices, dtype=np.float32)
    for i, vertex in enumerate(cloth_obj.data.vertices):
        for group in vertex.groups:
            if group.group == vertex_group.index:
                current_weights[i] = group.weight
                break
    
    # cKDTreeを使用して近傍検索を効率化
    kdtree = cKDTree(vertex_coords)
    
    # スムージング済みウェイト配列を初期化
    smoothed_weights = np.copy(current_weights)
    
    print(f"  スムージング処理開始 (半径: {smoothing_radius}, 距離重み付け: {use_distance_weighting}, ガウシアン減衰: {gaussian_falloff})")
    
    # ガウシアン関数のシグマ値（半径の1/3程度が適切）
    sigma = smoothing_radius / 3.0
    
    # 最初のイテレーションでneighbor_indicesをキャッシュ
    if neighbors_cache is None:
        neighbors_cache = {}
    
    for iteration_idx in range(iteration):
        # 各頂点に対してスムージングを適用
        for i in range(num_vertices):
            # 最初のイテレーションでneighbor_indicesを計算・キャッシュ、二回目以降はキャッシュを使用
            if iteration_idx == 0:
                if i not in neighbors_cache:
                    neighbor_indices = kdtree.query_ball_point(vertex_coords[i], smoothing_radius)
                    neighbors_cache[i] = neighbor_indices
                else:
                    neighbor_indices = neighbors_cache[i]
            else:
                neighbor_indices = neighbors_cache[i]
            
            if len(neighbor_indices) > 1:  # 自分自身以外の近傍が存在する場合
                # 近傍頂点への距離を計算
                neighbor_coords = vertex_coords[neighbor_indices]
                distances = np.linalg.norm(neighbor_coords - vertex_coords[i], axis=1)
                
                # 近傍頂点のウェイト値を取得
                neighbor_weights = current_weights[neighbor_indices]
                
                if use_distance_weighting:
                    if gaussian_falloff:
                        # ガウシアン減衰による重み計算
                        weights = np.exp(-(distances ** 2) / (2 * sigma ** 2))
                    else:
                        # 線形減衰による重み計算
                        weights = np.maximum(0, 1.0 - distances / smoothing_radius)
                    
                    # 自分自身の重みを少し強めに設定（オリジナル値の保持）
                    # self_index = np.where(distances == 0)[0]
                    # if len(self_index) > 0:
                    #     weights[self_index[0]] *= 2.0
                    
                    # 重み付き平均を計算
                    if np.sum(weights) > 0.001:
                        smoothed_weights[i] = np.sum(neighbor_weights * weights) / np.sum(weights)
                    else:
                        smoothed_weights[i] = current_weights[i]
                else:
                    # 従来の単純平均
                    smoothed_weights[i] = np.mean(neighbor_weights)
            else:
                # 近傍頂点が自分だけの場合は元の値を保持
                smoothed_weights[i] = current_weights[i]
        current_weights = np.copy(smoothed_weights)
    
    # 新しいウェイトを頂点グループに適用
    for i in range(num_vertices):
        vertex_group.add([i], smoothed_weights[i], 'REPLACE')
    
    # BMeshをクリーンアップ
    cloth_bm.free()
    
    # 元のモードに戻す
    bpy.ops.object.mode_set(mode=current_mode)
    
    total_time = time.time() - start_time
    print(f"  スムージング完了: {total_time:.2f}秒")

    return neighbors_cache

# Merged from custom_max_vertex_group_numpy.py

def custom_max_vertex_group_numpy(obj, group_name, neighbors_info, offsets, num_verts,
                                  repeat=3, weight_factor=1.0):
    """
    NumPy を用いたカスタムスムージング (MAXベース) の高速実装
    
    Parameters:
        obj: 対象のメッシュオブジェクト
        group_name: スムージング対象の頂点グループ名
        neighbors_info: create_vertex_neighbors_array で作成した近接頂点情報フラット配列
        offsets: create_vertex_neighbors_array で作成した頂点ごとのオフセット
        num_verts: 頂点数
        repeat: スムージングの繰り返し回数
        weight_factor: 周辺頂点からの最大値に掛ける係数
    """
    if group_name not in obj.vertex_groups:
        print(f"頂点グループ '{group_name}' が見つかりません")
        return
    
    group_index = obj.vertex_groups[group_name].index
    
    # 頂点ウェイトを NumPy 配列で取得
    current_weights = np.zeros(num_verts, dtype=np.float64)
    for v in obj.data.vertices:
        w = 0.0
        for g in v.groups:
            if g.group == group_index:
                w = g.weight
                break
        current_weights[v.index] = w
    
    # スムージングを繰り返し
    for _ in range(repeat):
        new_weights = np.copy(current_weights)
        
        # 各頂点ごとに近接頂点の (weight * factor) の最大値を取る
        for vert_idx in range(num_verts):
            start = offsets[vert_idx]
            end = offsets[vert_idx+1]
            if start == end:
                # 近接頂点がない場合
                continue
            
            # neighbors_info[start:end, 0] -> neighbor_idx (float なので int にキャスト)
            neighbor_idx = neighbors_info[start:end, 0].astype(np.int64)
            dist_factors = neighbors_info[start:end, 1]  # weight_dist_factor
            
            # 周囲頂点のウェイトに距離係数を掛け合わせ、その最大値を求める
            local_max = np.max(current_weights[neighbor_idx] * dist_factors)
            
            # 現在ウェイトと比較して大きい方を適用
            new_weights[vert_idx] = max(new_weights[vert_idx], local_max * weight_factor)
        
        current_weights = new_weights
    
    # 計算結果を頂点グループに反映 (まとめて書き戻し)
    vg = obj.vertex_groups[group_name]
    for vert_idx in range(num_verts):
        w = current_weights[vert_idx]
        if w > 1.0:
            w = 1.0
        vg.add([vert_idx], float(w), 'REPLACE')

# Merged from process_humanoid_vertex_groups.py

def process_humanoid_vertex_groups(mesh_obj: bpy.types.Object, clothing_armature: bpy.types.Object, base_avatar_data: dict, clothing_avatar_data: dict) -> None:
    """
    衣装メッシュのHumanoidボーン頂点グループを処理
    - Humanoidボーン名を素体アバターデータのものに変換
    - 補助ボーンの頂点グループを追加
    - 条件を満たす場合はOptional Humanoidボーンの頂点グループを追加
    """

    # Get bone names from clothing armature
    clothing_bone_names = set(bone.name for bone in clothing_armature.data.bones)
    
    # Humanoidボーン名のマッピングを作成
    base_humanoid_to_bone = {bone_map["humanoidBoneName"]: bone_map["boneName"] 
                        for bone_map in base_avatar_data["humanoidBones"]}
    clothing_humanoid_to_bone = {bone_map["humanoidBoneName"]: bone_map["boneName"] 
                           for bone_map in clothing_avatar_data["humanoidBones"]}
    clothing_bone_to_humanoid = {bone_map["boneName"]: bone_map["humanoidBoneName"] 
                           for bone_map in clothing_avatar_data["humanoidBones"]}
    
    # 補助ボーンのマッピングを作成
    auxiliary_bones = {}
    for aux_set in base_avatar_data.get("auxiliaryBones", []):
        humanoid_bone = aux_set["humanoidBoneName"]
        if humanoid_bone in base_humanoid_to_bone:
            auxiliary_bones[base_humanoid_to_bone[humanoid_bone]] = aux_set["auxiliaryBones"]
    
    # 既存の頂点グループ名を取得
    existing_groups = set(vg.name for vg in mesh_obj.vertex_groups)
    
    # 名前変更が必要なグループを特定
    groups_to_rename = {}
    for group in mesh_obj.vertex_groups:
        if group.name in clothing_bone_to_humanoid:
            humanoid_name = clothing_bone_to_humanoid[group.name]
            if humanoid_name in base_humanoid_to_bone:
                base_bone_name = base_humanoid_to_bone[humanoid_name]
                groups_to_rename[group.name] = base_bone_name
    
    # グループ名を変更
    for old_name, new_name in groups_to_rename.items():
        if old_name in mesh_obj.vertex_groups:
            group = mesh_obj.vertex_groups[old_name]
            group_index = group.index
            # 頂点ごとのウェイトを保存
            weights = {}
            for vert in mesh_obj.data.vertices:
                for g in vert.groups:
                    if g.group == group_index:
                        weights[vert.index] = g.weight
                        break
            
            # グループ名を変更
            group.name = new_name
            
            # 補助ボーンの頂点グループを追加
            if new_name in auxiliary_bones:
                # 補助ボーンの頂点グループを作成
                for aux_bone in auxiliary_bones[new_name]:
                    if aux_bone not in existing_groups:
                        mesh_obj.vertex_groups.new(name=aux_bone)
    
    existing_groups = set(vg.name for vg in mesh_obj.vertex_groups)

    breast_bones_dont_exist = 'LeftBreast' not in clothing_humanoid_to_bone and 'RightBreast' not in clothing_humanoid_to_bone
    
    # Process each humanoid bone from base avatar
    for humanoid_name, bone_name in base_humanoid_to_bone.items():
        # Skip if bone exists in clothing armature
        if bone_name in existing_groups:
            continue

        should_add_optional_humanoid_bone = False
        
        # Condition 1: Chest exists in clothing, UpperChest missing in clothing but exists in base
        if (humanoid_name == "UpperChest" and 
            "Chest" in clothing_humanoid_to_bone and 
            base_humanoid_to_bone["Chest"] in existing_groups and
            "UpperChest" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 2: LeftLowerLeg exists in clothing, LeftFoot missing in clothing but exists in base
        elif (humanoid_name == "LeftFoot" and 
                "LeftLowerLeg" in clothing_humanoid_to_bone and 
                base_humanoid_to_bone["LeftLowerLeg"] in existing_groups and
                "LeftFoot" not in clothing_humanoid_to_bone and
                "LeftFoot" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 2: RightLowerLeg exists in clothing, RightFoot missing in clothing but exists in base
        elif (humanoid_name == "RightFoot" and 
                "RightLowerLeg" in clothing_humanoid_to_bone and 
                base_humanoid_to_bone["RightLowerLeg"] in existing_groups and
                "RightFoot" not in clothing_humanoid_to_bone and
                "RightFoot" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 3: LeftLowerLeg or LeftFoot exists in clothing, LeftToe missing in clothing but exists in base
        elif (humanoid_name == "LeftToe" and 
                (("LeftLowerLeg" in clothing_humanoid_to_bone and base_humanoid_to_bone["LeftLowerLeg"] in existing_groups) or
                ("LeftFoot" in clothing_humanoid_to_bone and base_humanoid_to_bone["LeftFoot"] in existing_groups)) and
                "LeftToe" not in clothing_humanoid_to_bone and
                "LeftToe" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 3: RightLowerLeg or RightFoot exists in clothing, RightToe missing in clothing but exists in base
        elif (humanoid_name == "RightToe" and 
                (("RightLowerLeg" in clothing_humanoid_to_bone and base_humanoid_to_bone["RightLowerLeg"] in existing_groups) or
                ("RightFoot" in clothing_humanoid_to_bone and base_humanoid_to_bone["RightFoot"] in existing_groups)) and
                "RightToe" not in clothing_humanoid_to_bone and
                "RightToe" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 4: LeftShoulder exists in clothing, LeftUpperArm exists in base but not in clothing
        elif (humanoid_name == "LeftUpperArm" and 
                "LeftShoulder" in clothing_humanoid_to_bone and 
                base_humanoid_to_bone["LeftShoulder"] in existing_groups and
                "LeftUpperArm" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 4: RightShoulder exists in clothing, RightUpperArm exists in base but not in clothing
        elif (humanoid_name == "RightUpperArm" and 
                "RightShoulder" in clothing_humanoid_to_bone and 
                base_humanoid_to_bone["RightShoulder"] in existing_groups and
                "RightUpperArm" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 5: LeftBreast exists in clothing, breast bones don't exist in clothing, Chest or UpperChest exists in base
        elif (humanoid_name == "LeftBreast" and breast_bones_dont_exist and
                (base_humanoid_to_bone["Chest"] in existing_groups or base_humanoid_to_bone["UpperChest"] in existing_groups) and
                "LeftBreast" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        # Condition 5: RightBreast exists in clothing, breast bones don't exist in clothing, Chest or UpperChest exists in base
        elif (humanoid_name == "RightBreast" and breast_bones_dont_exist and
                (base_humanoid_to_bone["Chest"] in existing_groups or base_humanoid_to_bone["UpperChest"] in existing_groups) and
                "RightBreast" in base_humanoid_to_bone):
            should_add_optional_humanoid_bone = True
        
        if should_add_optional_humanoid_bone:
            print(f"Adding optional humanoid bone group: {humanoid_name} ({bone_name})")
            if bone_name not in existing_groups:
                mesh_obj.vertex_groups.new(name=bone_name)
            else:
                print(f"Optional humanoid bone group already exists: {bone_name}")
            # 補助ボーンの頂点グループを追加
            if bone_name in auxiliary_bones:
                # 補助ボーンの頂点グループを作成
                for aux_bone in auxiliary_bones[bone_name]:
                    if aux_bone not in existing_groups:
                        mesh_obj.vertex_groups.new(name=aux_bone)