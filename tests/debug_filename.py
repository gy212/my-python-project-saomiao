# -*- coding: utf-8 -*-
import sys
import os
import re

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_sanitize_filename():
    """测试_sanitize_filename函数"""
    print("=== 测试 _sanitize_filename 函数 ===")
    
    # 模拟原始函数
    def old_sanitize_filename(filename):
        return re.sub(r'[^\w.\-]', '', filename)
    
    # 新的函数
    def new_sanitize_filename(filename):
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
    
    test_names = [
        "未知文件",
        "测试文档",
        "My Document",
        "文档<>:tests",
        "normal_file.txt"
    ]
    
    for name in test_names:
        old_result = old_sanitize_filename(name)
        new_result = new_sanitize_filename(name)
        print(f"原始: '{name}' -> 旧函数: '{old_result}' -> 新函数: '{new_result}'")
        print(f"  原始编码: {name.encode('utf-8')}")
        print(f"  旧函数编码: {old_result.encode('utf-8')}")
        print(f"  新函数编码: {new_result.encode('utf-8')}")
        print()

def test_path_encoding():
    """测试路径编码"""
    print("=== 测试路径编码 ===")
    
    test_path = r"C:\Users\21240\Desktop\测试文件.docx"
    print(f"原始路径: {test_path}")
    print(f"路径编码: {test_path.encode('utf-8')}")
    print(f"路径repr: {repr(test_path)}")
    
    # 测试路径规范化
    normalized = os.path.normpath(test_path)
    print(f"规范化路径: {normalized}")
    print(f"规范化编码: {normalized.encode('utf-8')}")
    print()

if __name__ == "__main__":
    test_sanitize_filename()
    test_path_encoding()