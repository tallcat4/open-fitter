using UnityEngine;
using UnityEditor;

[CustomEditor(typeof(BoneDeformer))]
public class BoneDeformerEditor : Editor
{
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        BoneDeformer deformer = (BoneDeformer)target;

        GUILayout.Space(10);

        if (GUILayout.Button("Apply Pose"))
        {
            // Record undo for all transforms under the root
            if (deformer.rootTransform != null)
            {
                Undo.RecordObjects(deformer.rootTransform.GetComponentsInChildren<Transform>(), "Apply Bone Pose");
            }
            else
            {
                Undo.RecordObjects(deformer.GetComponentsInChildren<Transform>(), "Apply Bone Pose");
            }
            
            deformer.ApplyPose();
        }

        if (GUILayout.Button("Reset Pose"))
        {
            if (deformer.rootTransform != null)
            {
                Undo.RecordObjects(deformer.rootTransform.GetComponentsInChildren<Transform>(), "Reset Bone Pose");
            }
            else
            {
                Undo.RecordObjects(deformer.GetComponentsInChildren<Transform>(), "Reset Bone Pose");
            }
            
            deformer.ResetPose();
        }
    }
}
