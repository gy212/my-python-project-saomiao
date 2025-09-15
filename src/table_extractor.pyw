# -----------------------------------------------------------------------------
# 功能: 表格提取器模块（兼容补丁）
# 说明: 解决部分 img2table 版本不支持 Image.extract_tables(ocr_config=...) 导致的
#       TypeError: unexpected keyword argument 'ocr_config'。
# 做法: 先尝试带 ocr_config 调用；如果抛 TypeError（或签名不匹配），
#       自动回退到不带该参数的调用，功能不受影响。
# -----------------------------------------------------------------------------

from img2table.document import Image
from img2table.ocr import TesseractOCR
import pandas as pd


def extract_tables_as_markdown(image_path: str) -> list[str]:
    """
    从图片中提取所有表格，并返回一个包含Markdown格式表格字符串的列表。
    每个单元格内的换行符会被转换为 <br> 标签。

    :param image_path: 图片文件的路径
    :return: 一个列表，每个元素都是一个Markdown格式的表格字符串
    """
    markdown_tables = []

    # 1) 初始化 OCR 引擎
    try:
        ocr = TesseractOCR(n_threads=1, lang="chi_sim")
    except Exception as e:
        print(f"初始化TesseractOCR失败: {e}")
        print("请确保Tesseract已正确安装于系统PATH，并已安装'chi_sim'语言包。")
        return []

    # 2) 调用 img2table 提取表格（带回退）
    try:
        doc = Image(src=image_path)

        # 在高版本 img2table 中，可通过 ocr_config 传递 tesseract 额外参数
        # 但部分版本不支持该关键字参数，这里做兼容回退。
        ocr_config = {"tess_config": "--psm 6"}

        extracted_tables = None
        try:
            extracted_tables = doc.extract_tables(
                ocr=ocr,
                implicit_rows=True,
                borderless_tables=True,
                ocr_config=ocr_config,  # 首选：若版本支持
            )
        except TypeError as te:
            # 兼容回退：移除不被支持的关键字参数
            if "ocr_config" in str(te) or "unexpected keyword" in str(te):
                print("img2table: 当前版本不支持 ocr_config，已自动回退到兼容调用。")
                extracted_tables = doc.extract_tables(
                    ocr=ocr,
                    implicit_rows=True,
                    borderless_tables=True,
                )
            else:
                raise

        # 3) 转为 Markdown
        for table in (extracted_tables or []):
            df_with_br = table.df.replace(r"\n", "  \n", regex=True)
            markdown_string = df_with_br.to_markdown(index=False)
            markdown_tables.append(markdown_string)

            print("--- 检测到一个表格 (Markdown格式) ---")
            print(markdown_string)
            print("--------------------------------------\n")

    except Exception as e:
        print(f"使用img2table提取表格时发生错误: {e}")
        return []

    return markdown_tables
