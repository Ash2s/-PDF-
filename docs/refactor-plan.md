# PDF 表格匹配逻辑重构计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 执行此计划。

**Goal:** 将 pdf_service.py 的匹配逻辑拆分为职责单一的模块，提升可维护性

**Architecture:** 
- 提取表格检测为独立模块
- 提取字段匹配为独立模块
- 统一别名系统
- 保持原有 API 接口不变

**Tech Stack:** Python, PyMuPDF

---

## 文件结构

**重构后目录：**
```
services/
├── pdf_service.py          # 保留：PDF 转图片、坐标提取、表单域添加
├── table_detector.py       # 新增：表格结构检测
├── field_matcher.py        # 新增：字段匹配核心逻辑
├── aliases.py              # 新增：统一别名系统
└── config.py               # 新增：配置常量
```

**职责划分：**
- `pdf_service.py`：PDF 文件操作（保留原有接口）
- `table_detector.py`：表格结构检测
- `field_matcher.py`：字段到坐标的匹配
- `aliases.py`：所有别名映射
- `config.py`：容差值、页面尺寸等常量

---

## Task 1: 创建配置模块

**Files:**
- Create: `services/config.py`

- [ ] **Step 1: 创建配置文件**

```python
"""配置常量"""

# 页面尺寸
PAGE_WIDTH = 565  # A4 页面宽度（像素）
PAGE_LEFT_MARGIN = 28
PAGE_RIGHT_MARGIN = 10

# 匹配容差
Y_TOLERANCE = 15  # 垂直匹配容差（像素）
X_TOLERANCE = 10  # 水平匹配容差（像素）
DISTANCE_THRESHOLD = 12  # 标签与填写区域最大距离

# 表格检测
MIN_COLUMNS = 3  # 最少列数
MIN_SPREAD = 150  # 列间最小水平距离
GAP_VARIANCE_RATIO = 0.5  # 间距均匀性阈值

# 行高
DEFAULT_ROW_HEIGHT = 35
TABLE_ROW_HEIGHT = 30
```

- [ ] **Step 2: 验证配置**

确认所有硬编码值已提取，原有逻辑不受影响。

---

## Task 2: 创建别名系统

**Files:**
- Create: `services/aliases.py`
- Modify: `services/pdf_service.py` (删除 LABEL_ALIASES 和 row_label_aliases)

- [ ] **Step 1: 创建统一别名模块**

```python
"""统一别名系统 - 中英文标签映射"""

# AI 返回的中文标签 → PDF 上的英文标签
AI_LABEL_TO_PDF = {
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
    # 家庭字段
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

# 行标签别名（用于表格匹配）
ROW_ALIASES = {
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

def resolve_ai_label(label: str) -> str:
    """将 AI 返回的中文标签转换为 PDF 上的英文标签"""
    return AI_LABEL_TO_PDF.get(label, label)

def get_row_aliases(base_label: str) -> list[str]:
    """获取行标签的所有别名"""
    base_lower = base_label.lower()
    aliases = [base_lower]
    if base_lower in ROW_ALIASES:
        aliases.extend(ROW_ALIASES[base_lower])
    else:
        for key, values in ROW_ALIASES.items():
            if base_lower in values:
                aliases.append(key)
                aliases.extend(v for v in values if v != base_lower)
                break
    return aliases
```

- [ ] **Step 2: 更新 pdf_service.py**

删除原有的 `LABEL_ALIASES` 和 `row_label_aliases`，导入新模块：

```python
from .aliases import resolve_ai_label, get_row_aliases
```

- [ ] **Step 3: 验证功能**

运行现有测试，确认别名映射功能不变。

---

## Task 3: 创建表格检测模块

**Files:**
- Create: `services/table_detector.py`
- Modify: `services/pdf_service.py` (删除 detect_table_structures 和相关函数)

- [ ] **Step 1: 创建表格检测模块**

```python
"""表格结构检测"""
import re
from .config import MIN_COLUMNS, MIN_SPREAD, GAP_VARIANCE_RATIO, DEFAULT_ROW_HEIGHT


def detect_table_structures(text_positions: list[dict], page: int) -> list[dict]:
    """
    检测页面中的表格结构
    返回 [{"header_y": y, "columns": [{"x":, "x1":, "label":}], "first_row_y": y, "row_height": n}]
    """
    page_spans = [t for t in text_positions if t["page"] == page]
    if not page_spans:
        return []

    # 按 y 坐标分组（同一行的文字 y 差 < 5 像素）
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
        if len(group) < MIN_COLUMNS:
            continue

        # 检查是否是水平排列
        xs = [s["x"] for s in group]
        if max(xs) - min(xs) < MIN_SPREAD:
            continue

        # 检查间距是否均匀
        spans_sorted = sorted(group, key=lambda s: s["x"])
        gaps = [spans_sorted[i]["x"] - spans_sorted[i-1]["x1"] for i in range(1, len(spans_sorted))]
        if not gaps:
            continue
        avg_gap = sum(gaps) / len(gaps)
        if avg_gap < 5:
            continue
        variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
        if variance > (avg_gap * GAP_VARIANCE_RATIO) ** 2:
            continue

        # 计算列边界
        columns = _calculate_columns(spans_sorted)

        # 找第一行数据的 y 坐标
        header_y = group[0]["y"]
        header_y1 = max(sp["y1"] for sp in group)
        first_row_y = _find_first_row_y(page_spans, header_y1)

        # 检测子标签行（如 "First Term" / "Second Term"）
        columns = _merge_sub_labels(columns, page_spans, header_y1)

        if columns and first_row_y:
            tables.append({
                "header_y": header_y,
                "columns": columns,
                "first_row_y": first_row_y - 3,
                "row_height": DEFAULT_ROW_HEIGHT,
            })

    return tables


def _calculate_columns(spans_sorted: list[dict]) -> list[dict]:
    """计算列边界"""
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
    return columns


def _find_first_row_y(page_spans: list[dict], header_y1: float) -> float:
    """找表头下方第一行数据的 y 坐标"""
    for sp in page_spans:
        if sp["y"] > header_y1 + 8 and sp["y"] < header_y1 + 100:
            return sp["y"]
    return header_y1 + 20


def _merge_sub_labels(columns: list[dict], page_spans: list[dict], header_y1: float) -> list[dict]:
    """合并子标签行（如 First Term / Second Term）到列标签中"""
    sub_term_row = []
    for sp in page_spans:
        if header_y1 < sp["y"] < header_y1 + 25:
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

    return columns
```

- [ ] **Step 2: 更新 pdf_service.py 导入**

```python
from .table_detector import detect_table_structures
```

- [ ] **Step 3: 删除 pdf_service.py 中的旧代码**

删除 `detect_table_structures` 及其辅助函数（约 110 行）。

- [ ] **Step 4: 验证功能**

测试表格检测功能是否正常。

---

## Task 4: 创建字段匹配模块

**Files:**
- Create: `services/field_matcher.py`
- Modify: `services/pdf_service.py` (删除 match_fields_to_positions 和相关函数)

- [ ] **Step 1: 创建字段匹配模块**

```python
"""字段到坐标的匹配"""
import re
from .config import Y_TOLERANCE, X_TOLERANCE, DISTANCE_THRESHOLD, TABLE_ROW_HEIGHT
from .aliases import resolve_ai_label, get_row_aliases
from .table_detector import detect_table_structures


def match_fields_to_positions(fields: list[dict], text_positions: list[dict]) -> list[dict]:
    """将 AI 字段匹配到 PDF 文字坐标"""
    # 1. 去重
    unique_fields = _dedup_fields(fields, text_positions)

    # 2. 跳过签署类字段
    skip_keywords = ["signature", "签署", "签章", "签名", "applicant.*sign", "parent.*sign",
                     "已提交", "copy of", "copies of", "bank-in", "payment",
                     "tick", "勾", "checkbox", " checklist"]

    # 3. 预检测所有页面的表格结构
    all_table_headers = _pre_detect_table_headers(unique_fields, text_positions)

    result = []
    for field in unique_fields:
        # 标签别名解析
        raw_label = field.get("label", "")
        if raw_label in resolve_ai_label(raw_label):
            field = dict(field)
            field["label"] = resolve_ai_label(raw_label)

        label = field.get("label", "")
        value = field.get("value", "")
        field_page = field.get("page", 0)

        if not value or not label:
            continue

        # 跳过签署类字段
        if any(kw in label.lower() for kw in skip_keywords):
            continue

        # 跳过与表格表头重名的字段
        if field_page in all_table_headers:
            if _normalize_text(label) in all_table_headers[field_page]:
                continue

        # 尝试匹配
        matched = _try_match_field(field, text_positions, all_table_headers)
        if matched:
            result.append(matched)

    # 4. 位置重叠去重
    result = _dedup_by_position(result)

    return result


def _dedup_fields(fields: list[dict], text_positions: list[dict]) -> list[dict]:
    """字段去重"""
    # 实现原有的去重逻辑
    seen_norm = {}
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

    unique_fields = []
    for norm, field_list in seen_norm.items():
        with_value = [f for f in field_list if f.get("value")]
        if not with_value:
            unique_fields.append(field_list[0])
            continue
        # 检查文字是否实际存在于页面
        existing = [f for f in with_value if _text_exists_on_page(f, text_positions)]
        if existing:
            best = min(existing, key=lambda f: f.get("page", 99))
        else:
            best = min(with_value, key=lambda f: f.get("page", 99))
        unique_fields.append(best)

    return unique_fields


def _text_exists_on_page(field: dict, text_positions: list[dict]) -> bool:
    """检查字段标签文字是否存在于页面"""
    label_norm = _normalize_text(field.get("label", ""))
    page = field.get("page", 0)
    for tp in text_positions:
        if tp["page"] == page:
            if _score_match(label_norm, _normalize_text(tp["text"])) >= 80:
                return True
    return False


def _pre_detect_table_headers(fields: list[dict], text_positions: list[dict]) -> dict:
    """预检测所有页面的表格结构"""
    all_table_headers = {}
    pages_with_tables = set(f.get("page", 0) for f in fields)
    for p in pages_with_tables:
        tables = detect_table_structures(text_positions, p)
        headers = []
        for t in tables:
            for col in t["columns"]:
                headers.append(_normalize_text(col["label"]))
        all_table_headers[p] = headers
    return all_table_headers


def _try_match_field(field: dict, text_positions: list[dict], all_table_headers: dict) -> dict | None:
    """尝试匹配单个字段"""
    label = field.get("label", "")
    value = field.get("value", "")
    field_page = field.get("page", 0)
    label_norm = _normalize_text(label)

    # 1. 解析 label 为 (base_label, qualifier) 二元组
    base_label, qualifier, qualifier_type = _parse_label(label)

    # 2. 尝试表格匹配
    if qualifier is not None:
        matched = _try_table_match(base_label, qualifier, qualifier_type, value, field_page, text_positions)
        if matched:
            return matched

    # 3. 尝试通用表格字段匹配（如 "姓名 (Father)"）
    table_col = _detect_table_column(label_norm)
    if table_col:
        matched = _try_generic_table_match(label, value, table_col, field_page, text_positions)
        if matched:
            return matched

    # 4. 非表格字段直接匹配
    return _try_direct_match(label, value, field_page, text_positions)


def _parse_label(label: str) -> tuple[str, any, str | None]:
    """解析 label 为 (base_label, qualifier, qualifier_type)"""
    base_label = label
    qualifier = None
    qualifier_type = None

    # 策略1: 数字前缀 "1.活动"
    m1 = re.match(r'^(\d+)[.\s](.+)$', label)
    if m1:
        qualifier = int(m1.group(1))
        qualifier_type = "row_num"
        base_label = m1.group(2).strip()
    else:
        # 策略2: 括号内容
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
                qualifier = paren_content
                qualifier_type = "col_name"

    return base_label, qualifier, qualifier_type


def _detect_table_column(label_norm: str) -> str | None:
    """检测字段是否属于表格列"""
    for en_col in ["(father)", "(mother)", "(guardian)"]:
        if en_col in label_norm:
            return en_col.strip("()")
    for cn_col in ["父亲", "母亲", "监护人"]:
        if cn_col in label_norm:
            return cn_col
    return None


def _try_table_match(base_label, qualifier, qualifier_type, value, field_page, text_positions):
    """尝试表格匹配"""
    # 实现原有的表格匹配逻辑
    pass


def _try_generic_table_match(label, value, table_col, field_page, text_positions):
    """尝试通用表格字段匹配"""
    # 实现原有的通用表格匹配逻辑
    pass


def _try_direct_match(label, value, field_page, text_positions):
    """尝试直接匹配"""
    # 实现原有的直接匹配逻辑
    pass


def _dedup_by_position(result: list[dict]) -> list[dict]:
    """按位置去重"""
    result_deduped = []
    for i, r in enumerate(result):
        overlapping = False
        for j, other in enumerate(result):
            if i == j:
                continue
            same_page = r.get("page") == other.get("page")
            x_overlap = abs(r.get("x", 0) - other.get("x", 0)) < 10
            y_overlap = abs(r.get("y", 0) - other.get("y", 0)) < 8
            if same_page and x_overlap and y_overlap:
                if len(r.get("label", "")) < len(other.get("label", "")):
                    overlapping = True
                    break
        if not overlapping:
            result_deduped.append(r)
    return result_deduped


def _normalize_text(text: str) -> str:
    """文本规范化"""
    t = text.lower().strip()
    t = re.sub(r'[()（）\[\]【】：:\.,/]', '', t)
    t = t.replace("、", " ").replace("，", " ").replace("。", "")
    t = " ".join(t.split())
    return t


def _score_match(label_norm: str, tp_norm: str) -> int:
    """计算匹配分数"""
    # 实现原有的评分逻辑
    pass
```

- [ ] **Step 2: 补充完整匹配逻辑**

将 `pdf_service.py` 中的以下函数迁移到 `field_matcher.py`：
- `_try_table_match`
- `_try_generic_table_match`
- `_try_direct_match`
- `_score_match`
- `_find_blank_position`
- `_adjust_for_bilingual`
- `_find_table_cell`
- `_detect_table_columns`
- `_calc_table_font`

- [ ] **Step 3: 更新 pdf_service.py**

```python
from .field_matcher import match_fields_to_positions
```

删除 `match_fields_to_positions` 及其所有辅助函数（约 600 行）。

- [ ] **Step 4: 验证功能**

运行完整测试，确认所有匹配逻辑正常。

---

## Task 5: 清理和验证

**Files:**
- Modify: `services/pdf_service.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: 清理 pdf_service.py**

确认 `pdf_service.py` 只保留：
- `pdf_to_images`
- `get_pdf_info`
- `extract_text_with_positions`
- `add_form_fields`

约 300 行代码。

- [ ] **Step 2: 添加导入**

```python
from .field_matcher import match_fields_to_positions
from .table_detector import detect_table_structures
```

- [ ] **Step 3: 创建测试用例**

```python
"""测试字段匹配"""
import pytest
from services.field_matcher import match_fields_to_positions, _normalize_text, _score_match


def test_normalize_text():
    assert _normalize_text("Name in English") == "name in english"
    assert _normalize_text("姓名（中文）") == "姓名中文"


def test_score_match():
    assert _score_match("name", "name") == 150  # 精确匹配
    assert _score_match("name", "name in english") == 80  # 包含匹配


def test_match_fields_basic():
    fields = [{"label": "Name", "value": "John", "page": 0}]
    text_positions = [{"text": "Name", "x": 100, "y": 100, "x1": 150, "y1": 112, "page": 0}]
    result = match_fields_to_positions(fields, text_positions)
    assert len(result) == 1
    assert result[0]["label"] == "Name"
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_matcher.py -v
```

- [ ] **Step 5: 提交**

```bash
git add services/config.py services/aliases.py services/table_detector.py services/field_matcher.py
git commit -m "refactor: 拆分 pdf_service.py 的匹配逻辑为独立模块"
```

---

## 验证清单

- [ ] 所有现有测试通过
- [ ] `match_fields_to_positions` 接口不变
- [ ] 别名映射功能正常
- [ ] 表格检测功能正常
- [ ] 字段匹配功能正常
- [ ] 代码行数从 1080 行减少到约 300 行
