"""完整流程测试：简历+表单 → 填写版PDF"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from services.pdf_service import pdf_to_images, get_pdf_info, extract_text_with_positions, add_form_fields
from services.field_matcher import match_fields_to_positions
from services.extractor import detect_form_fields, extract_student_info
import docx2txt

def main():
    resume_path = r"C:\Users\EDY\Desktop\1\余谦\A余谦递交合集.docx"
    form_path = r"C:\Users\EDY\Desktop\1\余谦\余謙入學申請表.pdf"
    output_dir = r"C:\Users\EDY\Desktop"
    
    print("Step 1: Extract student info from resume...")
    text = docx2txt.process(resume_path)
    print(f"  Resume text length: {len(text)} chars")
    
    from services.extractor import STUDENT_EXTRACT_PROMPT
    from services.mimo import analyze_text, _extract_json
    prompt = f"{STUDENT_EXTRACT_PROMPT}\n\n以下是学生文档内容：\n{text[:3000]}"
    result = analyze_text(prompt)
    student_info = _extract_json(result)
    print(f"  Student: {student_info.get('name_cn', 'N/A')}")
    print(f"  School: {student_info.get('current_school', 'N/A')}")
    
    print("\nStep 2: Process PDF form...")
    pdf_info = get_pdf_info(form_path)
    print(f"  Form pages: {pdf_info['total_pages']}")
    
    text_positions = extract_text_with_positions(form_path)
    print(f"  Text elements: {len(text_positions)}")
    
    images = pdf_to_images(form_path, dpi=1.5)
    all_ai_fields = []
    for img_data in images:
        page_num = img_data["page"]
        try:
            fields, activities = detect_form_fields(img_data["base64"], student_info=student_info)
            for f in fields:
                f["page"] = page_num
            all_ai_fields.extend([f for f in fields if not f.get("_skip")])
            filled = sum(1 for f in fields if f.get("value"))
            print(f"  Page {page_num+1}: {len(fields)} fields, {filled} filled")
        except Exception as e:
            print(f"  Page {page_num+1}: skipped ({e})")
    
    print(f"\nStep 3: Match fields to positions...")
    matched = match_fields_to_positions(all_ai_fields, text_positions)
    print(f"  Matched: {len(matched)} fields")
    
    print("\nStep 4: Generate filled PDF...")
    output_path = os.path.join(output_dir, "屯门天主教中学_填写版.pdf")
    add_form_fields(form_path, output_path, matched, text_positions=text_positions)
    print(f"  Output: {output_path}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
