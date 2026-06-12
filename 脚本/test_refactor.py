"""测试重构后的模块"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf_service import pdf_to_images, get_pdf_info, extract_text_with_positions, add_form_fields
from services.field_matcher import match_fields_to_positions
from services.table_detector import detect_table_structures
from services.aliases import resolve_ai_label, get_row_aliases, LABEL_ALIASES, ROW_ALIASES
from services.config import PAGE_WIDTH, MIN_COLUMNS

def test_config():
    print("=== 测试配置模块 ===")
    assert PAGE_WIDTH == 565
    assert MIN_COLUMNS == 3
    print("  [OK] 配置常量正确")

def test_aliases():
    print("=== 测试别名模块 ===")
    assert resolve_ai_label("性别") == "Sex"
    assert resolve_ai_label("出生日期") == "Date of Birth"
    assert resolve_ai_label("Unknown") == "Unknown"
    aliases = get_row_aliases("chinese name")
    assert "中文姓名" in aliases
    assert "姓名" in aliases
    print(f"  [OK] LABEL_ALIASES: {len(LABEL_ALIASES)} 条")
    print(f"  [OK] ROW_ALIASES: {len(ROW_ALIASES)} 条")

def test_pdf_service():
    print("=== 测试PDF服务 ===")
    pdf_path = r"C:\Users\EDY\Desktop\1\李紫辰\屯门天主教中学.pdf"
    if not os.path.exists(pdf_path):
        print("  [SKIP] 测试PDF不存在，跳过")
        return

    info = get_pdf_info(pdf_path)
    print(f"  [OK] get_pdf_info: {info['total_pages']} 页")

    text_positions = extract_text_with_positions(pdf_path)
    print(f"  [OK] extract_text_with_positions: {len(text_positions)} 个文字元素")

    images = pdf_to_images(pdf_path, dpi=1.0)
    print(f"  [OK] pdf_to_images: {len(images)} 页")

def test_table_detector():
    print("=== 测试表格检测 ===")
    pdf_path = r"C:\Users\EDY\Desktop\1\李紫辰\屯门天主教中学.pdf"
    if not os.path.exists(pdf_path):
        print("  [SKIP] 测试PDF不存在，跳过")
        return

    text_positions = extract_text_with_positions(pdf_path)
    for page in range(min(3, len(set(tp["page"] for tp in text_positions)))):
        tables = detect_table_structures(text_positions, page)
        if tables:
            print(f"  [OK] 第{page+1}页检测到 {len(tables)} 个表格")
            for t in tables:
                print(f"    列: {[c['label'] for c in t['columns']]}")

def test_field_matcher():
    print("=== 测试字段匹配 ===")
    fields = [
        {"label": "Name", "value": "李紫辰", "page": 0},
        {"label": "Sex", "value": "女", "page": 0},
        {"label": "Date of Birth", "value": "01/01/2010", "page": 0},
    ]
    text_positions = [
        {"text": "Name", "x": 100, "y": 100, "x1": 150, "y1": 112, "width": 50, "height": 12, "page": 0, "line_text": "Name"},
        {"text": "Sex", "x": 100, "y": 120, "x1": 130, "y1": 132, "width": 30, "height": 12, "page": 0, "line_text": "Sex"},
        {"text": "Date of Birth", "x": 100, "y": 140, "x1": 200, "y1": 152, "width": 100, "height": 12, "page": 0, "line_text": "Date of Birth"},
    ]
    result = match_fields_to_positions(fields, text_positions)
    print(f"  [OK] 匹配结果: {len(result)} 个字段")
    for r in result:
        print(f"    {r['label']}: x={r['x']:.0f}, y={r['y']:.0f}")

if __name__ == "__main__":
    print("开始测试重构后的模块...\n")
    test_config()
    test_aliases()
    test_pdf_service()
    test_table_detector()
    test_field_matcher()
    print("\n[DONE] 所有测试完成!")
