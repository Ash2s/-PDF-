"""PDF处理服务：文字坐标提取、表单域添加"""

import fitz  # PyMuPDF
import os
import base64
from io import BytesIO
from PIL import Image


def pdf_to_images(pdf_path: str, dpi: float = 1.5) -> list[dict]:
    """将PDF每页转为base64图片"""
    doc = fitz.open(pdf_path)
    results = []
    for i in range(len(doc)):
        page = doc[i]
        mat = fitz.Matrix(dpi, dpi)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        if img.width > 1200:
            ratio = 1200 / img.width
            img = img.resize((1200, int(img.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({
            "page": i, "width": img.width, "height": img.height,
            "pdf_width": page.rect.width, "pdf_height": page.rect.height,
            "base64": b64,
        })
    doc.close()
    return results


def get_pdf_info(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)
    pages = [{"page": i, "width": doc[i].rect.width, "height": doc[i].rect.height} for i in range(len(doc))]
    doc.close()
    return {"total_pages": len(pages), "pages": pages}


def extract_text_with_positions(pdf_path: str) -> list[dict]:
    """提取PDF所有文字及其精确坐标，按页和行分组"""
    doc = fitz.open(pdf_path)
    results = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                # 收集整行的文字
                line_text = ""
                line_spans = []
                for span in line["spans"]:
                    t = span["text"].strip()
                    if t:
                        line_text += " " + t if line_text else t
                        line_spans.append(span)
                # 逐个span存储
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text:
                        bbox = span["bbox"]
                        results.append({
                            "page": page_num,
                            "text": text,
                            "x": bbox[0], "y": bbox[1],
                            "x1": bbox[2], "y1": bbox[3],
                            "width": bbox[2] - bbox[0],
                            "height": bbox[3] - bbox[1],
                            "line_text": line_text,  # 同行完整文字
                        })
    doc.close()
    return results


def _adjust_for_bilingual(label_match: dict, all_spans: list[dict]) -> dict:
    """
    双语标签定位修正：检测匹配文字上方是否有中文标签，如有则上移y坐标。
    PDF双语布局：中文在上，英文在下，表单域应填在中文标签旁边。
    """
    page = label_match["page"]
    match_y = label_match["y"]
    match_x = label_match["x"]

    # 在匹配文字上方搜索最近的中文标签（只找紧邻的，避免跨字段误匹配）
    best = None
    best_dist = 999
    for sp in all_spans:
        if sp["page"] != page:
            continue
        # 中文标签应在上方（y < match_y），且距离不超过12像素（约一行高度）
        dist = match_y - sp["y"]
        if dist <= 0 or dist > 12:
            continue
        # x坐标重叠（在同一列）
        if sp["x1"] < match_x - 10 or sp["x"] > match_x + 50:
            continue
        # 检查是否包含中文字符
        has_chinese = any(ord(c) > 0x4e00 for c in sp["text"])
        if not has_chinese:
            continue
        # 选择最近的中文标签
        if dist < best_dist:
            best_dist = dist
            best = sp

    if best:
        adjusted = dict(label_match)
        adjusted["y"] = best["y"] - 1
        adjusted["y1"] = best["y1"]
        return adjusted

    return label_match


def _find_blank_position(label_match: dict, all_spans: list[dict],
                         label_text: str = "") -> dict:
    """
    精确定位填写区域：找到标签右侧的空白区域。
    核心逻辑：填写区域 = 标签右侧到下一个文字之间的间隙，不超过右侧最近的文字。
    特殊处理：长标签（占页面宽度>50%）时，填写区域放在标签下方。
    """
    page = label_match["page"]
    label_y_center = (label_match["y"] + label_match["y1"]) / 2
    label_height = label_match["height"]
    page_width = 565  # A4页面宽度

    # 如果匹配文本比标签长（如 "Sex Date of Birth" 匹配 "Sex"），
    # 从标签文字宽度之后开始
    matched_text = label_match["text"]
    is_prefix = (label_text and matched_text.lower().startswith(label_text.lower())
                 and len(matched_text) > len(label_text))
    if is_prefix:
        label_ratio = len(label_text) / max(len(matched_text), 1)
        label_x1 = label_match["x"] + (label_match["x1"] - label_match["x"]) * label_ratio
    else:
        label_x1 = label_match["x1"]

    # 特殊处理：长标签（占页面宽度>30%）
    # 先检测是否是表格行标签（右侧有同行文字），如果是则填在右侧而非下方
    label_width = label_x1 - label_match["x"]
    if label_width > page_width * 0.30:
        # 检查标签右侧是否有同行文字（表格行特征）
        has_right_neighbor = False
        for sp in all_spans:
            if sp["page"] != page:
                continue
            sp_y_center = (sp["y"] + sp["y1"]) / 2
            if abs(sp_y_center - label_y_center) < max(label_height * 1.5, 20):
                if sp["x"] > label_x1 + 5:
                    has_right_neighbor = True
                    break

        if not has_right_neighbor:
            # 真正独占一行的长标签 → 填写区域放在标签下方
            form_x = 28  # 页面左边距
            form_width = page_width - 28 - 10  # 减去右边距
            # 向下查找下一个文字，确定可用高度
            next_text_y = label_match["y"] + 100  # 默认100像素高
            for sp in all_spans:
                if sp["page"] != page:
                    continue
                if sp["y"] > label_match["y1"] + 5 and sp["x"] < 100:  # 左侧区域的文字
                    next_text_y = min(next_text_y, sp["y"])
                    break
            form_height = max(20, next_text_y - label_match["y1"] - 5)
            return {
                "x": form_x,
                "y": label_match["y1"] + 2,
                "width": form_width,
                "height": form_height,
            }
        # 表格行标签 → 继续走右侧逻辑

    # 找同一行（y坐标接近）且在标签右侧的文字
    same_line_after = []
    for sp in all_spans:
        if sp["page"] != page:
            continue
        sp_y_center = (sp["y"] + sp["y1"]) / 2
        # 扩大垂直容差：包含标签下方一行内的文字（如DOB的dd/mm/yy子标签）
        if abs(sp_y_center - label_y_center) < max(label_height * 1.2, 15):
            if sp["x"] > label_x1 + 2:
                same_line_after.append(sp)

    same_line_after.sort(key=lambda s: s["x"])

    form_x = label_x1 + 2

    if same_line_after:
        # 智能找空白区域：跳过紧密排列的子标签，找到真正的区域边界
        # 如果前几个文字间距很小（<20px），它们属于同一输入区域，继续往后找
        boundary_x = same_line_after[0]["x"]
        for i in range(1, len(same_line_after)):
            gap = same_line_after[i]["x"] - same_line_after[i-1]["x1"]
            if gap > 20:  # 大间距表示新区域开始
                break
            boundary_x = same_line_after[i]["x"]
        max_right = boundary_x - 3
        form_width = max(30, max_right - form_x)
    else:
        # 右侧没有同行文字，延伸到页面右侧（地址等全宽字段）
        page_right = 565
        form_width = max(180, page_right - form_x)

    return {
        "x": form_x,
        "y": label_match["y"] - 1,
        "width": form_width,
        "height": label_height + 2,
    }


def _detect_table_columns(text_positions: list[dict], page: int) -> list[dict]:
    """检测页面中的表格列结构（通过寻找水平排列的表头）"""
    import re as _re
    page_spans = [t for t in text_positions if t["page"] == page]
    # 中英文列头都识别（中文用包含匹配，英文用词边界匹配，兼容 "Father's Name" 等变体）
    column_headers = ["father", "mother", "guardian", "父亲", "母親", "母亲", "監護人", "监护人"]
    columns = []
    for sp in page_spans:
        text_lower = sp["text"].lower().strip()
        # 中文字符不用\b（\b不支持中文），改用 in 匹配
        def _match_header(text, ch):
            if any(ord(c) > 0x4e00 for c in ch):
                return ch in text
            return _re.search(r'\b' + _re.escape(ch) + r'\b', text) is not None
        if any(_match_header(text_lower, ch) for ch in column_headers):
            columns.append({
                "header": sp["text"].strip(),
                "x": sp["x"],
                "x1": sp["x1"],
                "y": sp["y"],
                "y_center": (sp["y"] + sp["y1"]) / 2,
            })
    columns.sort(key=lambda c: c["x"])
    return columns


def _find_table_cell(row_label_match: dict, column_header: str,
                     text_positions: list[dict], page: int) -> dict | None:
    """在表格中找到特定行和列交叉处的单元格区域"""
    columns = _detect_table_columns(text_positions, page)
    if not columns:
        return None

    # 找目标列（支持中英文匹配：父亲=father, 母亲=mother）
    col_aliases = {
        "父亲": "father", "母亲": "mother", "监护人": "guardian",
        "father": "father", "mother": "mother", "guardian": "guardian",
    }
    target_col = None
    for col in columns:
        header_lower = col["header"].lower().strip()
        if header_lower == column_header.lower():
            target_col = col
            break
        if col_aliases.get(header_lower) == col_aliases.get(column_header.lower()):
            target_col = col
            break
    if not target_col:
        return None

    # 找列的左右边界（相邻列的中间位置）
    col_idx = columns.index(target_col)
    if col_idx > 0:
        left_boundary = (columns[col_idx - 1]["x1"] + target_col["x"]) / 2
    else:
        left_boundary = target_col["x"] - 10

    if col_idx < len(columns) - 1:
        right_boundary = (target_col["x1"] + columns[col_idx + 1]["x"]) / 2
    else:
        right_boundary = target_col["x1"] + 150

    # 找行的上下边界（行标签的y坐标附近）
    row_y = row_label_match["y"]
    row_height = row_label_match["height"]

    return {
        "x": left_boundary + 2,
        "y": row_y - 1,
        "width": right_boundary - left_boundary - 4,
        "height": row_height + 2,
    }


def _normalize_text(text: str) -> str:
    """统一文本规范化：小写、去标点、压缩空格，兼容中英文"""
    t = text.lower().strip()
    # 去除所有括号和常见标点（中英文括号都去掉）
    import re
    t = re.sub(r'[()（）\[\]【】：:\.,/]', '', t)
    t = t.replace("、", " ").replace("，", " ").replace("。", "")
    # 压缩多余空格
    t = " ".join(t.split())
    return t


# 标签别名映射：AI返回的中文风格标签 → PDF上的英文标签
LABEL_ALIASES = {
    "地址(英文)": "Address in English",
    "地址(中文)": "Address in Chinese",
    "地址(住址)": "Address in English",
    "address_en": "Address in English",
    "address_cn": "Address in Chinese",
    "性别": "Sex",
    "出生日期": "Date of Birth",
    "出生地点": "Place of Birth",
    "身份证号码": "HKID Card/ Passport No.",
    "宗教": "Religion",
    "电话": "Phone No.",
    "手提电话": "Mobile",
    "学校名称": "School Name",
    "现就读学校": "School Name",
    "年级": "Class",
    "推荐人": "Referee(s)",
    "申请原因": "Reason(s) for Applying to Our School",
    # 家庭字段别名
    "姓名 (Father)": "Chinese Name (Father)",
    "姓名 (Mother)": "Chinese Name (Mother)",
    "中文姓名 (Father)": "Chinese Name (Father)",
    "中文姓名 (Mother)": "Chinese Name (Mother)",
    "英文姓名 (Father)": "English Name (Father)",
    "英文姓名 (Mother)": "English Name (Mother)",
    "职业 (Father)": "Occupation (Father)",
    "职业 (Mother)": "Occupation (Mother)",
    "联络电话 (Father)": "Contact Tel. No. (Father)",
    "联络电话 (Mother)": "Contact Tel. No. (Mother)",
    "电话 (Father)": "Contact Tel. No. (Father)",
    "电话 (Mother)": "Contact Tel. No. (Mother)",
    "与学生之关系 (Father)": "Relationship with Student (Father)",
    "与学生之关系 (Mother)": "Relationship with Student (Mother)",
    "关系 (Father)": "Relationship with Student (Father)",
    "关系 (Mother)": "Relationship with Student (Mother)",
}


def detect_table_structures(text_positions: list[dict], page: int) -> list[dict]:
    """
    通用表格结构检测：找出页面上所有水平排列的标题组，计算列边界和行位置。
    返回 [{"header_y": y, "columns": [{"x":, "x1":, "label":}], "first_row_y": y, "row_height": n}]
    """
    page_spans = [t for t in text_positions if t["page"] == page]
    if not page_spans:
        return []

    # 按y坐标分组（同一行的文字y差<5像素）
    sorted_spans = sorted(page_spans, key=lambda s: (s["y"], s["x"]))
    groups = []
    current_group = [sorted_spans[0]]
    for sp in sorted_spans[1:]:
        if abs(sp["y"] - current_group[0]["y"]) < 5:
            current_group.append(sp)
        else:
            groups.append(current_group)
            current_group = [sp]
    groups.append(current_group)

    tables = []
    for group in groups:
        if len(group) < 3:
            continue
        # 检查是否是水平排列（最左和最右的x差距>150像素）
        xs = [s["x"] for s in group]
        if max(xs) - min(xs) < 150:
            continue

        # 检查间距是否均匀（标题列之间的间距应该比较一致）
        spans_sorted = sorted(group, key=lambda s: s["x"])
        gaps = []
        for i in range(1, len(spans_sorted)):
            gap = spans_sorted[i]["x"] - spans_sorted[i-1]["x1"]
            gaps.append(gap)
        if not gaps:
            continue
        avg_gap = sum(gaps) / len(gaps)
        # 标题之间的间距应该比较均匀（标准差<平均值的50%）
        if avg_gap < 5:
            continue
        variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
        if variance > (avg_gap * 0.5) ** 2:
            continue

        # 这是一个表格标题行！计算列边界
        columns = []
        for i, sp in enumerate(spans_sorted):
            if i > 0:
                left = (spans_sorted[i-1]["x1"] + sp["x"]) / 2
            else:
                left = max(28, sp["x"] - 10)
            if i < len(spans_sorted) - 1:
                right = (sp["x1"] + spans_sorted[i+1]["x"]) / 2
            else:
                right = min(565, sp["x1"] + 100)
            columns.append({
                "x": left + 2,
                "x1": right - 2,
                "width": right - left - 4,
                "label": sp["text"],
            })

        # 找标题行下方第一行文字的y坐标（数据行起始位置）
        # 需要跳过表头行本身（中英文双行表头），用表头行底部+间距来定位
        header_y = group[0]["y"]
        header_y1 = max(sp["y1"] for sp in group)  # 表头行底部y坐标
        first_row_y = None
        for sp in page_spans:
            # 数据行应在表头行底部下方至少8像素处
            if sp["y"] > header_y1 + 8 and sp["y"] < header_y1 + 100:
                first_row_y = sp["y"]
                break

        # 如果没找到（空表格或搜索范围内无文字），用固定偏移估算
        if not first_row_y:
            first_row_y = header_y1 + 20

        # 检测子标签行（如 "First Term" / "Second Term" 在年份行下方）
        # 如果找到，将子标签合并到列标签中（如 "2025-2026" + "First Term" → "2025-2026 First Term"）
        sub_term_row = []
        for sp in page_spans:
            if header_y1 < sp["y"] < header_y1 + 25 and sp not in group:
                # 过滤掉分隔符（"/"、"-"等）和太短的文字
                text = sp["text"].strip()
                if len(text) > 1 and not all(c in '/-–|' for c in text):
                    sub_term_row.append(sp)
        if sub_term_row:
            sub_term_row.sort(key=lambda s: s["x"])
            for col in columns:
                col_center = (col["x"] + col["x1"]) / 2
                best_sub = None
                best_dist = 999
                for sub in sub_term_row:
                    sub_center = (sub["x"] + sub["x1"]) / 2
                    dist = abs(sub_center - col_center)
                    if dist < best_dist and dist < col["width"]:
                        best_dist = dist
                        best_sub = sub
                if best_sub:
                    col["label"] = col["label"] + " " + best_sub["text"]

        if columns and first_row_y:
            row_height = 35
            tables.append({
                "header_y": header_y,
                "columns": columns,
                "first_row_y": first_row_y - 3,
                "row_height": row_height,
            })

    return tables


def _calc_table_font(value: str, col_width: float, max_fs: float = 10, min_fs: float = 5) -> float:
    """计算表格单元格字号：最大max_fs，超长自适应缩小"""
    content_w = sum(max_fs * (1.1 if ord(c) > 127 else 0.55) for c in value) + 4
    if content_w > col_width and len(value) > 0:
        return max(min_fs, (col_width - 4) / (content_w - 4) * max_fs)
    return max_fs


def _strip_punct(text: str) -> str:
    """去掉所有标点符号，用于列名模糊匹配"""
    import re
    return re.sub(r'[^\w\s]', '', text).strip()


def _score_match(label_norm: str, tp_norm: str) -> int:
    """计算标签与PDF文字的匹配分数"""
    # 单字符或空字符串不给分（避免匹配到标点符号如 "(" "I."）
    # 中文每个字算1字符，2字中文词（如"年齡"）应正常匹配
    def _is_cjk(s):
        return any('一' <= c <= '鿿' for c in s)
    if len(tp_norm) < 2 or (len(tp_norm) < 3 and not _is_cjk(tp_norm)):
        return 0
    if len(label_norm) < 2 or (len(label_norm) < 3 and not _is_cjk(label_norm)):
        return 0

    if label_norm == tp_norm:
        return 150  # 精确匹配最高分，确保优先
    if tp_norm.startswith(label_norm) or label_norm.startswith(tp_norm):
        return 120  # 前缀匹配也很高
    if label_norm in tp_norm or tp_norm in label_norm:
        ratio = len(tp_norm) / max(len(label_norm), 1)
        if ratio > 5:
            return 20
        elif ratio > 3:
            return 40
        return 80
    # 词重叠 — 按覆盖率加权，防止长段落含常见词得分过高
    label_words = set(label_norm.split())
    tp_words = set(tp_norm.split())
    overlap = label_words & tp_words
    if len(overlap) >= 1 and len(label_words) > 0:
        coverage = len(overlap) / len(label_words)
        return int(coverage * 70)  # 最高70，始终低于精确匹配(100)
    # 中文字符重叠 — 至少2个共同字符且覆盖率>40%才给分
    if " " not in label_norm and " " not in tp_norm:
        common = sum(1 for c in label_norm if c in tp_norm)
        if common >= 2 and common / len(label_norm) > 0.4:
            return common * 15
    return 0


def _normalize_label_for_dedup(label: str) -> str:
    """归一化标签用于去重：去掉'in'、排序单词、统一括号格式"""
    import re
    l = label.lower().strip()
    # 提取后缀如 (father), (mother)
    suffix = ""
    m = re.search(r'\s*\(([^)]+)\)\s*$', l)
    if m:
        suffix = f" ({m.group(1)})"
        l = l[:m.start()]
    # 去掉 "in" (如 "Name in Chinese" -> "Name Chinese")
    words = [w for w in l.split() if w != "in"]
    words.sort()
    return " ".join(words) + suffix


def match_fields_to_positions(fields: list[dict], text_positions: list[dict]) -> list[dict]:
    """将AI字段匹配到PDF文字坐标，精确定位填写区域"""
    result = []

    # 去重：归一化label后只保留一个，优先保留有值的版本
    # 归一化处理 "Chinese Name (Father)" 和 "Name in Chinese (Father)" 为相同key
    seen_norm: dict[str, dict] = {}  # normalized_label -> field
    for field in fields:
        if not isinstance(field, dict):
            continue
        label = field.get("label", "").strip()
        if not label:
            continue
        norm = _normalize_label_for_dedup(label)
        if norm not in seen_norm:
            seen_norm[norm] = [field]
        else:
            seen_norm[norm].append(field)
    # 对每个归一化标签，选择最佳版本
    # 优先保留文字实际存在于该页面的版本（排除AI幻觉）
    unique_fields = []
    for norm, field_list in seen_norm.items():
        with_value = [f for f in field_list if f.get("value")]
        if not with_value:
            unique_fields.append(field_list[0])
            continue
        # 检查每个版本的label文字是否实际存在于该页面
        def _text_exists_on_page(field):
            label_norm = _normalize_text(field.get("label", ""))
            page = field.get("page", 0)
            for tp in text_positions:
                if tp["page"] == page:
                    if _score_match(label_norm, _normalize_text(tp["text"])) >= 80:
                        return True
            return False
        existing = [f for f in with_value if _text_exists_on_page(f)]
        if existing:
            best = min(existing, key=lambda f: f.get("page", 99))
        else:
            best = min(with_value, key=lambda f: f.get("page", 99))
        unique_fields.append(best)
    print(f"  [去重] {len(fields)} → {len(unique_fields)} 个字段")

    # 跳过签署类关键词
    skip_keywords = ["signature", "签署", "签章", "签名", "applicant.*sign", "parent.*sign",
                     "已提交", "copy of", "copies of", "bank-in", "payment",
                     "tick", "勾", "checkbox", " checklist"]

    # 预检测所有页面的表格结构，用于跳过表头字段
    all_table_headers = {}  # page -> list of header labels
    pages_with_tables = set(f.get("page", 0) for f in unique_fields)
    for p in pages_with_tables:
        tables = detect_table_structures(text_positions, p)
        headers = []
        for t in tables:
            for col in t["columns"]:
                headers.append(_normalize_text(col["label"]))
        all_table_headers[p] = headers

    for field in unique_fields:
        # 标签别名解析：将AI返回的中文风格标签转为PDF上的英文标签
        raw_label = field.get("label", "")
        if raw_label in LABEL_ALIASES:
            field = dict(field)  # 不修改原对象
            field["label"] = LABEL_ALIASES[raw_label]
        if not isinstance(field, dict):
            continue
        label = field.get("label", "")
        value = field.get("value", "")
        field_page = field.get("page", 0)
        if not value or not label:
            continue

        # 跳过签署类字段
        label_lower = label.lower()
        if any(kw in label_lower for kw in skip_keywords):
            print(f"  [跳过] 签署类: {label}")
            continue

        # 跳过与表格表头重名的字段（这些应由表格匹配处理）
        if field_page in all_table_headers:
            label_norm = _normalize_text(label)
            if label_norm in all_table_headers[field_page]:
                print(f"  [跳过] 表头字段: {label}")
                continue

        label_norm = _normalize_text(label)

        # 行/列标签中英文别名映射（PDF双语标签兼容，通用匹配用）
        row_label_aliases = {
            "chinese name": ["中文姓名", "中文名", "姓名"],
            "name": ["姓名", "名字", "名稱", "名称"],
            "english name": ["英文姓名", "英文名"],
            "name in english": ["英文姓名", "英文名"],
            "sex": ["性別", "性别"],
            "date of birth": ["出生日期"],
            "place of birth": ["出生地", "出生地點", "出生地点"],
            "address": ["住址", "地址", "通訊地址", "通讯地址"],
            "home tel. no.": ["住宅電話", "住宅电话", "住址電話", "住址电话"],
            "mobile": ["手機", "手提電話", "手提电话"],
            "phone": ["電話", "电话", "聯絡電話", "联络电话"],
            "contact tel. no.": ["聯絡電話", "联络电话", "电话", "電話"],
            "current school": ["現就讀學校", "現就讀学校", "現讀學校", "現读学校", "就讀學校"],
            "religion": ["宗教"],
            "hkid card": ["身份證", "身分證", "身份证"],
            "nationality": ["國籍", "国籍"],
            "occupation": ["職業", "职业"],
            "relationship with student": ["與學生之關係", "与学生之关系", "關係", "关系",
                                          "與申請人關係", "与申请人关系"],
            "relationship with applicant": ["與申請人關係", "与申请人关系", "關係", "关系",
                                            "與學生之關係", "与学生之关系"],
            "school name": ["學校名稱", "学校名称", "就读学校", "現讀學校"],
            "class": ["班級", "班级", "年级", "年級", "班別"],
            "month / year": ["年/月", "月/年", "年份", "月份"],
            "year": ["年/月", "月/年", "年份", "年"],
            "academic achievement / activity / service": ["活动", "活動", "學業", "服务", "成績"],
            "activity": ["活动", "活動"],
            "organizer": ["主办机构", "主辦機構", "机构", "機構"],
            "award / post (if any)": ["荣誉/职位", "榮譽/職位", "荣誉", "獎項", "奖项"],
            "award": ["荣誉", "獎項", "奖项"],
        }

        # ═══ 通用表格字段匹配 ═══
        # 解析 label 为 (base_label, qualifier) 二元组
        # qualifier 可能是：数字行号、括号中的列名、年份等
        import re
        base_label = label
        qualifier = None
        qualifier_type = None  # "row_num" | "col_name" | "year"

        # 策略1: 数字前缀 "1.活动" → row=1, col="活动"
        m1 = re.match(r'^(\d+)[.\s](.+)$', label)
        if m1:
            qualifier = int(m1.group(1))
            qualifier_type = "row_num"
            base_label = m1.group(2).strip()
        else:
            # 策略2: 括号内容 "Name (Father)" / "School Name (2024-2025)" / "活动 (1)"
            m2 = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', label)
            if m2:
                base_label = m2.group(1).strip()
                paren_content = m2.group(2).strip()
                if re.match(r'^\d+$', paren_content):
                    qualifier = int(paren_content)
                    qualifier_type = "row_num"
                elif re.match(r'^\d{4}', paren_content):
                    qualifier = paren_content
                    qualifier_type = "year"
                else:
                    # 检查中文序号：如"获奖记录第一项" → row_num=1
                    cn_num = {"一":1,"二":2,"三":3,"四":4,"五":5}
                    m_cn = re.match(r"^.*?第([一-五]+)(?:项|条|个|行|列).*$", paren_content)
                    if m_cn and m_cn.group(1) in cn_num:
                        qualifier = cn_num[m_cn.group(1)]
                        qualifier_type = "row_num"
                    else:
                        qualifier = paren_content
                        qualifier_type = "col_name"

        # 尝试匹配到表格单元格
        if qualifier is not None:
            tables = detect_table_structures(text_positions, field_page)
            matched_in_table = False
            for table in tables:
                if matched_in_table:
                    break

                if qualifier_type == "row_num":
                    # 行号模式：base_label 匹配列头，qualifier 是行号
                    col_name_norm = _normalize_text(base_label)
                    # 构建列名别名列表（中英文桥接）
                    col_aliases = [col_name_norm]
                    for alias_key, alias_vals in row_label_aliases.items():
                        if col_name_norm == alias_key:
                            col_aliases.extend(alias_vals)
                        elif col_name_norm in alias_vals:
                            col_aliases.append(alias_key)
                            col_aliases.extend(v for v in alias_vals if v != col_name_norm)

                    for ci, col in enumerate(table["columns"]):
                        col_label_norm = _normalize_text(col["label"])
                        col_label_stripped = _strip_punct(col["label"])
                        # 直接匹配或别名匹配
                        if (col_name_norm in col_label_norm or col_label_norm in col_name_norm
                                or _strip_punct(base_label) in col_label_stripped
                                or col_label_stripped in _strip_punct(base_label)
                                or any(a in col_label_norm or col_label_norm in a for a in col_aliases)):
                            row_y = table["first_row_y"] + (qualifier - 1) * table["row_height"]
                            font_size = _calc_table_font(value, col["width"], 10, 5)
                            result.append({
                                "label": label, "value": value,
                                "x": col["x"], "y": row_y,
                                "width": col["width"], "height": table["row_height"] - 2,
                                "page": field_page, "font_size": font_size,
                                "matched_text": f"row{qualifier} x {col['label']}", "match_score": 100,
                            })
                            print(f"  [表格] {label} → col={col['label']} row={qualifier} x={col['x']:.0f}, y={row_y:.0f}")
                            matched_in_table = True
                            break

                elif qualifier_type in ("col_name", "year"):
                    # 列名/年份模式：qualifier 匹配列头，base_label 匹配行头
                    target_col = None
                    qual_norm = _normalize_text(qualifier)
                    # 收集所有匹配的列（同年可能有多列，如 First Term / Second Term）
                    matching_cols = []
                    for ci, col in enumerate(table["columns"]):
                        col_label_norm = _normalize_text(col["label"])
                        if qual_norm in col_label_norm or col_label_norm in qual_norm:
                            matching_cols.append((ci, col))
                        elif qualifier_type == "year":
                            q_digits = set(re.findall(r'\d{4}', qualifier))
                            c_digits = set(re.findall(r'\d{4}', col["label"]))
                            if q_digits and c_digits and q_digits == c_digits:
                                matching_cols.append((ci, col))

                    if matching_cols:
                        # 如果有多个匹配列，用子学期（First Term/Second Term）区分
                        if len(matching_cols) > 1:
                            # 检查 qualifier 是否包含子学期信息
                            qual_lower = qualifier.lower()
                            if "first" in qual_lower or "上" in qual_lower or "1st" in qual_lower:
                                target_col = matching_cols[0][1]  # 第一个匹配列
                            elif "second" in qual_lower or "下" in qual_lower or "2nd" in qual_lower:
                                target_col = matching_cols[1][1] if len(matching_cols) > 1 else matching_cols[0][1]
                            else:
                                target_col = matching_cols[0][1]  # 默认用第一个
                        else:
                            target_col = matching_cols[0][1]

                    if target_col:
                        base_norm = _normalize_text(base_label)
                        row_aliases = [base_norm]
                        for alias_key, alias_vals in row_label_aliases.items():
                            if base_norm == alias_key:
                                row_aliases.extend(alias_vals)
                            elif base_norm in alias_vals:
                                row_aliases.append(alias_key)
                                row_aliases.extend(v for v in alias_vals if v != base_norm)

                        row_y = None
                        for tp in text_positions:
                            if tp["page"] != field_page:
                                continue
                            tp_norm = _normalize_text(tp["text"])
                            if any(_score_match(a, tp_norm) >= 80 for a in row_aliases):
                                row_y = tp["y"]
                                break

                        if row_y is not None:
                            font_size = _calc_table_font(value, target_col["width"], 8, 5)
                            result.append({
                                "label": label, "value": value,
                                "x": target_col["x"], "y": row_y - 1,
                                "width": target_col["width"], "height": 30,
                                "page": field_page, "font_size": font_size,
                                "matched_text": f"{base_label} x {qualifier}", "match_score": 100,
                            })
                            print(f"  [表格] {label} → col={target_col['label']} row={base_label} x={target_col['x']:.0f}, y={row_y:.0f}")
                            matched_in_table = True

            if matched_in_table:
                continue  # 已匹配到表格，不走后续通用匹配

        # 检查是否是表格字段（包含 "(Father)" "(Mother)" "(Guardian)" 等）（包含 "(Father)" "(Mother)" "(Guardian)" 或 "父亲" "母亲" 等）
        table_col = None
        row_label = label
        # 格式1: "姓名 (Father)" / "职业 (Mother)"
        for en_col in ["(father)", "(mother)", "(guardian)"]:
            if en_col in label_norm:
                table_col = en_col.strip("()")
                row_label = label_norm.split(en_col)[0].strip().rstrip(" -")
                break
        # 格式2: "父亲姓名" / "母亲职业"
        if not table_col:
            for cn_col in ["父亲", "母亲", "监护人"]:
                if cn_col in label:
                    table_col = cn_col
                    row_label = label.split(cn_col)[0].strip().rstrip(" （-")
                    break

        if table_col:
            # 表格字段：分别匹配行标签和列位置
            row_norm = _normalize_text(row_label)
            best_row_match = None
            best_row_score = 0

            for tp in text_positions:
                if tp["page"] != field_page:
                    continue
                tp_norm = _normalize_text(tp["text"])
                if not tp_norm:
                    continue

                score = _score_match(row_norm, tp_norm)
                # 如果直接匹配分数不高，尝试别名匹配
                if score < 30 and row_norm in row_label_aliases:
                    for alias in row_label_aliases[row_norm]:
                        alias_score = _score_match(_normalize_text(alias), tp_norm)
                        score = max(score, alias_score)
                if score > best_row_score:
                    best_row_score = score
                    best_row_match = tp

            if best_row_match and best_row_score >= 30:
                cell = _find_table_cell(best_row_match, table_col, text_positions, field_page)
                if not cell:
                    # Fallback: 在所有页面找列头，找到后用列头所在页作为正确页面
                    col_aliases = {"father": "father", "mother": "mother", "guardian": "guardian",
                                   "父亲": "father", "母親": "mother", "母亲": "mother", "監護人": "guardian", "监护人": "guardian"}
                    target = col_aliases.get(table_col, table_col)
                    col_spans = [t for t in text_positions
                                 if target in _normalize_text(t["text"])]
                    if col_spans:
                        col_span = col_spans[0]
                        correct_page = col_span["page"]
                        # 在列头所在页重新搜索行标签（使用别名匹配）
                        row_y = best_row_match["y"]
                        row_aliases = [row_norm]
                        if row_norm in row_label_aliases:
                            row_aliases.extend(row_label_aliases[row_norm])
                        for tp in text_positions:
                            if tp["page"] != correct_page:
                                continue
                            tp_norm = _normalize_text(tp["text"])
                            if any(_score_match(alias, tp_norm) >= 80 for alias in row_aliases):
                                row_y = tp["y"]
                                break
                        row_h = best_row_match.get("height", 12) + 2
                        cell = {"x": col_span["x"] - 5, "y": row_y - 1,
                                "width": 100, "height": row_h}
                        field_page = correct_page  # 更新到正确的页面
                        print(f"  [表格fallback] {label} → page={correct_page} col={col_span['text']} x={cell['x']:.0f} y={cell['y']:.0f}")
                if cell:
                    result.append({
                        "label": label,
                        "value": value,
                        "x": cell["x"],
                        "y": cell["y"],
                        "width": cell["width"],
                        "height": cell["height"],
                        "page": field_page,
                        "font_size": 8,
                        "matched_text": f"{best_row_match['text']} x {table_col}",
                        "match_score": best_row_score,
                    })
                    print(f"  [表格] {label} → row={best_row_match['text']} col={table_col} (x={cell['x']:.0f}, y={cell['y']:.0f})")
                    continue
                else:
                    print(f"  [表格失败] {label} → row={best_row_match['text']} col={table_col} 找不到单元格，跳过")
                    continue

        # 非表格字段：直接匹配标签（只在当前页搜索）
        best_match = None
        best_score = 0

        for tp in text_positions:
            if tp["page"] != field_page:
                continue
            tp_norm = _normalize_text(tp["text"])
            if not tp_norm:
                continue

            score = _score_match(label_norm, tp_norm)

            # 同分时优先选更短的文本（更可能是标签本身而非段落）
            if score > best_score or (score == best_score and score > 0
                                       and best_match and len(tp["text"]) < len(best_match["text"])):
                best_score = score
                best_match = tp

        # 别名桥接：直接匹配分数低时，通过别名匹配中英文差异
        # 如 label="chinese name" → 尝试用"中文姓名"匹配PDF
        if not (best_match and best_score >= 30):
            for alias_key, alias_vals in row_label_aliases.items():
                if label_norm == alias_key or label_norm in alias_vals:
                    candidates = [alias_key] + alias_vals
                    for alt in candidates:
                        if alt == label_norm:
                            continue
                        for tp in text_positions:
                            if tp["page"] != field_page:
                                continue
                            s = _score_match(alt, _normalize_text(tp["text"]))
                            if s > best_score:
                                best_score = s
                                best_match = tp
                    break
            # 最终尝试：label包含匹配（含短标签的精确文字匹配）
            if not (best_match and best_score >= 30):
                for tp in text_positions:
                    if tp["page"] != field_page:
                        continue
                    t = _normalize_text(tp["text"])
                    if label_norm in t or t in label_norm:
                        best_score = 80
                        best_match = tp
                        break
            # 短标签兜底：_score_match跳过的短标签(如"(英)")，直接搜原文
            if not (best_match and best_score >= 30) and len(label) <= 6:
                raw = label.strip()
                raw_norm = _normalize_text(raw)
                for tp in text_positions:
                    if tp["page"] != field_page:
                        continue
                    tp_raw = tp["text"]
                    if raw in tp_raw or (raw_norm and raw_norm in _normalize_text(tp_raw)):
                        best_score = 90
                        best_match = tp
                        break

        if best_match and best_score >= 30:
            # 双语修正：检测上方是否有中文标签，上移y坐标
            adjusted_match = _adjust_for_bilingual(best_match, text_positions)
            pos = _find_blank_position(adjusted_match, text_positions, label_text=label)
            result.append({
                "label": label,
                "value": value,
                "x": pos["x"],
                "y": pos["y"],
                "width": pos["width"],
                "height": pos["height"],
                "page": best_match["page"],
                "font_size": 8,
                "matched_text": best_match["text"],
                "match_score": best_score,
            })
            print(f"  [匹配] {label} → {best_match['text']} (score={best_score}, x={pos['x']:.0f}, y={pos['y']:.0f}, w={pos['width']:.0f})")
        else:
            # 未匹配时打印原因帮助调试
            reason = f"score={best_score}"
            if best_match:
                reason += f", 最佳候选: {best_match['text'][:30]!r} at y={best_match['y']:.0f}"
            print(f"  [跳过] 未匹配: {label} ({reason})")

    # 去重：检测位置重叠的字段，保留标签更具体的那个，移除较笼统的
    # 如 "姓名(中)" 和 "姓名" 在同一位置 → 保留 "姓名(中)"
    result_deduped = []
    for i, r in enumerate(result):
        overlapping = False
        for j, other in enumerate(result):
            if i == j:
                continue
            # 检查位置是否高度重叠
            same_page = r.get("page") == other.get("page")
            x_overlap = abs(r.get("x", 0) - other.get("x", 0)) < 10
            y_overlap = abs(r.get("y", 0) - other.get("y", 0)) < 8
            if same_page and x_overlap and y_overlap:
                # 保留标签更长的（更具体），跳过标签更短的（更笼统）
                if len(r.get("label", "")) < len(other.get("label", "")):
                    overlapping = True
                    print(f"  [去重] {r['label']} 被 {other['label']} 覆盖（同位置，保留更具体）")
                    break
        if not overlapping:
            result_deduped.append(r)

    # 活动表格字号：每个单元格独立自适应（最大10pt，超长缩小）
    # 不做全表统一，让每个单元格根据内容长度自适应

    return result_deduped


def add_form_fields(input_pdf: str, output_pdf: str, fields: list[dict],
                     text_positions: list[dict] = None) -> str:
    """在PDF上添加可编辑表单域"""
    import tempfile
    import shutil

    doc = fitz.open(input_pdf)

    for field in fields:
        page_num = field.get("page", 0)
        if page_num >= len(doc):
            continue
        page = doc[page_num]
        value = field.get("value", "")
        if not value:
            continue

        x = field["x"]
        y = field["y"]
        w = field.get("width", 150)
        h = field.get("height", 12)

        # 跳过坐标无效的字段
        if w <= 0 or h <= 0 or x < 0 or y < 0:
            print(f"  [跳过] 坐标无效: {field.get('label','')} x={x:.0f} y={y:.0f} w={w:.0f} h={h:.0f}")
            continue

        # 跳过超出页面范围的字段
        page_rect = doc[page_num].rect
        if x + w > page_rect.width + 10 or y + h > page_rect.height + 10:
            print(f"  [跳过] 超出页面: {field.get('label','')} x={x:.0f} y={y:.0f} w={w:.0f} h={h:.0f} page={page_rect.width:.0f}x{page_rect.height:.0f}")
            continue

        # 优先使用字段自带的font_size（活动表格等），否则自动计算
        # 全局上限：小四 = 12pt
        MAX_FONT_SIZE = 12
        preset_font_size = field.get("font_size")
        if preset_font_size:
            font_size = min(preset_font_size, MAX_FONT_SIZE)
        else:
            max_font_size = 8
            min_font_size = 5.5
            char_width = 4.5
            content_w = len(value) * char_width + 10
            if content_w > w and len(value) > 0:
                font_size = max(min_font_size, (w - 10) / content_w * max_font_size)
            else:
                font_size = max_font_size
            font_size = min(font_size, MAX_FONT_SIZE)

        widget = fitz.Widget()
        widget.field_name = field.get("label", f"f{page_num}_{int(x)}_{int(y)}")
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_value = value
        widget.field_flags = 0

        # 长文本启用多行模式
        if len(value) > 40 or '\n' in value:
            widget.field_flags = 1 << 12  # PDF_WIDGET_FLAG_MULTILINE
            estimated_lines = max(2, len(value) // 50 + 1)
            h = max(h, estimated_lines * (font_size + 2))
        widget.rect = fitz.Rect(x, y, x + w, y + h)
        widget.text_fontsize = font_size
        widget.text_color = (0, 0, 0)
        widget.fill_color = None
        widget.border_color = None
        widget.border_width = 0
        widget.border_style = "none"
        try:
            page.add_widget(widget)
        except ValueError as e:
            print(f"  [错误] 添加widget失败: {field.get('label','')} rect=({x:.0f},{y:.0f},{x+w:.0f},{y+h:.0f}) error={e}")
            continue

    # 先保存到临时文件，再替换（避免浏览器锁定文件导致 Permission denied）
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(output_pdf))
    os.close(tmp_fd)
    try:
        doc.save(tmp_path)
        doc.close()
        # 如果目标文件被锁定，shutil.move 也会失败，用替换策略
        if os.path.exists(output_pdf):
            try:
                os.remove(output_pdf)
            except PermissionError:
                # 文件被锁定，用临时文件名作为最终文件
                output_pdf = tmp_path
                return output_pdf
        shutil.move(tmp_path, output_pdf)
    except Exception:
        doc.close()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return output_pdf
