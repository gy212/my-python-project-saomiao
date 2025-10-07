# -----------------------------------------------------------------------------
# 功能: 应用程序主入口 (优化版)
# 优化内容:
# 1. 关闭debug模式提升启动速度
# 2. 优化窗口创建参数
# 3. 添加启动时间监控
# -----------------------------------------------------------------------------

import sys
import os
import time
import webview
from pathlib import Path

# 记录启动时间
start_time = time.time()

# --- 解决模块导入问题的关键代码 ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 延迟导入，提升启动速度
from src.main_api import Api

if __name__ == '__main__':
    # 创建API实例
    api_instance = Api()

    ui_file = Path(__file__).resolve().parent / 'ui' / 'ui.html'
    if not ui_file.exists():
        raise FileNotFoundError(f'UI 文件未找到: {ui_file}')

    # 创建窗口，优化参数减少启动开销
    window = webview.create_window(
        'LLM 图像扫描与导出 (Pywebview)',
        ui_file.as_uri(),
        js_api=api_instance,
        width=1250,
        height=850,
        resizable=True,
        confirm_close=True,
        # 性能优化参数
        shadow=True,
        text_select=False  # 减少初始化开销
    )

    # 将窗口实例回传给API类
    api_instance._window = window
    
    # 计算初始化时间
    init_time = time.time() - start_time
    print(f"应用初始化完成，耗时: {init_time:.2f}秒")

    # 启动应用，关闭debug模式提升性能
    webview.start(debug=False)

