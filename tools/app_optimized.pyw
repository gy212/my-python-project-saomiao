# -----------------------------------------------------------------------------
# 功能: 应用程序主入口 (性能优化版)
# 优化内容:
# 1. 添加启动时间测量
# 2. 优化窗口创建参数
# 3. 减少debug模式的开销
# 4. 添加启动进度反馈
# -----------------------------------------------------------------------------

import sys
import os
import time
import webview

# 记录启动时间
start_time = time.time()

# --- 解决模块导入问题的关键代码 ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("正在初始化应用程序...")

# 延迟导入主API模块
from main_api import Api

def create_optimized_window():
    """创建优化的窗口配置"""
    print("正在创建API实例...")
    api_instance = Api()
    
    print("正在创建应用窗口...")
    # 优化窗口参数，减少启动开销
    window = webview.create_window(
        'LLM 图像扫描与导出 (Pywebview)',
        'ui.html',
        js_api=api_instance,
        width=1250,
        height=850,
        resizable=True,
        confirm_close=True,
        # 优化参数
        shadow=True,
        on_top=False,
        minimized=False,
        fullscreen=False,
        # 减少初始化开销
        text_select=False
    )
    
    # 将窗口实例回传给API类
    api_instance._window = window
    
    return window

if __name__ == '__main__':
    try:
        window = create_optimized_window()
        
        # 计算启动时间
        init_time = time.time() - start_time
        print(f"应用初始化完成，耗时: {init_time:.2f}秒")
        
        # 启动应用，生产环境关闭debug模式以提升性能
        print("正在启动应用界面...")
        webview.start(debug=False)  # 关闭debug模式提升性能
        
    except Exception as e:
        print(f"应用启动失败: {e}")
        input("按回车键退出...")