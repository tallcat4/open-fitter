import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import argparse

import bpy
from parse_args import parse_args
from process_single_config import OutfitRetargetPipeline


def main():
    try:
        import time
        start_time = time.time()

        sys.stdout.reconfigure(line_buffering=True)
        
        print(f"Status: アドオン有効化中")
        print(f"Progress: 0.01")
        bpy.ops.preferences.addon_enable(module='robust-weight-transfer')
        print(f"Addon enabled: {time.time() - start_time:.2f}秒")

        # Parse command line arguments
        print(f"Status: 引数解析中")
        print(f"Progress: 0.02")
        args = parse_args()
        parse_time = time.time()
        print(f"引数解析: {parse_time - start_time:.2f}秒")

        # Process each config pair
        total_pairs = len(args.config_pairs)
        successful_pairs = 0
        
        for pair_index, config_pair in enumerate(args.config_pairs):
            try:
                print(f"\n{'='*60}")
                print(f"処理開始: ペア {pair_index + 1}/{total_pairs}")
                print(f"Base FBX: {config_pair['base_fbx']}")
                print(f"Config: {config_pair['config_path']}")
                print(f"{'='*60}")
                
                # Create output filename with index for multiple pairs
                # if total_pairs > 1:
                #     base_output = args.output.rsplit('.', 1)[0]
                #     extension = args.output.rsplit('.', 1)[1] if '.' in args.output else 'fbx'
                #     output_file = f"{base_output}_{pair_index + 1:03d}.{extension}"
                # else:
                #     output_file = args.output
                output_file = args.output
                
                # Create a copy of args with updated output path
                pair_args = argparse.Namespace(**vars(args))
                pair_args.output = output_file
                
                pipeline = OutfitRetargetPipeline(
                    pair_args, config_pair, pair_index, total_pairs, start_time
                )
                success = pipeline.execute()
                if success:
                    successful_pairs += 1
                    print(f"✓ ペア {pair_index + 1} 正常完了: {output_file}")
                else:
                    print(f"✗ ペア {pair_index + 1} 処理失敗")
                    break
            except Exception as e:
                import traceback
                print(f"✗ ペア {pair_index + 1} でエラーが発生しました:")
                print("============= Error Details =============")
                print(f"Error message: {str(e)}")
                print("\n============= Full Stack Trace =============")
                print(traceback.format_exc())
                print("==========================================")
                
                # Save error scene
                try:
                    error_output = args.output.rsplit('.', 1)[0] + f'_error_{pair_index + 1:03d}.blend'
                    bpy.ops.wm.save_as_mainfile(filepath=error_output)
                    print(f"エラー時のシーンを保存: {error_output}")
                except:
                    pass
        
        total_time = time.time() - start_time
        print(f"Progress: 1.00")
        print(f"\n{'='*60}")
        print(f"全体処理完了")
        print(f"成功: {successful_pairs}/{total_pairs} ペア")
        print(f"合計時間: {total_time:.2f}秒")
        print(f"{'='*60}")
        
        return successful_pairs == total_pairs
        
    except Exception as e:
        import traceback
        print("============= Fatal Error =============")
        print(f"Error message: {str(e)}")
        print("\n============= Full Stack Trace =============")
        print(traceback.format_exc())
        print("=====================================")
        return False

if __name__ == "__main__":
    main()
