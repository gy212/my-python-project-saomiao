# -*- coding: utf-8 -*-
"""
file_exporter.pyw（更新版）

改动要点：
1) 使用 Pandoc 将 Markdown 导出为 DOCX 时，启用硬换行语义，确保单元格中的
   每条信息一行展示：-f gfm+pipe_tables+hard_line_breaks --wrap=none。
2) 保留 PDF 导出（基于 FPDF）的实现；如果你更希望用 Pandoc→PDF，可在
   save_to_pdf_pandoc 中启用（需要 xelatex 或等价引擎）。
3) (新) 统一的错误处理与日志记录。

依赖：
- 系统需存在随应用打包的 pandoc 可执行文件（resources/bin/<os>/pandoc*）。
- 可选：fpdf（pip install fpdf2）。
"""

from __future__ import annotations
import os
import platform
import subprocess
from typing import Tuple, Optional

try:
    from fpdf import FPDF
except Exception:
    FPDF = None  # 允许没有 fpdf 的环境，仅影响 save_to_pdf()

# 导入日志系统
try:
    from .logger import get_logger, get_error_handler, handle_exceptions
    logger = get_logger()
    error_handler = get_error_handler()
    logger.info("文件导出模块初始化完成")
except ImportError:
    # 兼容性处理：如果日志模块不存在，使用print作为fallback
    logger = None
    error_handler = None
    print("文件导出模块: 日志系统不可用，使用print作为fallback")

def _log_info(message):
    if logger:
        logger.info(message)
    else:
        print(f"INFO: {message}")

def _log_error(message):
    if logger:
        logger.error(message)
    else:
        print(f"ERROR: {message}")

def _log_debug(message):
    if logger:
        logger.debug(message)
    else:
        print(f"DEBUG: {message}")

# -----------------------------------------------------------------------------
# Pandoc 路径探测
# -----------------------------------------------------------------------------

def get_pandoc_path() -> str:
    """返回随应用打包的 Pandoc 路径；若未找到，尝试使用系统 PATH 中的 pandoc。
    你可根据自己的打包结构调整此函数。
    """
    _log_debug("开始查找Pandoc可执行文件")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 修正路径：从 src 目录向上一级到项目根目录，然后到 resources/bin
    project_root = os.path.dirname(base_dir)  # 从 src 目录向上一级
    res_dir = os.path.join(project_root, "resources", "bin")
    sysname = platform.system()
    _log_debug(f"系统类型: {sysname}, 基础目录: {base_dir}, 资源目录: {res_dir}")

    candidates = []
    if sysname == "Windows":
        candidates.append(os.path.join(res_dir, "windows", "pandoc.exe"))
        # 兜底：尝试从常见安装位置寻找
        candidates.append(r"C:\\Program Files\\Pandoc\\pandoc.exe")
    elif sysname == "Darwin":
        candidates.append(os.path.join(res_dir, "macos", "pandoc"))
        candidates.append("/opt/homebrew/bin/pandoc")
        candidates.append("/usr/local/bin/pandoc")
    else:  # Linux
        candidates.append(os.path.join(res_dir, "linux", "pandoc"))
        candidates.append("/usr/bin/pandoc")
        candidates.append("/usr/local/bin/pandoc")

    for p in candidates:
        if p and os.path.exists(p):
            _log_info(f"找到Pandoc可执行文件: {p}")
            return p

    # 最后尝试系统 PATH
    from shutil import which
    p = which("pandoc")
    if p:
        _log_info(f"在系统PATH中找到Pandoc: {p}")
    else:
        _log_error("未找到Pandoc可执行文件")
    return p or ""


# -----------------------------------------------------------------------------
# DOCX 导出（Pandoc）
# -----------------------------------------------------------------------------

def save_to_word(markdown_text: str, output_path: str) -> Tuple[bool, Optional[str]]:
    """使用 Pandoc 将 Markdown 转换为 DOCX。

    关键点：启用 "hard_line_breaks" 让 Markdown 中的换行在 Word 里变成硬换行，
    配合你在表格单元格内使用的 "两个空格+换行"（或普通换行），即可实现"每条信息一行"。

    返回 (ok, error_message)。ok=True 表示成功；失败时返回错误信息。
    """
    _log_info(f"开始导出Word文档: {os.path.basename(output_path)}")
    pandoc = get_pandoc_path()
    if not pandoc or not os.path.exists(pandoc):
        error_msg = f"未找到 Pandoc 可执行文件，请确认路径或安装：{pandoc or '[未检测到]'}"
        _log_error(error_msg)
        return False, error_msg

    try:
        _log_debug(f"使用Pandoc路径: {pandoc}")
        # Windows 上通过 shell=False 直接调用可执行文件
        # 说明：-f gfm+pipe_tables+hard_line_breaks 让 Pandoc 以 GitHub 风格表格并把换行视为硬换行
        #       --wrap=none 避免 Pandoc 自动重排换行
        # 确保输出路径使用正确的编码
        original_output_path = output_path
        try:
            # 在Windows上，确保路径使用正确的编码
            if platform.system() == "Windows":
                # 首先确保路径是正确的字符串格式
                if isinstance(output_path, bytes):
                    output_path = output_path.decode('utf-8', errors='replace')
                
                # 规范化路径
                output_path = os.path.normpath(output_path)
                _log_debug(f"规范化后的输出路径: {output_path}")
                _log_debug(f"输出路径编码: {output_path.encode('utf-8')}")
                
                # 检查输出目录是否存在，如果不存在则创建
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                    _log_debug(f"创建输出目录: {output_dir}")
                
                # 检查文件是否已存在且被占用，如果被占用则生成新的文件名
                original_output_path_for_conflict = output_path
                conflict_counter = 1
                while os.path.exists(output_path):
                    try:
                        # 尝试以写入模式打开文件来检查是否被占用
                        with open(output_path, 'a', encoding='utf-8'):
                            pass
                        # 如果能打开，说明文件没有被占用，可以覆盖
                        _log_debug(f"文件存在但未被占用，将覆盖: {output_path}")
                        break
                    except PermissionError:
                        # 文件被占用，生成新的文件名
                        base_name = os.path.splitext(original_output_path_for_conflict)[0]
                        ext = os.path.splitext(original_output_path_for_conflict)[1]
                        output_path = f"{base_name}({conflict_counter}){ext}"
                        conflict_counter += 1
                        _log_debug(f"文件被占用，尝试新文件名: {output_path}")
                        
                        # 防止无限循环
                        if conflict_counter > 100:
                            error_msg = f"无法找到可用的文件名，已尝试100次: {original_output_path_for_conflict}"
                            _log_error(error_msg)
                            return False, error_msg
                
                # 尝试使用短路径名避免中文路径问题
                try:
                    import win32api
                    # 获取短路径名
                    short_path = win32api.GetShortPathName(output_path)
                    _log_debug(f"使用短路径: {short_path}")
                    output_path = short_path
                except Exception as e:
                    _log_debug(f"获取短路径失败: {e}，使用原路径")
                    # 如果获取短路径失败，继续使用原路径
                    pass
        except ImportError:
            # 如果没有win32api，尝试其他方法
            _log_debug("win32api不可用，使用原路径")
            pass
        except Exception as e:
            _log_debug(f"路径处理异常: {e}，使用原路径")
            output_path = original_output_path
        
        args = [
            pandoc,
            "-f", "gfm+pipe_tables+hard_line_breaks",
            "-t", "docx",
            "--wrap=none",
            "-o", output_path,
        ]
        _log_debug(f"Pandoc命令参数: {' '.join(args)}")
        _log_debug(f"最终输出路径: {output_path}")
        _log_debug(f"最终输出路径编码: {output_path.encode('utf-8')}")
        
        # 设置环境变量以确保正确的编码处理
        env = dict(os.environ, PYTHONIOENCODING='utf-8', LANG='zh_CN.UTF-8') if platform.system() == "Windows" else None
        
        proc = subprocess.run(
            args,
            input=markdown_text.encode("utf-8"),
            capture_output=True,
            check=False,
            env=env,
        )
        
        _log_debug(f"Pandoc返回码: {proc.returncode}")
        if proc.stdout:
            _log_debug(f"Pandoc标准输出: {proc.stdout.decode('utf-8', errors='ignore')}")
        if proc.stderr:
            _log_debug(f"Pandoc标准错误: {proc.stderr.decode('utf-8', errors='ignore')}")
        
        if proc.returncode != 0:
            stderr = (proc.stderr or b"").decode("utf-8", errors="ignore")
            error_msg = f"Pandoc 转换失败（exit={proc.returncode}）：{stderr}"
            _log_error(error_msg)
            return False, error_msg
        
        # 验证文件是否真的创建成功
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            _log_info(f"Word文档导出成功: {output_path} (大小: {file_size} 字节)")
            return True, None
        else:
            error_msg = f"Pandoc执行成功但文件未创建: {output_path}"
            _log_error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"调用 Pandoc 时出现异常：{e}"
        _log_error(error_msg)
        import traceback
        _log_debug(f"异常详情: {traceback.format_exc()}")
        return False, error_msg


# -----------------------------------------------------------------------------
# PDF 导出（简易文本→PDF，保持与你原流程兼容）
# -----------------------------------------------------------------------------

def save_to_pdf(plain_text: str, output_path: str, font_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """使用 FPDF 以"纯文本"导出 PDF 的实现（不解析 Markdown）。
    若要高质量 Markdown→PDF，请考虑使用 Pandoc + xelatex，见下方注释函数。
    """
    _log_info(f"开始导出PDF文档: {os.path.basename(output_path)}")
    if FPDF is None:
        error_msg = "未安装 fpdf（fpdf2）。请 pip install fpdf2，或改用 Pandoc→PDF。"
        _log_error(error_msg)
        return False, error_msg

    try:
        _log_debug("初始化FPDF实例")
        pdf = FPDF()
        pdf.add_page()
        # 字体：尽量载入中文字体，找不到则使用内置字体（会丢失中文）。
        if font_path and os.path.exists(font_path):
            _log_debug(f"使用自定义字体: {font_path}")
            pdf.add_font("Custom", fname=font_path, uni=True)
            pdf.set_font("Custom", size=12)
        else:
            _log_debug("尝试使用系统中文字体")
            try:
                # 假设系统内有常见中文字体
                for fp in [
                    r"C:\\Windows\\Fonts\\simhei.ttf",
                    r"C:\\Windows\\Fonts\\msyh.ttc",
                    "/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/STHeiti Light.ttc",
                    "/usr/share/fonts/truetype/arphic/ukai.ttc",
                ]:
                    if os.path.exists(fp):
                        pdf.add_font("Custom", fname=fp, uni=True)
                        pdf.set_font("Custom", size=12)
                        break
                else:
                    pdf.set_font("Arial", size=12)  # 兜底
            except Exception:
                pdf.set_font("Arial", size=12)

        # 简单写入（不支持 Markdown 样式 / 表格）
        for line in plain_text.splitlines():
            pdf.multi_cell(0, 8, line)
        pdf.output(output_path)
        return True, None
    except Exception as e:
        return False, f"生成 PDF 失败：{e}"


# -----------------------------------------------------------------------------
# （可选）Pandoc 直接导出 PDF（需要 xelatex）
# -----------------------------------------------------------------------------

def save_to_pdf_pandoc(markdown_text: str, output_path: str, cjk_mainfont: str = "SimSun") -> Tuple[bool, Optional[str]]:
    """使用 Pandoc + xelatex 将 Markdown 转为 PDF（可获得更好的表格/公式效果）。
    注意：需要系统或打包内包含 LaTeX 引擎（xelatex）。
    """
    pandoc = get_pandoc_path()
    if not pandoc or not os.path.exists(pandoc):
        return False, f"未找到 Pandoc 可执行文件，请确认路径或安装：{pandoc or '[未检测到]'}"

    try:
        args = [
            pandoc,
            "-f", "gfm+pipe_tables+hard_line_breaks",
            "-t", "pdf",
            "--pdf-engine=xelatex",
            "--variable", f"CJKmainfont={cjk_mainfont}",
            "--wrap=none",
            "-o", output_path,
        ]
        proc = subprocess.run(
            args,
            input=markdown_text.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or b"").decode("utf-8", errors="ignore")
            return False, f"Pandoc→PDF 失败（exit={proc.returncode}）：{stderr}"
        return True, None
    except Exception as e:
        return False, f"调用 Pandoc（PDF）时出现异常：{e}"


__all__ = [
    "get_pandoc_path",
    "save_to_word",
    "save_to_pdf",
    "save_to_pdf_pandoc",
]
