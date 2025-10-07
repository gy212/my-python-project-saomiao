# -*- coding: utf-8 -*-
import subprocess
import os
import sys
import tempfile

def test_pandoc_encoding():
    """测试Pandoc调用时的编码问题"""
    
    # 测试文本
    test_content = "# 测试文档\n\n这是一个测试文档，包含中文内容。"
    
    # 测试路径
    test_paths = [
        "测试文档.docx",
        "未知文件.docx", 
        "中文测试123.docx"
    ]
    
    for test_filename in test_paths:
        print(f"\n=== 测试文件名: {test_filename} ===")
        print(f"文件名编码: {test_filename.encode('utf-8')}")
        print(f"文件名repr: {repr(test_filename)}")
        
        # 创建临时输出路径
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, test_filename)
        print(f"输出路径: {output_path}")
        print(f"输出路径编码: {output_path.encode('utf-8')}")
        print(f"输出路径repr: {repr(output_path)}")
        
        # 创建临时输入文件
        input_file = os.path.join(temp_dir, "temp_input.md")
        try:
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            # 构建Pandoc命令 - 使用项目中的Pandoc
            pandoc_exe = os.path.join(os.path.dirname(__file__), "resources", "bin", "windows", "pandoc.exe")
            pandoc_cmd = [
                pandoc_exe,
                input_file,
                "-o", output_path,
                "--from", "markdown",
                "--to", "docx"
            ]
            
            print(f"Pandoc命令: {pandoc_cmd}")
            print(f"命令参数编码:")
            for i, arg in enumerate(pandoc_cmd):
                print(f"  [{i}] {repr(arg)} -> {arg.encode('utf-8')}")
            
            # 设置环境变量
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # 执行Pandoc命令
            try:
                result = subprocess.run(
                    pandoc_cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    env=env,
                    timeout=30
                )
                
                print(f"返回码: {result.returncode}")
                if result.stdout:
                    print(f"标准输出: {result.stdout}")
                if result.stderr:
                    print(f"标准错误: {result.stderr}")
                
                # 检查输出文件是否存在
                if os.path.exists(output_path):
                    print("✅ 文件创建成功")
                    file_size = os.path.getsize(output_path)
                    print(f"文件大小: {file_size} 字节")
                    # 清理文件
                    os.remove(output_path)
                else:
                    print("❌ 文件创建失败")
                    
            except subprocess.TimeoutExpired:
                print("❌ Pandoc执行超时")
            except Exception as e:
                print(f"❌ Pandoc执行异常: {e}")
                import traceback
                traceback.print_exc()
            
            # 清理输入文件
            if os.path.exists(input_file):
                os.remove(input_file)
                
        except Exception as e:
            print(f"❌ 创建临时文件失败: {e}")

if __name__ == "__main__":
    test_pandoc_encoding()