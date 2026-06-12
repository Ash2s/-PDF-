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


LABEL_ALIASES = AI_LABEL_TO_PDF


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
