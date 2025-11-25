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
using System.IO;
using System.Collections.Generic;

public class OpenFitterWindow : EditorWindow
{
    // Inputs
    private GameObject sourceObject;
    private TextAsset rbfDataJson;
    private TextAsset poseDataJson;
    
    // Settings
    private string outputFolder = "Assets/OpenFitter_Output";
    private bool createPrefab = true;

    [MenuItem("Window/OpenFitter/Converter")]
    public static void ShowWindow()
    {
        GetWindow<OpenFitterWindow>("OpenFitter Converter");
    }

    private void OnGUI()
    {
        GUILayout.Label("OpenFitter Converter", EditorStyles.boldLabel);
        GUILayout.Space(10);

        // 1. Input Section
        GUILayout.Label("Inputs", EditorStyles.label);
        sourceObject = (GameObject)EditorGUILayout.ObjectField("Source Object (Scene/Prefab)", sourceObject, typeof(GameObject), true);
        rbfDataJson = (TextAsset)EditorGUILayout.ObjectField("RBF Data JSON", rbfDataJson, typeof(TextAsset), false);
        poseDataJson = (TextAsset)EditorGUILayout.ObjectField("Pose Data JSON", poseDataJson, typeof(TextAsset), false);

        GUILayout.Space(10);

        // 2. Output Settings
        GUILayout.Label("Output Settings", EditorStyles.label);
        
        EditorGUILayout.BeginHorizontal();
        outputFolder = EditorGUILayout.TextField("Output Folder", outputFolder);
        if (GUILayout.Button("...", GUILayout.Width(30)))
        {
            string path = EditorUtility.OpenFolderPanel("Select Output Folder", "Assets", "");
            if (!string.IsNullOrEmpty(path))
            {
                if (path.StartsWith(Application.dataPath))
                {
                    outputFolder = "Assets" + path.Substring(Application.dataPath.Length);
                }
                else
                {
                    EditorUtility.DisplayDialog("Error", "Output folder must be inside the Assets directory.", "OK");
                }
            }
        }
        EditorGUILayout.EndHorizontal();

        createPrefab = EditorGUILayout.Toggle("Create Prefab", createPrefab);

        GUILayout.Space(20);

        // 3. Action
        GUI.backgroundColor = new Color(0.6f, 0.9f, 1.0f);
        if (GUILayout.Button("Convert & Save", GUILayout.Height(40)))
        {
            if (ValidateInputs())
            {
                ConvertAndSave();
            }
        }
        GUI.backgroundColor = Color.white;
    }

    private bool ValidateInputs()
    {
        if (sourceObject == null)
        {
            EditorUtility.DisplayDialog("Error", "Please assign a Source Object.", "OK");
            return false;
        }
        if (rbfDataJson == null)
        {
            EditorUtility.DisplayDialog("Error", "Please assign RBF Data JSON.", "OK");
            return false;
        }
        if (poseDataJson == null)
        {
            EditorUtility.DisplayDialog("Error", "Please assign Pose Data JSON.", "OK");
            return false;
        }
        return true;
    }

    private void ConvertAndSave()
    {
        // 1. Instantiate Copy
        GameObject instance;
        bool isSceneObject = !EditorUtility.IsPersistent(sourceObject);
        
        if (isSceneObject)
        {
            instance = Instantiate(sourceObject);
            instance.transform.position = sourceObject.transform.position;
            instance.transform.rotation = sourceObject.transform.rotation;
            instance.transform.localScale = sourceObject.transform.localScale;
        }
        else
        {
            instance = (GameObject)PrefabUtility.InstantiatePrefab(sourceObject);
        }
        
        instance.name = "[Fitted] " + sourceObject.name;
        Undo.RegisterCreatedObjectUndo(instance, "OpenFitter Convert");

        try
        {
            // 2. Attach & Run Components
            // RBF
            var rbf = instance.AddComponent<RBFDeformer>();
            rbf.rbfDataJson = rbfDataJson;
            rbf.RunDeformationInEditor();

            // Bone
            var bone = instance.AddComponent<BoneDeformer>();
            bone.poseDataJson = poseDataJson;
            bone.rootTransform = instance.transform;
            bone.ApplyPose();

            // BindPose
            var binder = instance.AddComponent<BindPoseCorrector>();
            binder.RecalculateBindPoses();

            // 3. Save Meshes to Disk
            if (!Directory.Exists(outputFolder))
            {
                Directory.CreateDirectory(outputFolder);
            }

            string meshFolder = Path.Combine(outputFolder, "Meshes_" + sourceObject.name);
            if (!Directory.Exists(meshFolder))
            {
                Directory.CreateDirectory(meshFolder);
            }

            var smrs = instance.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            foreach (var smr in smrs)
            {
                Mesh mesh = smr.sharedMesh;
                if (mesh == null) continue;

                // Check if it's a new instance (RBFDeformer creates copies ending in _Preview)
                // Or if we just want to save everything to be safe.
                // RBFDeformer creates meshes named "OriginalName_Preview".
                
                Mesh meshToSave = Instantiate(mesh);
                meshToSave.name = mesh.name.Replace("_Preview", "");
                
                string assetPath = Path.Combine(meshFolder, meshToSave.name + ".asset");
                assetPath = AssetDatabase.GenerateUniqueAssetPath(assetPath);
                
                AssetDatabase.CreateAsset(meshToSave, assetPath);
                smr.sharedMesh = meshToSave; // Re-assign the saved asset
            }
            
            AssetDatabase.SaveAssets();

            // 4. Cleanup Components
            DestroyImmediate(binder);
            DestroyImmediate(bone);
            DestroyImmediate(rbf);
            
            // Also remove OpenFitterController if it exists on the source
            var controller = instance.GetComponent<OpenFitterController>();
            if (controller != null) DestroyImmediate(controller);

            // 5. Create Prefab
            if (createPrefab)
            {
                string prefabPath = Path.Combine(outputFolder, instance.name + ".prefab");
                prefabPath = AssetDatabase.GenerateUniqueAssetPath(prefabPath);
                PrefabUtility.SaveAsPrefabAssetAndConnect(instance, prefabPath, InteractionMode.UserAction);
                Debug.Log($"<color=green>[OpenFitter]</color> Saved Prefab to: {prefabPath}");
            }

            Debug.Log("<color=green>[OpenFitter]</color> Conversion Complete!");
            Selection.activeGameObject = instance;
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[OpenFitter] Conversion Failed: {e.Message}\n{e.StackTrace}");
            // Optional: Destroy instance on failure?
        }
    }
}
