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
using UnityEditor;

[CustomEditor(typeof(BindPoseCorrector))]
public class BindPoseCorrectorEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        BindPoseCorrector corrector = (BindPoseCorrector)target;

        GUILayout.Space(10);
        GUILayout.Label("Actions", EditorStyles.boldLabel);

        if (GUILayout.Button("Recalculate BindPoses", GUILayout.Height(30)))
        {
            Undo.RecordObjects(corrector.GetComponentsInChildren<SkinnedMeshRenderer>(true), "Recalculate BindPoses");
            corrector.RecalculateBindPoses();
            
            // シーンビューの更新を強制
            SceneView.RepaintAll();
        }
        
        GUILayout.Space(5);
        EditorGUILayout.HelpBox(
            "This will update the BindPoses of all child SkinnedMeshRenderers to match the CURRENT bone positions.\n" +
            "Use this after applying RBF deformation and Bone deformation to prevent double-transformation.", 
            MessageType.Info);
    }
}
