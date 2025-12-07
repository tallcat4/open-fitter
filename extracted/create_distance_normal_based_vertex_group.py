import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import math
import time

import bpy
import mathutils
from algo_utils.vertex_group_utils import apply_max_filter_to_vertex_group
from algo_utils.vertex_group_utils import apply_min_filter_to_vertex_group
from blender_utils.get_evaluated_mesh import get_evaluated_mesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy.spatial import cKDTree


def create_distance_normal_based_vertex_group(body_obj, cloth_obj, distance_threshold=0.1, min_distance_threshold=0.005, angle_threshold=30.0, new_group_name="InpaintMask", normal_radius=0.01, filter_mask=None):
    """
    素体メッシュからの距離と法線角度に基づいて衣装メッシュに頂点グループを作成します
    
    Parameters:
    body_obj (obj): 素体メッシュのオブジェクト名
    cloth_obj (obj): 衣装メッシュのオブジェクト名
    distance_threshold (float): この距離以上離れている場合、ウェイトを1.0に設定
    min_distance_threshold (float): この距離以下の場合、ウェイトを0.0に設定
    angle_threshold (float): この角度以上の場合、ウェイトを1.0に設定（度単位）
    new_group_name (str): 作成する頂点グループ名
    normal_radius (float): 面の近傍検索を行う際に考慮する球体の半径
    filter_mask (obj): フィルタリングに使用する頂点グループ
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
    body_bm.verts.ensure_lookup_table()
    body_bm.faces.ensure_lookup_table()
    body_bm.normal_update()
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
    
    # 角度のしきい値をラジアンに変換
    angle_threshold_rad = math.radians(angle_threshold)
    
    # モディファイア適用後のソースメッシュを取得
    cloth_bm_time_start = time.time()
    cloth_bm = get_evaluated_mesh(cloth_obj)
    cloth_bm.verts.ensure_lookup_table()
    cloth_bm.faces.ensure_lookup_table()
    cloth_bm.normal_update()
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
        original_normal_world = (Vector((vertex.normal[0], vertex.normal[1], vertex.normal[2], 0))).xyz.normalized()
        
        # 素体メッシュ上の最近傍面を検索
        nearest_result = bvh_tree.find_nearest(cloth_vert_world)
        if nearest_result:
            # BVHTree.find_nearest() は (co, normal, index, distance) を返す
            nearest_point, nearest_normal, nearest_face_index, _ = nearest_result
            
            # 最近傍面を取得
            face = body_bm.faces[nearest_face_index]
            face_normal = face.normal
            
            # 面の法線をワールド座標系に変換
            face_normal_world = (Vector((face_normal[0], face_normal[1], face_normal[2], 0))).xyz.normalized()
            
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
    
    # 衣装メッシュの頂点に対してKDTreeを構築（新しい実装用）
    vertex_positions = []
    for vertex in cloth_bm.verts:
        vertex_positions.append(vertex.co)
    vertex_kd = cKDTree(vertex_positions)
    
    kdtree_time = time.time() - kdtree_time_start
    print(f"  KDTree構築: {kdtree_time:.2f}秒")
    
    # 各頂点から一定距離内に面の一部が存在する面を検索するための準備完了
    normal_avg_time_start = time.time()
    normal_avg_time = time.time() - normal_avg_time_start
    print(f"  面の近傍検索準備完了: {normal_avg_time:.2f}秒")
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
            face_normal_world = (Vector((face_normal[0], face_normal[1], face_normal[2], 0))).xyz.normalized()
            
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
        
        if nearest_point and distance >= min_distance_threshold:
            # 距離に基づくウェイト
            if distance >= distance_threshold:
                weight = 1.0
            
            # 法線角度に基づくウェイト（新しいロジック）
            if weight < 1.0 and nearest_normal:
                # 衣装メッシュの頂点から一定距離内の面をすべて取得
                min_angle = float('inf')
                
                # cloth_vert_worldからnormal_radiusの範囲内に少なくとも一つの頂点を含む面を検索
                nearby_vertex_indices = vertex_kd.query_ball_point(cloth_vert_world, normal_radius)
                nearby_faces = set()
                
                # 近傍頂点を含む面を検索
                for vertex_idx in nearby_vertex_indices:
                    vertex = cloth_bm.verts[vertex_idx]
                    for face in vertex.link_faces:
                        nearby_faces.add(face.index)
                
                nearby_faces = list(nearby_faces)
                
                if nearby_faces:
                    for face_index in nearby_faces:
                        # 面の法線を取得
                        face_normal = face_adjusted_normals[face_index]
                        
                        # 素体メッシュの最近接面の法線との角度を計算
                        angle = math.acos(min(1.0, max(-1.0, face_normal.dot(nearest_normal))))
                        
                        # 90度以上の場合は法線を反転して再計算
                        if angle > math.pi / 2:
                            inverted_normal = -nearest_normal
                            angle = math.acos(min(1.0, max(-1.0, face_normal.dot(inverted_normal))))
                        
                        # 最小角度を更新
                        min_angle = min(min_angle, angle)
                else:
                    # 近傍面が見つからない場合は元の頂点法線を使用
                    original_adjusted_normal = adjusted_normals[i]
                    min_angle = math.acos(min(1.0, max(-1.0, original_adjusted_normal.dot(nearest_normal))))
                    
                    # 90度以上の場合は法線を反転して再計算
                    if min_angle > math.pi / 2:
                        inverted_normal = -nearest_normal
                        min_angle = math.acos(min(1.0, max(-1.0, original_adjusted_normal.dot(inverted_normal))))
                
                # 最小角度のしきい値を超えた場合
                if min_angle >= angle_threshold_rad:
                    weight = 1.0
        
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
    bpy.ops.object.vertex_group_smooth(factor=0.3, repeat=10, expand=0.25)
    
    # クリーニング処理も適用
    bpy.ops.object.vertex_group_clean(group_select_mode='ACTIVE', limit=0.5)
    smooth_time = time.time() - smooth_time_start
    print(f"  スムージング処理: {smooth_time:.2f}秒")

    apply_max_filter_to_vertex_group(cloth_obj, new_group_name, filter_radius=0.01, filter_mask=filter_mask)
    apply_min_filter_to_vertex_group(cloth_obj, new_group_name, filter_radius=0.01, filter_mask=filter_mask)
    
    # 元のモードに戻す
    bpy.ops.object.mode_set(mode=current_mode)
    
    # BMeshをクリーンアップ
    body_bm.free()
    cloth_bm.free()
    
    total_time = time.time() - start_time
    print(f"{new_group_name}頂点グループを作成しました (合計時間: {total_time:.2f}秒)")
    return vertex_group
