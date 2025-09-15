# -----------------------------------------------------------------------------
# 功能: OCR 服务模块
# 职责:
# 1. 封装与豆包（Doubao）视觉API的所有交互。
# 2. 将图片文件转换为Base64编码。
# 3. 发送API请求并解析返回的文本结果。
# 4. (新) 接收预提取的表格，指导LLM进行内容整合。
# 5. (新) 统一的错误处理与日志记录。
# -----------------------------------------------------------------------------

import base64
import json
import mimetypes
import os
import requests
from . import config_manager as cfg
from .logger import get_logger, get_error_handler, handle_exceptions
from .cache_manager import get_cache_manager, CacheConfig
from .error_manager import get_error_manager, enhanced_handle_exceptions
from .performance_monitor import get_performance_monitor, performance_monitor


class OcrService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.logger = get_logger()
        self.error_handler = get_error_handler()
        
        # 调试日志
        self.logger.info(f"[DEBUG] OCR服务初始化，接收到API密钥长度: {len(api_key) if api_key else 0}")
        
        # 集成错误管理器和性能监控器
        self.error_manager = get_error_manager()
        self.performance_monitor = get_performance_monitor()
        
        # 使用新的缓存管理器
        cache_config = CacheConfig()
        cache_config.max_memory_cache_size = 200  # OCR结果缓存更多项
        cache_config.memory_cache_ttl = 7200  # 2小时TTL
        cache_config.disk_cache_ttl = 86400 * 3  # 磁盘缓存3天
        self.cache_manager = get_cache_manager(cache_config)
        
        # 保留旧的缓存接口以兼容现有代码
        self.extracted_text_cache = {}
        self.logger.info("OCR服务初始化完成，已集成错误管理和性能监控")

    def set_api_key(self, api_key):
        self.api_key = api_key
        self.logger.info(f"OCR服务: API密钥已更新 (长度: {len(api_key) if api_key else 0})")

    def clear_text_cache(self):
        """清除OCR服务的文本缓存"""
        # 清理新缓存管理器
        self.cache_manager.clear("memory")
        
        # 清理旧缓存（兼容性）
        cache_size = len(self.extracted_text_cache)
        self.extracted_text_cache.clear()
        
        self.logger.info(f"OCR缓存已清理，清理了 {cache_size} 个旧缓存项")
        
        # 获取缓存统计
        stats = self.cache_manager.get_stats()
        self.logger.info(f"缓存统计: 总请求={stats['total_requests']}, "
                        f"命中率={stats['overall_hit_rate']:.1f}%, "
                        f"缓存大小={stats['cache_size_mb']:.2f}MB")

    def image_to_base64_data_uri(self, image_path):
        try:
            self.logger.debug(f"开始转换图片为Base64: {os.path.basename(image_path)}")
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image'): 
                self.logger.warning(f"不支持的图片格式: {image_path}, MIME类型: {mime_type}")
                return None
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            self.logger.debug(f"图片转换成功: {os.path.basename(image_path)}, 大小: {len(encoded_string)} 字符")
            return f"data:{mime_type};base64,{encoded_string}"
        except Exception as e:
            self.logger.error(f"图片转Base64失败: {image_path}, 错误: {e}")
            return None

    @enhanced_handle_exceptions("extract_text_from_image")
    @performance_monitor("extract_text_from_image")
    def extract_text_from_image(self, image_path, markdown_tables: list[str] = None):
        """
        使用豆包API提取文本。
        如果提供了表格，会指导LLM识别表格以外的内容并进行整合。
        """
        self.logger.info(f"开始OCR文本提取: {os.path.basename(image_path)}")
        
        # 生成缓存键（包含文件路径、修改时间和表格信息）
        try:
            file_mtime = os.path.getmtime(image_path)
            cache_key_data = {
                'image_path': image_path,
                'file_mtime': file_mtime,
                'markdown_tables': markdown_tables or []
            }
        except OSError:
            # 如果无法获取文件修改时间，使用文件路径和表格信息
            cache_key_data = {
                'image_path': image_path,
                'markdown_tables': markdown_tables or []
            }
        
        # 尝试从新缓存管理器获取结果
        cached_result = self.cache_manager.get(cache_key_data)
        if cached_result is not None:
            self.logger.debug(f"使用缓存的OCR结果: {os.path.basename(image_path)}")
            return {"status": "成功", "text": cached_result}
        
        # 兼容旧缓存系统
        old_cache_key = (image_path, tuple(markdown_tables) if markdown_tables else ())
        if old_cache_key in self.extracted_text_cache:
            self.logger.debug(f"使用旧缓存的OCR结果: {os.path.basename(image_path)}")
            result_text = self.extracted_text_cache[old_cache_key]
            # 将结果存储到新缓存系统
            self.cache_manager.put(cache_key_data, result_text)
            return {"status": "成功", "text": result_text}

        if not self.api_key:
            self.logger.error("OCR处理失败: API密钥未设置")
            return self.error_handler.handle_validation_error("API密钥未设置")

        data_uri = self.image_to_base64_data_uri(image_path)
        if not data_uri:
            error_msg = f"无法处理图片文件: {os.path.basename(image_path)}"
            self.logger.error(error_msg)
            return self.error_handler.handle_validation_error(error_msg)

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        # --- 根据是否存在表格，动态生成Prompt ---
        if markdown_tables:
            # 将表格列表合并为一个字符串块，以便注入Prompt
            tables_block = "\n\n---\n\n".join(markdown_tables)
            prompt_text = f"""
# 角色
你是一个文档整合专家。你的任务是将已经识别出的表格，与图片中的其余文本内容，按原始顺序完美地组合成一份完整的Markdown文档。

# 已知信息
我已经使用专业的表格识别工具从图片中提取出了以下表格，格式为Markdown：
```markdown
{tables_block}
```

# 你的任务
1.  仔细分析我提供的原始图片。
2.  识别并提取图片中 **除了上述表格之外** 的所有其他文本内容（如标题、段落、公式、列表等）。
3.  将你提取的文本内容，与我提供给你的表格，按照它们在原始图片中的**先后顺序**，重新组合成一份**完整、连贯**的Markdown文档。
4.  在处理非表格部分的公式时，请严格遵守以下规则：
    * 所有独立成行的、居中的数学公式，**必须**使用 `$$...$$` 包裹（前后各留一个空行）。
    * 所有嵌入在文本行内的数学符号或短公式，**必须**使用 `$...$` 包裹。
    * **严禁**使用 r`\[ ... \]`、r`\( ... \)`、r`\\[ ... \\]` 或 r`\\( ... \\)` 等LaTeX原生格式。
    * 确保数学公式内容正确转义，避免使用可能导致Pandoc解析错误的特殊字符。

请现在开始处理，并输出最终那份完整的Markdown文档。
"""
        else:
            prompt_text = r"""
# 角色
你是一个精通学术文档分析的AI助手，擅长将图像内容精确地转换为结构化的Markdown文本。
# 任务
请仔细分析我提供的图片，并将其中的所有内容转换为一个Pandoc兼容的Markdown文件。
# 输出规则
1.  **文本格式**: 保持原始的段落、标题、列表等格式。
2.  **表格与公式**:
    * 如果图片中有表格，请使用标准的Markdown格式进行转换。
    * 所有独立成行的、居中的数学公式，**必须**使用 `$$...$$` 包裹（前后各留一个空行）。
    * 所有嵌入在文本行内的数学符号或短公式，**必须**使用 `$...$` 包裹。
    * **严禁**使用 `\\[ ... \\]`、`\\( ... \\)`、`\\\\[ ... \\\\]` 或 `\\\\( ... \\\\)` 等LaTeX原生格式。
    * 确保数学公式内容正确转义，避免使用可能导致Pandoc解析错误的特殊字符。
3.  **完整性**: 确保输出的Markdown文本是完整且可以直接使用的。
请现在处理以下图片：
"""

        payload = {
            "model": cfg.DOUBAO_MODEL,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text},
                                                      {"type": "image_url", "image_url": {"url": data_uri}}]}]
        }

        try:
            self.logger.debug(f"发送OCR API请求: {os.path.basename(image_path)}")
            response = requests.post(cfg.DOUBAO_API_URL, headers=headers, data=json.dumps(payload), timeout=90)  # 延长超时
            response_text_for_debug = response.text
            self.logger.debug(f"收到API响应: 状态码 {response.status_code}")
            response.raise_for_status()
            response_data = response.json()

            if response_data.get("choices") and response_data["choices"][0].get("message"):
                content = response_data["choices"][0].get("message").get("content")
                if content:
                    extracted_text = content[0].get("text", "") if isinstance(content, list) else str(content)
                    
                    # 存储到新缓存管理器
                    self.cache_manager.put(cache_key_data, extracted_text)
                    
                    # 兼容旧缓存系统
                    old_cache_key = (image_path, tuple(markdown_tables) if markdown_tables else ())
                    self.extracted_text_cache[old_cache_key] = extracted_text
                    
                    self.logger.info(f"OCR文本提取成功: {os.path.basename(image_path)}, 文本长度: {len(extracted_text)}")
                    return {"status": "成功", "text": extracted_text}

            self.logger.error(f"API响应格式不正确: {response_data}")
            return {"status": "失败", "error": "API响应格式不正确或无有效内容。", "details": response_data}

        except requests.exceptions.HTTPError as http_err:
            error_msg = f"API请求HTTP错误: {http_err.response.status_code}"
            self.logger.error(f"OCR API HTTP错误: {error_msg}, 响应: {response_text_for_debug}")
            return {"status": "失败", "error": error_msg, "details": response_text_for_debug}
        except requests.exceptions.RequestException as req_err:
            error_msg = f"API请求失败: {req_err}"
            self.logger.error(f"OCR API请求异常: {error_msg}")
            return {"status": "失败", "error": error_msg}
        except Exception as e:
            error_msg = f"处理时发生未知错误: {str(e)}"
            self.logger.error(f"OCR处理未知错误: {error_msg}")
            return {"status": "失败", "error": error_msg}

