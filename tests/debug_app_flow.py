# -*- coding: utf-8 -*-
import sys
import os
import re

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def simulate_app_flow():
    """模拟应用程序中的完整文件保存流程"""
    
    print("=== 模拟应用程序文件保存流程 ===")
    
    # 1. 模拟OCR结果
    ocr_result = {
        'file_name': '未知文件.jpg',
        'extracted_text': '# 测试文档\n\n这是一个测试文档，包含中文内容。'
    }
    
    print(f"1. OCR结果文件名: {ocr_result['file_name']}")
    print(f"   文件名编码: {ocr_result['file_name'].encode('utf-8')}")
    
    # 2. 模拟_sanitize_filename函数
    def _sanitize_filename(filename):
        """模拟main_api.pyw中的_sanitize_filename函数"""
        import string
        forbidden_chars = '<>:"|?*\\/'
        control_chars = ''.join(chr(i) for i in range(32))
        
        sane_name = filename
        for char in forbidden_chars + control_chars:
            sane_name = sane_name.replace(char, '')
        
        sane_name = sane_name.strip(' .')
        
        if not sane_name:
            return "scanned_document"
        
        if len(sane_name) > 200:
            sane_name = sane_name[:200]
            
        return sane_name
    
    # 3. 处理文件名
    file_name = ocr_result.get('file_name', '未知文件')
    base_name = os.path.splitext(file_name)[0]
    sanitized_base_name = _sanitize_filename(base_name)
    default_filename = f"{sanitized_base_name}.docx"
    
    print(f"2. 原始文件名: {file_name}")
    print(f"   基础名称: {base_name}")
    print(f"   清理后名称: {sanitized_base_name}")
    print(f"   默认文件名: {default_filename}")
    print(f"   默认文件名编码: {default_filename.encode('utf-8')}")
    
    # 4. 模拟文件对话框返回的路径
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    simulated_save_path = os.path.join(desktop_path, default_filename)
    
    print(f"3. 模拟保存路径: {simulated_save_path}")
    print(f"   保存路径编码: {simulated_save_path.encode('utf-8')}")
    print(f"   保存路径repr: {repr(simulated_save_path)}")
    
    # 5. 模拟路径处理（来自file_exporter.pyw）
    def process_path_for_pandoc(output_path):
        """模拟file_exporter.pyw中的路径处理"""
        try:
            # 确保路径是字符串
            if isinstance(output_path, (list, tuple)):
                output_path = output_path[0]
            
            # 规范化路径
            output_path = os.path.normpath(str(output_path))
            print(f"   规范化后路径: {output_path}")
            print(f"   规范化后编码: {output_path.encode('utf-8')}")
            
            # 尝试获取短路径名（Windows）
            try:
                import win32api
                short_path = win32api.GetShortPathName(output_path)
                print(f"   短路径: {short_path}")
                print(f"   短路径编码: {short_path.encode('utf-8')}")
                return short_path
            except Exception as e:
                print(f"   获取短路径失败: {e}")
                return output_path
                
        except Exception as e:
            print(f"   路径处理异常: {e}")
            return output_path
    
    processed_path = process_path_for_pandoc(simulated_save_path)
    
    # 6. 模拟Pandoc调用
    def simulate_pandoc_call(content, output_path):
        """模拟Pandoc调用"""
        import tempfile
        import subprocess
        
        print(f"4. 准备调用Pandoc:")
        print(f"   输出路径: {output_path}")
        print(f"   输出路径编码: {output_path.encode('utf-8')}")
        print(f"   输出路径repr: {repr(output_path)}")
        
        # 创建临时输入文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            input_file = f.name
        
        try:
            # 构建Pandoc命令
            pandoc_exe = os.path.join(os.path.dirname(__file__), "resources", "bin", "windows", "pandoc.exe")
            pandoc_cmd = [
                pandoc_exe,
                input_file,
                "-o", output_path,
                "--from", "gfm+pipe_tables+hard_line_breaks",
                "--to", "docx",
                "--wrap=none"
            ]
            
            print(f"   Pandoc命令: {pandoc_cmd}")
            
            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # 执行命令
            result = subprocess.run(
                pandoc_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                timeout=30
            )
            
            print(f"   返回码: {result.returncode}")
            if result.stdout:
                print(f"   标准输出: {result.stdout}")
            if result.stderr:
                print(f"   标准错误: {result.stderr}")
            
            # 检查文件是否创建成功
            if os.path.exists(output_path):
                print("   ✅ 文件创建成功")
                file_size = os.path.getsize(output_path)
                print(f"   文件大小: {file_size} 字节")
                # 清理文件
                os.remove(output_path)
                return True, None
            else:
                print("   ❌ 文件创建失败")
                return False, "文件未创建"
                
        except Exception as e:
            print(f"   ❌ Pandoc执行异常: {e}")
            return False, str(e)
        finally:
            # 清理临时文件
            if os.path.exists(input_file):
                os.remove(input_file)
    
    # 执行模拟调用
    success, error = simulate_pandoc_call(ocr_result['extracted_text'], processed_path)
    
    print(f"\n=== 流程结果 ===")
    print(f"成功: {success}")
    if error:
        print(f"错误: {error}")

if __name__ == "__main__":
    simulate_app_flow()