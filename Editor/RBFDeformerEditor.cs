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

// RBFDeformerEditor.cs

using UnityEngine;
using UnityEditor;
using System.IO;

[CustomEditor(typeof(RBFDeformer))]
public class RBFDeformerEditor : Editor
{
    private SerializedProperty rbfDataJsonProp;
    private SerializedProperty targetsProp;

    private void OnEnable()
    {
        rbfDataJsonProp = serializedObject.FindProperty("rbfDataJson");
        targetsProp = serializedObject.FindProperty("targets");
    }

    public override void OnInspectorGUI()
    {
        RBFDeformer deformer = (RBFDeformer)target;
        serializedObject.Update();

        // ----------------------------------------------------
        // 1. RBF Data Path Setup
        // ----------------------------------------------------
        GUILayout.Label("RBF Data Configuration", EditorStyles.boldLabel);
        
        EditorGUILayout.PropertyField(rbfDataJsonProp, new GUIContent("RBF Data JSON"));

        // 状態表示
        GUILayout.Space(5);
        EditorGUILayout.LabelField("Target Meshes:", EditorStyles.miniBoldLabel);
        
        if (targetsProp != null)
        {
            EditorGUILayout.PropertyField(targetsProp, new GUIContent("Targets"), true);
            
            if (deformer.Targets != null && deformer.Targets.Count > 0)
            {
                EditorGUILayout.HelpBox($"Found {deformer.Targets.Count} target meshes.", MessageType.Info);
            }
            else
            {
                EditorGUILayout.HelpBox("No targets found. Click 'Run RBF' to initialize.", MessageType.Warning);
            }
        }
        
        serializedObject.ApplyModifiedProperties();
        
        // ----------------------------------------------------
        // 2. Deformation Workflow
        // ----------------------------------------------------

        GUILayout.Space(15);
        GUILayout.Label("Workflow (Edit Mode Only)", EditorStyles.boldLabel);

        if (GUILayout.Button("Run RBF & Preview", GUILayout.Height(30)))
        {
            deformer.RunDeformationInEditor();
            SceneView.RepaintAll();
        }

        GUILayout.Space(10);
        
        // ----------------------------------------------------
        // 3. Export Options
        // ----------------------------------------------------
        
        bool hasTargets = deformer.Targets != null && deformer.Targets.Count > 0;
        
        using (new EditorGUI.DisabledScope(!hasTargets))
        {
            GUILayout.Label("Export Options", EditorStyles.boldLabel);

            if (GUILayout.Button("Save Deformed Meshes (.asset)"))
            {
                SaveAsMeshAssets(deformer);
            }

            if (GUILayout.Button("Create Meshes with BlendShape"))
            {
                AddBlendShapeToOriginals(deformer);
            }
        }
    }

    void SaveAsMeshAssets(RBFDeformer deformer)
    {
        string folderPath = EditorUtility.SaveFolderPanel("Select Folder to Save Meshes", Application.dataPath, "");
        if (string.IsNullOrEmpty(folderPath)) return;

        // Assets/... の相対パスに変換
        if (folderPath.StartsWith(Application.dataPath))
        {
            folderPath = "Assets" + folderPath.Substring(Application.dataPath.Length);
        }
        else
        {
            Debug.LogError("Please select a folder inside the Assets directory.");
            return;
        }

        foreach (var target in deformer.Targets)
        {
            if (target.deformedMesh == null) continue;

            Mesh meshToSave = Instantiate(target.deformedMesh);
            string path = Path.Combine(folderPath, target.originalMesh.name + "_RBF.asset");
            
            AssetDatabase.CreateAsset(meshToSave, path);
            Debug.Log($"Saved mesh to: {path}");
        }
        AssetDatabase.SaveAssets();
    }

    void AddBlendShapeToOriginals(RBFDeformer deformer)
    {
        string folderPath = EditorUtility.SaveFolderPanel("Select Folder to Save BlendShape Meshes", Application.dataPath, "");
        if (string.IsNullOrEmpty(folderPath)) return;

        if (folderPath.StartsWith(Application.dataPath))
        {
            folderPath = "Assets" + folderPath.Substring(Application.dataPath.Length);
        }
        else
        {
            Debug.LogError("Please select a folder inside the Assets directory.");
            return;
        }

        foreach (var target in deformer.Targets)
        {
            if (target.originalMesh == null || target.deformedMesh == null) continue;

            Mesh original = target.originalMesh;
            Mesh deformed = target.deformedMesh;

            Vector3[] origVerts = original.vertices;
            Vector3[] defVerts = deformed.vertices;
            
            if (origVerts.Length != defVerts.Length)
            {
                Debug.LogError($"Vertex count mismatch for {original.name}. Skipping.");
                continue;
            }
            
            // 差分計算
            Vector3[] delta = new Vector3[origVerts.Length];
            for (int i = 0; i < origVerts.Length; i++)
            {
                delta[i] = defVerts[i] - origVerts[i];
            }

            string path = Path.Combine(folderPath, original.name + "_BlendShape.asset");

            Mesh newMesh = Instantiate(original);
            newMesh.name = original.name + "_BlendShape";
            newMesh.AddBlendShapeFrame("RBF_Adjust", 100f, delta, null, null);
            
            AssetDatabase.CreateAsset(newMesh, path);

            // 適用
            if (target.smr != null)
            {
                target.smr.sharedMesh = newMesh;
                target.smr.SetBlendShapeWeight(newMesh.blendShapeCount - 1, 100f);
            }
            
            Debug.Log($"Created BlendShape mesh at: {path}");
        }
        AssetDatabase.SaveAssets();
    }
}