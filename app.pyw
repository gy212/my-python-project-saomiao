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


def main():
    """应用程序主函数"""
    api_instance = Api()

    ui_file = Path(__file__).resolve().parent / 'ui' / 'ui.html'
    if not ui_file.exists():
        raise FileNotFoundError(f'UI 文件未找到: {ui_file}')

    window = webview.create_window(
        'LLM 图像扫描与导出 (PyWebView)',
        ui_file.as_uri(),
        js_api=api_instance,
        width=1250,
        height=850,
        resizable=True,
        confirm_close=True,
        shadow=True,
        text_select=False,
        hidden=True
    )

    api_instance._window = window

    def handle_window_loaded():
        """前端加载完成后再显示窗口，确保界面一次性呈现"""
        init_duration = time.time() - start_time
        print(f"前端加载完成，耗时: {init_duration:.2f}s")
        try:
            window.evaluate_js("window.dispatchEvent(new Event('pywebviewready'))")
        except Exception as exc:
            print(f"派发前端就绪事件失败: {exc}")
        window.show()

    window.events.loaded += handle_window_loaded

    webview.start(debug=False)


if __name__ == '__main__':
    main()
