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

[CustomEditor(typeof(OpenFitterController))]
public class OpenFitterControllerEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        OpenFitterController controller = (OpenFitterController)target;

        GUILayout.Space(20);
        GUILayout.Label("Pipeline Execution", EditorStyles.boldLabel);

        GUI.backgroundColor = new Color(0.7f, 1.0f, 0.7f);
        if (GUILayout.Button("Run Full Fitting Pipeline", GUILayout.Height(40)))
        {
            Undo.RecordObjects(controller.GetComponentsInChildren<Transform>(true), "Run OpenFitter Pipeline");
            controller.RunFullFittingPipeline();
            SceneView.RepaintAll();
        }
        GUI.backgroundColor = Color.white;

        GUILayout.Space(10);
        if (GUILayout.Button("Reset Bone Pose"))
        {
            controller.ResetAll();
            SceneView.RepaintAll();
        }
    }
}
