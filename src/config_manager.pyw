# -----------------------------------------------------------------------------
# 功能: 配置文件及历史记录管理器
# 职责:
# 1. 统一定义所有全局常量 (API地址, 文件名, 字体路径等)。
# 2. 提供函数来加载和保存JSON配置文件 (如api_key)。
# 3. 提供函数来加载、保存和更新扫描历史记录。
# -----------------------------------------------------------------------------

import json
import os
from datetime import datetime

# --- Constants ---
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.json")
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "scan_history.json")
MAX_RECENT_SCANS = 10

# Doubao API Config
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DOUBAO_MODEL = "doubao-1-5-vision-pro-32k-250115"

# Font Config for PDF Exporter
POSSIBLE_FONT_PATHS = [
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "arialuni.ttf"
]
CHINESE_FONT_PATH = None
for p in POSSIBLE_FONT_PATHS:
    if os.path.exists(p):
        CHINESE_FONT_PATH = p
        print(f"PDF将使用中文字体: {CHINESE_FONT_PATH}")
        break
if not CHINESE_FONT_PATH:
    print("警告: 未找到预设的中文字体路径，PDF中的中文可能无法正确显示。")

# --- Generic JSON Data Handlers ---
def load_config_data(file_path, default_value=None):
    """从JSON文件加载数据，处理可能发生的错误。"""
    if default_value is None:
        default_value = {}
    
    print(f"[DEBUG] 尝试加载配置文件: {file_path}")
    print(f"[DEBUG] 文件是否存在: {os.path.exists(file_path)}")
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 只对字典类型数据打印API密钥信息
                if isinstance(data, dict) and 'api_key' in data:
                    print(f"[DEBUG] 成功加载配置文件，API密钥长度: {len(data.get('api_key', ''))}")
                else:
                    print(f"[DEBUG] 成功加载配置文件，数据类型: {type(data).__name__}")
                return data
        except (IOError, json.JSONDecodeError) as e:
            print(f"从 {file_path} 加载数据失败: {e}")
    else:
        print(f"[DEBUG] 配置文件不存在，使用默认值: {default_value}")
    return default_value

def save_config_data(file_path, data):
    """将数据保存到JSON文件。"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"数据已保存到 {file_path}")
    except IOError as e:
        print(f"保存数据到 {file_path} 失败: {e}")

# --- Scan History Handlers ---
def load_scan_history():
    """加载扫描历史记录。"""
    history_data = load_config_data(HISTORY_FILE, [])
    if not isinstance(history_data, list):
        return []
    return history_data[:MAX_RECENT_SCANS]

def save_scan_history(history_list):
    """保存整个扫描历史列表。"""
    save_config_data(HISTORY_FILE, history_list)

def add_scan_to_history(history_list, image_name, output_name, output_format_ext, saved_file_full_path):
    """向历史记录列表添加一个新条目并保存。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_entry = {
        "image_name": image_name,
        "output_name": output_name,
        "output_format": output_format_ext,
        "timestamp": timestamp,
        "saved_file_full_path": saved_file_full_path
    }
    history_list.insert(0, scan_entry)
    if len(history_list) > MAX_RECENT_SCANS:
        history_list.pop()
    save_scan_history(history_list)
    print(f"已添加扫描记录: {image_name} -> {output_name}")

