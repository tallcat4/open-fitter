// ----------------------------------------------------------------------------
// Copyright (C) [2025] tallcat
//
// This file is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This file is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
// See the accompanying LICENSE file for more details.
// ----------------------------------------------------------------------------

using UnityEngine;
using System.Collections.Generic;

[ExecuteInEditMode]
public class BindPoseCorrector : MonoBehaviour
{
    /// <summary>
    /// 子階層にあるすべてのSkinnedMeshRendererに対して、現在のボーン位置に基づいてBindPoseを再計算します。
    /// これにより、現在のポーズが「初期姿勢（Tポーズ）」として再定義されます。
    /// </summary>
    public void RecalculateBindPoses()
    {
        var smrs = GetComponentsInChildren<SkinnedMeshRenderer>(true);
        int count = 0;

        foreach (var smr in smrs)
        {
            if (ProcessSMR(smr))
            {
                count++;
            }
        }
        Debug.Log($"<color=green>[BindPoseCorrector]</color> Updated bindposes for {count} renderers.");
    }

    bool ProcessSMR(SkinnedMeshRenderer smr)
    {
        Mesh mesh = smr.sharedMesh;
        if (mesh == null) return false;

        Transform[] bones = smr.bones;
        if (bones == null || bones.Length == 0) return false;

        // BindPose配列の準備
        Matrix4x4[] bindPoses = new Matrix4x4[bones.Length];
        
        // メッシュのルート変換行列
        // BindPoseは「メッシュのローカル空間」を基準としたボーンの逆変換行列です。
        // 公式定義: bindPose = bone.worldToLocalMatrix * transform.localToWorldMatrix;
        Matrix4x4 meshRootMat = smr.transform.localToWorldMatrix;

        for (int i = 0; i < bones.Length; i++)
        {
            if (bones[i] == null)
            {
                // ボーンが欠落している場合は単位行列を入れておく（エラー回避）
                bindPoses[i] = Matrix4x4.identity;
                continue;
            }
            
            // 現在のボーンの位置を「初期位置」とするためのBindPoseを計算
            bindPoses[i] = bones[i].worldToLocalMatrix * meshRootMat;
        }

        mesh.bindposes = bindPoses;
        return true;
    }
}
