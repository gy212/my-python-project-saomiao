# -*- coding: utf-8 -*-
import webview
import os
import sys

def test_file_dialog():
    """测试文件对话框的编码问题"""
    
    def on_window_loaded():
        print("窗口已加载，开始测试文件对话框...")
        
        # 测试不同的文件名
        test_filenames = [
            "未知文件.docx",
            "测试文档.docx", 
            "My Document.docx",
            "中文测试123.docx"
        ]
        
        for filename in test_filenames:
            print(f"\n=== 测试文件名: {filename} ===")
            print(f"原始文件名编码: {filename.encode('utf-8')}")
            print(f"原始文件名repr: {repr(filename)}")
            
            try:
                # 调用文件保存对话框
                save_path = window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=filename
                )
                
                if save_path:
                    path_str = save_path[0] if isinstance(save_path, tuple) else save_path
                    print(f"返回路径: {path_str}")
                    print(f"返回路径类型: {type(path_str)}")
                    print(f"返回路径编码: {path_str.encode('utf-8')}")
                    print(f"返回路径repr: {repr(path_str)}")
                    
                    # 提取文件名部分
                    returned_filename = os.path.basename(path_str)
                    print(f"提取的文件名: {returned_filename}")
                    print(f"提取的文件名编码: {returned_filename.encode('utf-8')}")
                    print(f"提取的文件名repr: {repr(returned_filename)}")
                    
                    # 检查是否有乱码
                    if '?' in returned_filename or 'δ' in returned_filename or '֪' in returned_filename:
                        print("⚠️ 检测到可能的乱码字符!")
                    else:
                        print("✅ 文件名看起来正常")
                        
                else:
                    print("用户取消了对话框")
                    
            except Exception as e:
                print(f"错误: {e}")
                import traceback
                traceback.print_exc()
        
        # 测试完成后关闭窗口
        print("\n测试完成，3秒后关闭窗口...")
        import threading
        def close_window():
            import time
            time.sleep(3)
            window.destroy()
        threading.Thread(target=close_window).start()
    
    # 创建窗口
    window = webview.create_window(
        '文件对话框编码测试',
        html='<h1>文件对话框编码测试</h1><p>请查看控制台输出</p>',
        width=400,
        height=300
    )
    
    # 启动应用
    webview.start(on_window_loaded, debug=True)

if __name__ == "__main__":
    test_file_dialog()