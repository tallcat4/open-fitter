# OpenFitter

[English](#english) | [日本語](#japanese)

<a name="english"></a>

An open-source avatar clothing fitting tool implementation project designed to handle data formats from the "MochiFitter" workflow.
Based on the GPL-3 components released by Nine Gates, OpenFitter provides a pipeline for transferring clothing between different avatar shapes using RBF (Radial Basis Function) deformation and Bone Pose transfer.

***

**Status**: **Architecture Refactoring**

The project is currently in the phase of analyzing and structuring the original code (Upstream) to ensure data compatibility while establishing a maintainable code base.

***

## Architecture Refresh & Progress

We are actively refactoring the core logic derived from the upstream GPL code. The goal is to transform the code structure into a format that is easier for the open-source community to maintain and extend.

*   **Legacy Implementation**:
    The initial independent implementation of bone/mesh control logic has been deprecated.

*   **Upstream-based Implementation (Current Focus)**:
    We are restructuring the GPL code (approx. 20,000 lines) located in `src/upstream/retarget_script2_7.py`.
    Recent efforts have focused on adapting the codebase for better readability and modularity:

    *   **Modularization via AST**: Using Abstract Syntax Tree (AST) tools, the large-scale source file was subdivided into separate files per function and process to improve navigability. (Note: The current file granularity is high and subject to future consolidation.)
    *   **Streamlining**: Identified and removed approximately 50 isolated functions that are not currently required for this project's scope.
    *   **Pipeline Structured & Visualized**: Refactored several large-scale functions into structured classes and processing stages. This reorganization helps visualize the processing pipeline, making the logic easier to trace for developers.
    *   **Removed Proprietary Dependency**: Removed the dependency on the proprietary `Template.fbx`, `avatar_data_template.json`, and `pose_basis_template.json` files. Standard clothing fitting functionality appears to operate correctly without them, though we are monitoring for potential regressions in specific features.
    *   **Optimization**: Applied performance optimizations alongside the refactoring process.

### Version Compatibility & Base Code

The current refactored codebase is based on `retarget_script2_7.py` included in "MochiFitter" 27r.

*   **Targeting 30r**: Although argument formats changed between 27r and 30r, we have updated `parse_args.py` to match the new specifications. Consequently, the current code is **configured to operate with** the "MochiFitter" 30r binary.
*   **Regarding Upstream Changes (`retarget_script2_10.py`)**: We are aware that `retarget_script2_10.py` (included in 30r) contains approximately 1,000 lines of additions and changes compared to the 2.7 version. However, we have decided to hold off on merging these upstream changes for now, based on the following:
    1. The current code operates correctly with 30r via the argument fix.
    2. Our tests indicate the current implementation is faster than the 2.10 script.
    3. Due to heavy refactoring, merging the massive upstream diff is technically difficult at this stage.

### Long-term Goals & Future Scope

The primary objective of the current refactoring is to understand the underlying algorithms and mechanisms, rather than just cleaning up the code.

*   **Frontend Design**: Once the logic within the GPL-3 code is fully comprehended, we plan to design a safe, open-source alternative to the proprietary components of the original workflow.This future design will be based strictly on the understanding gained from the GPL code and public documentation, ensuring that no reverse engineering of proprietary binaries is involved.
*   **Separation of Concerns**: To maintain a clear distinction between the "Upstream-based" code and our "New Independent" implementation, this future development will likely take place in a **separate repository**.

## Acknowledgements & Compliance

This software is an independent open-source implementation interoperable with "MochiFitter" data.

* Core Engine: Based on the GPL-3 source code (Upstream) being released by Nine Gates.
* UI & Frontend: Being developed independently for this project.

**Development Policy and Compliance:**

*   **Shift in Development Policy**: Initially, this project avoided direct interaction with the original proprietary product to attempt an independent reproduction. However, our priority has shifted to ensuring complete interoperability. We now utilize the original proprietary product in a standard manner as a reference to validate the behavior and data compatibility of our GPL-3 development.
*   **No Reverse Engineering**: To ensure compliance with the original product's EULA, this project is developed **without any reverse engineering** (decompilation, disassembly, etc.) of proprietary binaries. All independent implementations are based on publicly available documentation, GPL-3 source code, and behavioral observation.

This is an unofficial project and has not received any approval or endorsement from Nine Gates or "MochiFitter".

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3).
See the LICENSE file for details.

---

<a name="japanese"></a>

# OpenFitter (日本語)

「もちふぃった～」ワークフローのデータ形式に対応した、オープンソースのアバター衣装フィッティングツール実装プロジェクトです。
Nine Gatesによって公開されたGPL-3コンポーネントに基づき、RBF変形とボーンポーズ転送のパイプラインを提供します。

***

**ステータス**: **Architecture Refactoring**

現在、本プロジェクトは本家製品（Upstream）とのデータ互換性を維持しつつ、持続可能なコードベースを確立するための解析・構造改革フェーズにあります。

***

## アーキテクチャの刷新と進捗

Upstreamより取得したコアロジックに対し、オープンソースコミュニティでの保守や拡張を容易にするためのリファクタリングを進めています。

*   **レガシー実装**:
    独自に推測・実装していたボーン・メッシュ制御ロジックは廃止されました。

*   **Upstreamに基づく実装 (現在進行中)**:
    `src/upstream/retarget_script2_7.py` に配置された約20,000行に及ぶGPLコードに対し、可読性とモジュール性を高めるための改善を実施しました。

    *   **ASTによるモジュール化**: AST（抽象構文木）ベースのツールを使用し、大規模なソースファイルを関数・処理単位で個別のファイルへ分割しました。（現在は分割粒度が細かいため、今後の開発で適切な構成へ再統合していく予定です。）
    *   **コードの軽量化**: 現状使用されていない約50個の関数を特定し、削除することでコードベースを整理しました。
    *   **パイプラインの可視化**: 複数の大規模な関数をクラス化し、処理ステージごとに整理しました。これにより処理パイプラインの流れが可視化され、開発者がロジックを追いやすくなりました。
    *   **プロプライエタリ依存の排除**: プロプライエタリなデータである `Template.fbx`、`avatar_data_template.json`、`pose_basis_template.json` への依存を排除しました。一部機能への影響（デグレ）の可能性は残るものの、標準的な衣装の着せ替えにおいては問題なく動作しているように見受けられます。
    *   **処理の最適化**: リファクタリングの過程で、複数の処理に対し最適化を施しました。

### バージョン互換性とベースコードについて

現在リファクタリングされているコードは、「もちふぃった～」27rに含まれていた `retarget_script2_7.py` をベースとしています。

*   **30rバイナリへの対応**: 27rから30rの間で引数の形式が変更されましたが、本プロジェクトでは `parse_args.py` をアップデートすることで対応しています。そのため、現在は「もちふぃった～」30rのバイナリでの動作を想定しています。
*   **Upstreamの変更への追従 (`retarget_script2_10.py`)**: 30rに含まれる `retarget_script2_10.py` では、2.7系と比較して約1,000行規模のコード追加・変更が行われていることを把握しています。しかし、以下の理由からこれらの変更の追従は現在保留としています。
    1. 引数処理の修正のみで、現状問題なく動作しているため。
    2. 確認している限り、2.10系よりも現在のコードの方が高速に動作するため。
    3. リファクタリングによる構造変更が大きく、差分のマージが技術的に容易ではないため。

### 長期的な目標

現在行っているリファクタリングの目的は、単なるコードの整理ではなく、アルゴリズムや内部構造を理解することにあります。

*   **フロントエンドの設計**: GPL-3コードに含まれるロジックを把握した段階で、その知見に基づき、プロプライエタリな部分の代替となる機能を安全に設計・実装する計画です。この将来的な設計は、GPLコードの理解と公開ドキュメントに基づいて行われ、プロプライエタリなバイナリのリバースエンジニアリングは一切含みません。
*   **プロジェクトの分離**: Upstream由来のコードと、将来開発される完全新規の実装を明確に区別するため、この新しい開発は本リポジトリとは別リポジトリで行われる可能性が高いです。

## クレジット・規約の遵守

本ソフトウェアは「もちふぃった～」のデータと相互運用性を持つ、独立したオープンソース実装です。

* コアエンジン: Nine Gatesにより公開されているGPL-3ソースコード(Upstream)を基にしています。
* UI・フロントエンド: 本プロジェクトのために独自に実装しているものです。

**開発方針と規約の遵守について:**

*   **開発方針の変更について**: 当初、本プロジェクトは完全な独自再現を目指し、オリジナル製品の使用を避けていました。しかし現在は、相互運用性の確保を最優先事項としています。そのため、GPL-3部分の開発において、動作検証やデータ互換性の確認のためにオリジナル製品を正規に利用しています。
*   **リバースエンジニアリングの禁止**: オリジナル製品の利用規約を遵守するため、プロプライエタリなバイナリに対するリバースエンジニアリング（逆コンパイル、逆アセンブル等）は一切行わずに開発しています。独自実装部分は、公開されているドキュメントおよびGPL-3ソースコード、そして正規利用による挙動の観測のみに基づいています。

本プロジェクトは非公式なものであり、Nine Gatesおよび「もちふぃった～」からのあらゆる承認、認可等も受けていません。

## ライセンス

本プロジェクトは GNU General Public License v3.0 (GPL-3) の下で公開されています。
詳細は LICENSE ファイルをご確認ください。