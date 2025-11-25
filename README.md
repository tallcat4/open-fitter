# OpenFitter

English | [日本語](Documentation~/README-ja.md)

An open-source avatar clothing fitting tool compatible with the "MochiFitter" workflow.
Based on the GPL-3 core logic released by Nine Gates, OpenFitter provides a complete pipeline for transferring clothing between different avatar shapes using RBF (Radial Basis Function) deformation and Bone Pose transfer.

***

**Status**: Alpha (Partially Functional)
While the core features for fitting clothing (Mesh Deformation, Bone Transformation, and Re-binding) are implemented and usable, full compatibility with all "MochiFitter" features is not yet achieved.

***

## Features

*   **Blender Tools**:
    *   **Bone Pose Exporter**: Exports the difference between two armatures (Source -> Target) as a JSON file.
    *   **RBF Field Exporter**: Calculates the deformation field between a "Basis" shape key and a "Target" shape key and exports it as RBF data (JSON). Supports epsilon estimation and smoothing.
*   **Unity Tools**:
    *   **OpenFitter Converter**: A standalone Editor Window to convert clothing prefabs.
        *   Applies RBF deformation to meshes.
        *   Applies Bone Pose transformation to the armature.
        *   **Asset Saving**: Automatically saves deformed meshes and creates a ready-to-use Prefab.

## Installation

### Blender Addon
1.  Copy the `blender_addon` folder (or zip it) and install it in Blender via `Edit > Preferences > Add-ons`.
2.  Enable "Import-Export: OpenFitter Tools".
3.  Access the tools via the **Sidebar (N-Panel) > OpenFitter** tab.

### Unity Package
1.  Copy the `UnityProject/Assets/OpenFitter` folder into your Unity project's `Assets` folder.
2.  Ensure you have the `Newtonsoft Json` package installed (usually included by default in modern Unity versions, or install via Package Manager).

## Usage Workflow

### 1. Blender: Prepare Data
1.  **Bone Data**:
    *   Align your Source Armature to the Target Armature.
    *   Select the Armature and use **OpenFitter > Bone Pose Export** to save `pose_data.json`.
2.  **RBF Data**:
    *   Create a "Basis" shape key (original shape) and a "Target" shape key (fitted shape) on your reference mesh.
    *   Select the mesh and use **OpenFitter > RBF Field Export**.
    *   Select the Basis and Target keys, adjust settings (Epsilon, Smoothing), and export `rbf_data.json`.

### 2. Unity: Convert Clothing
1.  Import the exported `.json` files into your Unity project.
2.  Open **Window > OpenFitter > Converter**.
3.  Assign the **Source Object** (the clothing prefab you want to fit).
4.  Assign the **RBF Data JSON** and **Pose Data JSON**.
5.  Click **Convert & Save**.
6.  A new `[Fitted]` prefab will be created in the output folder, ready for use.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3).
See the LICENSE file for details.

## Special Thanks

We would like to express our gratitude to Nine Gates for releasing the core logic as open source. Their great contribution to the open source community made this project possible.

## Acknowledgements & Compliance

This software is an independent open-source implementation compatible with "MochiFitter".

* Core Engine: Derived from the GPL-3 licensed source code released by Nine Gates.
* UI & Frontend: Developed entirely from scratch.

Note on Development:
To ensure compliance with the original software's EULA (specifically Article 3), this project was developed without any reverse engineering, decompilation, or disassembly of the proprietary binaries. All original implementations are based solely on public documentation and the GPL-3 source code.

This is an unofficial project and has not received any approval or endorsement from Nine Gates or "MochiFitter".
