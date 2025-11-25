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

[ExecuteInEditMode]
public class OpenFitterController : MonoBehaviour
{
    [Header("Components")]
    public RBFDeformer rbfDeformer;
    public BoneDeformer boneDeformer;
    public BindPoseCorrector bindPoseCorrector;

    [Header("Settings")]
    public bool autoFindComponents = true;

    private void OnEnable()
    {
        if (autoFindComponents)
        {
            FindComponents();
        }
    }

    public void FindComponents()
    {
        if (rbfDeformer == null) rbfDeformer = GetComponentInChildren<RBFDeformer>();
        if (boneDeformer == null) boneDeformer = GetComponentInChildren<BoneDeformer>();
        if (bindPoseCorrector == null) bindPoseCorrector = GetComponentInChildren<BindPoseCorrector>();
    }

    public void RunFullFittingPipeline()
    {
        FindComponents();

        if (rbfDeformer == null || boneDeformer == null || bindPoseCorrector == null)
        {
            Debug.LogError("Missing required components. Please ensure RBFDeformer, BoneDeformer, and BindPoseCorrector are attached.");
            return;
        }

        Debug.Log("<color=cyan>[OpenFitter]</color> Starting full fitting pipeline...");

        // 1. RBF Deformation (Mesh Shape)
        Debug.Log("<color=cyan>[OpenFitter]</color> Step 1: Running RBF Deformation...");
        rbfDeformer.RunDeformationInEditor();

        // 2. Bone Deformation (Skeleton Shape)
        Debug.Log("<color=cyan>[OpenFitter]</color> Step 2: Running Bone Deformation...");
        boneDeformer.ApplyPose();

        // 3. BindPose Correction (Re-binding)
        Debug.Log("<color=cyan>[OpenFitter]</color> Step 3: Recalculating BindPoses...");
        bindPoseCorrector.RecalculateBindPoses();

        Debug.Log("<color=green>[OpenFitter]</color> Pipeline completed successfully!");
    }

    public void ResetAll()
    {
        FindComponents();

        if (boneDeformer != null)
        {
            Debug.Log("<color=orange>[OpenFitter]</color> Resetting Bone Pose...");
            boneDeformer.ResetPose();
        }

        // Note: Resetting RBF meshes is complex because it involves swapping back original meshes.
        // Currently, RBFDeformer doesn't expose a "Reset" method that reverts sharedMesh.
        // Users should manually revert meshes or we can implement it later if needed.
        Debug.LogWarning("<color=orange>[OpenFitter]</color> Note: Mesh deformation reset is not fully automated yet. You may need to manually revert meshes if you want to run RBF again from scratch.");
    }
}
