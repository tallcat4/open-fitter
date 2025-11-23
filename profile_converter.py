#!/usr/bin/env python
# ----------------------------------------------------------------------------
# profile_converter.py: Converts saved .npz deformation field data into a compact JSON format with RBF weights for Unity.
# Copyright (C) [2025] tallcat
#
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the accompanying LICENSE file for more details.
# ----------------------------------------------------------------------------

import sys
import os
import json
import numpy as np
import time

try:
    from rbf_core import RBFCore
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from rbf_core import RBFCore

def convert_npz_to_json(npz_path):
    print(f"Converting: {npz_path}")
    
    try:
        data = np.load(npz_path, allow_pickle=True)
        
        # --- データの取り出し ---
        if 'all_field_points' in data:
            all_pts = data['all_field_points']
            all_deltas = data['all_delta_positions']
            centers = all_pts[-1]
            deltas = all_deltas[-1]
            if len(centers) == 0 and len(all_pts) > 1:
                centers = all_pts[-2]
                deltas = all_deltas[-2]
        elif 'field_points' in data:
            centers = data['field_points']
            deltas = data['delta_positions']
        else:
            print("Error: Unknown NPZ format.")
            return

        # キャスト
        centers = np.array(centers.tolist(), dtype=float)
        deltas = np.array(deltas.tolist(), dtype=float)
        
        # --- ミラーリング ---
        enable_x_mirror = False
        if 'enable_x_mirror' in data:
            enable_x_mirror = bool(data['enable_x_mirror'])
        
        if enable_x_mirror:
            print("Applying X-Mirroring...")
            mask = centers[:, 0] > 0.0001
            mirror_centers = centers[mask].copy()
            mirror_deltas = deltas[mask].copy()
            mirror_centers[:, 0] *= -1
            mirror_deltas[:, 0] *= -1
            centers = np.vstack([centers, mirror_centers])
            deltas = np.vstack([deltas, mirror_deltas])

        total_points = len(centers)
        print(f"Total Grid Points: {total_points}")

        # --- 【重要】ダウンサンプリング (間引き) ---
        # Unityでリアルタイム動作させるため、制御点は最大でも 500点 程度に抑える必要がある
        # (経験的に500点程度が最も安定して動作するため、PoC段階ではこの値を採用)
        MAX_CENTERS = 500 
        
        if total_points > MAX_CENTERS:
            print(f"⚠️ Too many points for RBF centers ({total_points} > {MAX_CENTERS}).")
            print(f"   Downsampling to {MAX_CENTERS} points for performance...")
            
            # ランダムにインデックスを選択（一様分布）
            # ※本来は「K-Means」や「Farthest Point Sampling」が良いが、100万点相手だと計算が終わらないためランダム採用
            np.random.seed(42) # 再現性のため固定
            indices = np.random.choice(total_points, MAX_CENTERS, replace=False)
            
            centers = centers[indices]
            deltas = deltas[indices]
            
            print(f"   Reduced to {len(centers)} points.")

        # --- RBF計算 ---
        epsilon = 0.5
        if 'rbf_epsilon' in data:
            epsilon = float(data['rbf_epsilon'])
            if epsilon <= 0: epsilon = 0.5

        target_points = centers + deltas
        
        print("Calculating RBF weights...")
        rbf = RBFCore(epsilon=epsilon)
        rbf.fit(centers, target_points)

        # --- JSON保存 ---
        export_data = {
            "epsilon": float(rbf.epsilon),
            "centers": centers.tolist(),
            "weights": rbf.weights.tolist(),
            "poly_weights": rbf.polynomial_weights.tolist()
        }

        json_path = os.path.splitext(npz_path)[0] + ".json"
        with open(json_path, 'w') as f:
            json.dump(export_data, f)
            
        print(f"Success! Saved to: {json_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for file_path in sys.argv[1:]:
            if file_path.lower().endswith('.npz'):
                convert_npz_to_json(file_path)
        time.sleep(3)
    else:
        print("Drop .npz files here.")
        input()