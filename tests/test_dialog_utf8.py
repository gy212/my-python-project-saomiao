# -*- coding: utf-8 -*-
import webview
import os

def test_file_dialog():
    # 创建一个简单的窗口
    window = webview.create_window("Test", "data:text/html,<h1>Test</h1>", width=400, height=300)
    
    # 测试文件保存对话框
    def test_save():
        save_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="测试文件.docx"
        )
        print(f"保存路径: {save_path}")
        print(f"路径类型: {type(save_path)}")
        if save_path:
            path_str = save_path[0] if isinstance(save_path, tuple) else save_path
            print(f"路径字符串: {path_str}")
            print(f"路径编码: {path_str.encode('utf-8')}")
            print(f"路径repr: {repr(path_str)}")
    
    # 延迟执行测试
    webview.start(test_save, debug=True)

if __name__ == "__main__":
    test_file_dialog()