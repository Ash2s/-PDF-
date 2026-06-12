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
