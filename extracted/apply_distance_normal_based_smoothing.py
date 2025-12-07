import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import math
import time

import bpy
import mathutils
import numpy as np
from algo_utils.vertex_group_utils import apply_max_filter_to_vertex_group
from algo_utils.vertex_group_utils import apply_smoothing_to_vertex_group
from blender_utils.clear_mesh_cache import clear_mesh_cache
from blender_utils.get_evaluated_mesh import get_evaluated_mesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy.spatial import cKDTree


def apply_distance_normal_based_smoothing(body_obj, cloth_obj, distance_min=0.0, distance_max=0.1, angle_min=0.0, angle_max=30.0, new_group_name="InpaintMask", normal_radius=0.01, smoothing_mask_groups=None, target_vertex_groups=None, smoothing_radius=0.02, mask_group_name=None):
    """
    素体メッシュからの距離と法線角度に基づいて衣装メッシュに頂点グループを作成し、スムージングを適用します
    
    Parameters:
    body_obj (obj): 素体メッシュのオブジェクト名
    cloth_obj (obj): 衣装メッシュのオブジェクト名
    distance_min (float): 距離の最小値、この値以下では ウェイト0.0
    distance_max (float): 距離の最大値、この値以上では ウェイト1.0
    angle_min (float): 角度の最小値、この値以下では ウェイト0.0（度単位）
    angle_max (float): 角度の最大値、この値以上では ウェイト1.0（度単位）
    new_group_name (str): 作成する頂点グループ名
    normal_radius (float): 法線の加重平均を計算する際に考慮する球体の半径
    smoothing_mask_groups (list): スムージングマスクとして適用する頂点グループ名のリスト
    target_vertex_groups (list): スムージング対象の頂点グループ名のリスト
    smoothing_radius (float): スムージングに使用する距離
    mask_group_name (str): スムージング処理結果の合成強度に対するマスク頂点グループの名前
    """
    start_time = time.time()
    
    if not body_obj or not cloth_obj:
        print("指定されたオブジェクトが見つかりません")
        return
    
    # 現在のモードを保存
    current_mode = bpy.context.object.mode
    # オブジェクトモードに切り替え
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 衣装オブジェクトを選択してアクティブに
    bpy.ops.object.select_all(action='DESELECT')
    cloth_obj.select_set(True)
    bpy.context.view_layer.objects.active = cloth_obj
    
    # BVHツリーを作成（高速な最近傍点検索のため）
    # モディファイア適用後のターゲットメッシュを取得
    body_bm_time_start = time.time()
    body_bm = get_evaluated_mesh(body_obj)
    body_bm.faces.ensure_lookup_table()
    body_bm_time = time.time() - body_bm_time_start
    print(f"  Body BMesh作成: {body_bm_time:.2f}秒")

    # ターゲットメッシュのBVHツリーを作成
    bvh_time_start = time.time()
    bvh_tree = BVHTree.FromBMesh(body_bm)
    bvh_time = time.time() - bvh_time_start
    print(f"  BVHツリー作成: {bvh_time:.2f}秒")
    
    # 頂点グループがまだ存在しない場合は作成
    if new_group_name not in cloth_obj.vertex_groups:
        cloth_obj.vertex_groups.new(name=new_group_name)
    vertex_group = cloth_obj.vertex_groups[new_group_name]
    
    # 角度の最小値・最大値をラジアンに変換
    angle_min_rad = math.radians(angle_min)
    angle_max_rad = math.radians(angle_max)
    
    # モディファイア適用後のソースメッシュを取得
    cloth_bm_time_start = time.time()
    cloth_bm = get_evaluated_mesh(cloth_obj)
    cloth_bm.verts.ensure_lookup_table()
    cloth_bm.faces.ensure_lookup_table()
    cloth_bm_time = time.time() - cloth_bm_time_start
    print(f"  Cloth BMesh作成: {cloth_bm_time:.2f}秒")
    
    # トランスフォームマトリックスをキャッシュ（繰り返しの計算を避けるため）
    body_normal_matrix = body_obj.matrix_world.inverted().transposed()
    cloth_normal_matrix = cloth_obj.matrix_world.inverted().transposed()
    
    # 修正した法線を格納する辞書
    adjusted_normals_time_start = time.time()
    adjusted_normals = {}
    
    # 衣装メッシュの各頂点の法線処理（逆転の必要があるかチェック）
    for i, vertex in enumerate(cloth_bm.verts):
        # ワールド座標系での頂点位置と法線
        cloth_vert_world = vertex.co
        original_normal_world = (cloth_normal_matrix @ Vector((vertex.normal[0], vertex.normal[1], vertex.normal[2], 0))).xyz.normalized()
        
        # 素体メッシュ上の最近傍面を検索
        nearest_result = bvh_tree.find_nearest(cloth_vert_world)
        if nearest_result:
            # BVHTree.find_nearest() は (co, normal, index, distance) を返す
            nearest_point, nearest_normal, nearest_face_index, _ = nearest_result
            
            # 最近傍面を取得
            face = body_bm.faces[nearest_face_index]
            face_normal = face.normal
            
            # 面の法線をワールド座標系に変換
            face_normal_world = (body_normal_matrix @ Vector((face_normal[0], face_normal[1], face_normal[2], 0))).xyz.normalized()
            
            # 内積が負の場合、法線を反転
            dot_product = original_normal_world.dot(face_normal_world)
            if dot_product < 0:
                adjusted_normal = -original_normal_world
            else:
                adjusted_normal = original_normal_world
                 
            # 調整済み法線を辞書に保存
            adjusted_normals[i] = adjusted_normal
        else:
            # 最近傍点が見つからない場合は元の法線を使用
            adjusted_normals[i] = original_normal_world
    adjusted_normals_time = time.time() - adjusted_normals_time_start
    print(f"  法線調整: {adjusted_normals_time:.2f}秒")
    
    # 面の中心点と面積を事前計算してキャッシュ
    face_cache_time_start = time.time()
    face_centers = []
    face_areas = {}
    face_adjusted_normals = {}
    face_indices = []
    
    for face in cloth_bm.faces:
        # 面の中心点を計算
        center = Vector((0, 0, 0))
        for v in face.verts:
            center += v.co
        center /= len(face.verts)
        face_centers.append(center)
        face_indices.append(face.index)
        
        # 面積を計算
        face_areas[face.index] = face.calc_area()
        
        # 面の調整済み法線を計算
        face_normal = Vector((0, 0, 0))
        for v in face.verts:
            face_normal += adjusted_normals[v.index]
        face_adjusted_normals[face.index] = face_normal.normalized()
    face_cache_time = time.time() - face_cache_time_start
    print(f"  面キャッシュ作成: {face_cache_time:.2f}秒")
    
    # 衣装メッシュの面に対してKDTreeを構築
    kdtree_time_start = time.time()
    # size = len(cloth_bm.faces)
    # kd = mathutils.kdtree.KDTree(size)
    
    # for face_index, center in face_centers.items():
    #     kd.insert(center, face_index)
    
    # kd.balance()
    kd = cKDTree(face_centers)
    kdtree_time = time.time() - kdtree_time_start
    print(f"  KDTree構築: {kdtree_time:.2f}秒")
    
    # 各頂点の法線を近傍面の法線の加重平均で更新
    normal_avg_time_start = time.time()
    for i, vertex in enumerate(cloth_bm.verts):
        # 一定の半径内の面を検索
        co = vertex.co
        weighted_normal = Vector((0, 0, 0))
        total_weight = 0
        
        # KDTreeを使用して近傍の面を効率的に検索
        for index in kd.query_ball_point(co, normal_radius):
            # 距離に応じた重みを計算（距離が近いほど影響が大きい）
            face_index = face_indices[index]
            area = face_areas[face_index]
            dist = (co - face_centers[index]).length
            # 距離に基づく減衰係数
            distance_factor = 1.0 - (dist / normal_radius) if dist < normal_radius else 0.0
            weight = area * distance_factor
            
            weighted_normal += face_adjusted_normals[face_index] * weight
            total_weight += weight
        
        # 重みの合計が0でない場合は正規化
        if total_weight > 0:
            weighted_normal /= total_weight
            weighted_normal.normalize()
            # 調整済み法線を更新
            adjusted_normals[i] = weighted_normal
    normal_avg_time = time.time() - normal_avg_time_start
    print(f"  法線加重平均計算: {normal_avg_time:.2f}秒")
    # ----------------------------------
    
    # 衣装メッシュの各頂点に対して処理
    weight_calc_time_start = time.time()
    for i, vertex in enumerate(cloth_bm.verts):
        # ワールド座標系での頂点位置
        cloth_vert_world = vertex.co
        
        # 調整済みの法線を使用
        cloth_normal_world = adjusted_normals[i]
        
        # 素体メッシュ上の最近傍面を検索
        nearest_result = bvh_tree.find_nearest(cloth_vert_world)
        distance = float('inf')  # 初期値として無限大を設定
        
        if nearest_result:
            # BVHTree.find_nearest() は (co, normal, index, distance) を返す
            nearest_point, nearest_normal, nearest_face_index, _ = nearest_result
            
            # 最近傍面を取得
            face = body_bm.faces[nearest_face_index]
            face_normal = face.normal
            
            # 面上の最近接点を計算
            closest_point_on_face = mathutils.geometry.closest_point_on_tri(
                cloth_vert_world,
                face.verts[0].co,
                face.verts[1].co,
                face.verts[2].co
            )
            
            # 面の法線をワールド座標系に変換
            face_normal_world = (body_normal_matrix @ Vector((face_normal[0], face_normal[1], face_normal[2], 0))).xyz.normalized()
            
            # 距離を計算
            distance = (cloth_vert_world - closest_point_on_face).length
            
            # 最近傍点と法線を設定
            nearest_point = closest_point_on_face
            nearest_normal = face_normal_world
        else:
            # 最近傍点が見つからない場合は初期値をNoneに設定
            nearest_point = None
            nearest_normal = None
        
        # 頂点ウェイトの初期値
        weight = 0.0
        
        if nearest_point:
            # 距離に基づくウェイト（線形補間）
            distance_weight = 0.0
            if distance <= distance_min:
                distance_weight = 0.0
            elif distance >= distance_max:
                distance_weight = 1.0
            else:
                # 線形補間
                distance_weight = (distance - distance_min) / (distance_max - distance_min)
            
            # 法線角度に基づくウェイト（線形補間）
            angle_weight = 0.0
            if nearest_normal:
                # 法線の角度を計算
                angle = math.acos(min(1.0, max(-1.0, cloth_normal_world.dot(nearest_normal))))
                
                # 90度以上の場合は法線を反転して再計算
                if angle > math.pi / 2:
                    inverted_normal = -nearest_normal
                    angle = math.acos(min(1.0, max(-1.0, cloth_normal_world.dot(inverted_normal))))
                
                # 角度の線形補間
                if angle <= angle_min_rad:
                    angle_weight = 0.0
                elif angle >= angle_max_rad:
                    angle_weight = 1.0
                else:
                    # 線形補間
                    angle_weight = (angle - angle_min_rad) / (angle_max_rad - angle_min_rad)
            
            weight = distance_weight *angle_weight
        
        # 頂点グループにウェイトを設定
        vertex_group.add([i], weight, 'REPLACE')
    weight_calc_time = time.time() - weight_calc_time_start
    print(f"  ウェイト計算: {weight_calc_time:.2f}秒")
    
    # 頂点グループをアクティブに設定
    cloth_obj.vertex_groups.active_index = vertex_group.index
    
    # Weight Paintモードに切り替え
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    
    # スムージング処理を実行（アクティブな頂点グループに適用される）
    smooth_time_start = time.time()
    bpy.ops.object.vertex_group_smooth(group_select_mode='ACTIVE', factor=0.3, repeat=10, expand=0.0)
    
    # クリーニング処理も適用
    bpy.ops.object.vertex_group_clean(group_select_mode='ACTIVE', limit=0.5)
    smooth_time = time.time() - smooth_time_start
    print(f"  スムージング処理: {smooth_time:.2f}秒")
    
    # オブジェクトモードに戻す
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Maxフィルターを適用
    print("  Maxフィルター適用中...")
    apply_max_filter_to_vertex_group(cloth_obj, new_group_name, filter_radius=0.02)
    
    # === 新しく作成された頂点グループに対するスムージング処理 ===
    print("  新しく作成された頂点グループのスムージング処理適用中...")
    neighbors_cache_result = apply_smoothing_to_vertex_group(cloth_obj, new_group_name, smoothing_radius, iteration=1, use_distance_weighting=True, gaussian_falloff=True)
    
    if smoothing_mask_groups:
        # 新しく生成された頂点グループのウェイトを取得
        new_group_weights = np.zeros(len(cloth_obj.data.vertices), dtype=np.float32)
        for i, vertex in enumerate(cloth_obj.data.vertices):
            for group in vertex.groups:
                if group.group == vertex_group.index:
                    new_group_weights[i] = group.weight
                    break
        # 指定された頂点グループのウェイト合計を計算
        total_target_weights = np.zeros(len(cloth_obj.data.vertices), dtype=np.float32)
        
        for target_group_name in smoothing_mask_groups:
            if target_group_name in cloth_obj.vertex_groups:
                target_group = cloth_obj.vertex_groups[target_group_name]
                print(f"    頂点グループ '{target_group_name}' のウェイトを取得中...")
                
                for i, vertex in enumerate(cloth_obj.data.vertices):
                    for group in vertex.groups:
                        if group.group == target_group.index:
                            total_target_weights[i] += group.weight
                            break
            else:
                print(f"    警告: 頂点グループ '{target_group_name}' が見つかりません")
        
        if mask_group_name and mask_group_name in cloth_obj.vertex_groups:
            mask_group = cloth_obj.vertex_groups[mask_group_name]
            for i in range(len(cloth_obj.data.vertices)):
                weight = 0.0
                for group in cloth_obj.data.vertices[i].groups:
                    if group.group == mask_group.index:
                        weight = group.weight
                        break
                total_target_weights[i] *= weight
        
        # 新しい頂点グループのウェイトから合計を減算
        masked_weights = np.maximum(0.0, new_group_weights * total_target_weights)
        
        # 結果を新しい頂点グループに適用
        for i in range(len(cloth_obj.data.vertices)):
            vertex_group.add([i], masked_weights[i], 'REPLACE')
    
    # === 追加処理：指定された頂点グループのウェイト処理 ===
    if target_vertex_groups:
        print("  指定された頂点グループの処理開始...")
        
        # 生成された頂点グループのウェイトを取得
        mask_weights = np.zeros(len(cloth_obj.data.vertices), dtype=np.float32)
        for i, vertex in enumerate(cloth_obj.data.vertices):
            for group in vertex.groups:
                if group.group == vertex_group.index:
                    mask_weights[i] = group.weight
                    break
        
        # 指定された頂点グループを処理
        for target_group_name in target_vertex_groups:
            if target_group_name not in cloth_obj.vertex_groups:
                print(f"  警告: 頂点グループ '{target_group_name}' が見つかりません")
                continue
            
            target_group = cloth_obj.vertex_groups[target_group_name]
            print(f"  処理中の頂点グループ: {target_group_name}")
            
            # 1. オリジナルのウェイトを取得
            original_weights = np.zeros(len(cloth_obj.data.vertices), dtype=np.float32)
            for i, vertex in enumerate(cloth_obj.data.vertices):
                for group in vertex.groups:
                    if group.group == target_group.index:
                        original_weights[i] = group.weight
                        break
            
            # 2. スムージング処理（original_weightsがすべて0でない場合のみ）
            if np.any(original_weights > 0):
                print(f"    スムージング処理実行中...")
                neighbors_cache_result = apply_smoothing_to_vertex_group(cloth_obj, target_group_name, smoothing_radius, iteration=3, use_distance_weighting=True, gaussian_falloff=True, neighbors_cache=neighbors_cache_result)
                
                # 3. スムージング後のウェイトを取得
                smoothed_weights = np.zeros(len(cloth_obj.data.vertices), dtype=np.float32)
                for i, vertex in enumerate(cloth_obj.data.vertices):
                    for group in vertex.groups:
                        if group.group == target_group.index:
                            smoothed_weights[i] = group.weight
                            break
                
                # 4. 合成処理
                print(f"    合成処理...")
                for i in range(len(cloth_obj.data.vertices)):
                    # 生成された頂点グループのウェイトを合成の重みとして使用
                    blend_factor = mask_weights[i]
                    
                    # 元のウェイトとスムージング結果を合成
                    final_weight = original_weights[i] * (1.0 - blend_factor) + smoothed_weights[i] * blend_factor
                    
                    # 最終ウェイトを設定
                    target_group.add([i], final_weight, 'REPLACE')
            else:
                print(f"    スキップ: original_weightsがすべて0のため処理をスキップします")
            
            print(f"    頂点グループ '{target_group_name}' の処理完了")
    
    # 元のモードに戻す
    bpy.ops.object.mode_set(mode=current_mode)
    
    # BMeshをクリーンアップ
    body_bm.free()
    cloth_bm.free()
    
    # キャッシュをクリーンアップ（メモリ使用量削減のため）
    clear_mesh_cache()
    
    total_time = time.time() - start_time
    print(f"{new_group_name}頂点グループを作成しました (合計時間: {total_time:.2f}秒)")
    return vertex_group
