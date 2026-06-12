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
