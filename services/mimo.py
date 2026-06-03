"""MIMO-v2.5 API调用封装 - 直接用httpx"""

import os
import json
import httpx


def get_api_key() -> str:
    api_key = os.environ.get("MIMO_API_KEY", "")
    if not api_key:
        raise ValueError("未设置 MIMO_API_KEY 环境变量")
    return api_key


def _call_api(messages: list, max_tokens: int = 8192, retries: int = 5) -> str:
    """调用MIMO API，处理reasoning_content，带自动重试"""
    import time as _time
    api_key = get_api_key()
    url = "https://api.xiaomimimo.com/v1/chat/completions"

    payload = {
        "model": "mimo-v2.5",
        "messages": messages,
        "max_tokens": min(max_tokens, 16384),  # MIMO API上限
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=120, trust_env=False) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            break  # 成功，跳出重试循环
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < retries - 1:
                wait = (attempt + 1) * 3
                print(f"  [API重试] 第{attempt+1}次失败: {type(e).__name__}, {wait}秒后重试...")
                _time.sleep(wait)
            else:
                print(f"  [API重试] 第{attempt+1}次失败，已用尽重试次数")
                raise

    msg = data["choices"][0]["message"]
    content = msg.get("content", "") or ""
    reasoning = msg.get("reasoning_content", "") or ""

    # 优先用content（最终答案），如果为空则用reasoning_content
    # 如果两者都有内容，选择包含JSON的那个
    if content.strip() and "{" in content:
        return content.strip()
    if reasoning.strip() and "{" in reasoning:
        return reasoning.strip()
    # 都没有JSON，返回有内容的那个
    if content.strip():
        return content.strip()
    if reasoning.strip():
        return reasoning.strip()
    # 都为空，打印调试信息
    print(f"  [API调试] content长度={len(content)}, reasoning长度={len(reasoning)}")
    print(f"  [API调试] msg keys: {list(msg.keys())}")
    return ""


def analyze_image(image_base64: str, prompt: str, max_tokens: int = 8192) -> str:
    """发送图片+prompt给MIMO，返回文本响应"""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        }
    ]
    return _call_api(messages, max_tokens=max_tokens)


def analyze_image_json(image_base64: str, prompt: str, max_tokens: int = 8192):
    """发送图片+prompt给MIMO，解析JSON响应"""
    response_text = analyze_image(image_base64, prompt, max_tokens=max_tokens)
    return _extract_json(response_text)


def analyze_text(prompt: str) -> str:
    """纯文本调用MIMO（无图片）"""
    messages = [
        {"role": "system", "content": "你是一个JSON提取助手。直接返回JSON对象，不要输出思考过程或解释。"},
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    ]
    return _call_api(messages, max_tokens=16384)


def _extract_json(text: str):
    """从AI响应文本中提取JSON"""
    text = text.strip()
    if not text:
        raise ValueError("AI返回为空")

    # 打印原始响应帮助调试
    print(f"  [AI原始响应前300字]: {text[:300]}")

    # 移除markdown代码块
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # 如果文本以非JSON字符开头（如AI的思考过程），找到第一个{或[
    first_brace = text.find("{")
    first_bracket = text.find("[")
    if first_brace != -1 or first_bracket != -1:
        start = min(x for x in [first_brace, first_bracket] if x != -1)
        text = text[start:]
        print(f"  [JSON提取] 跳过前{start}字的非JSON内容")

    try:
        result = json.loads(text)
        print(f"  [JSON解析成功] 类型={type(result).__name__}")
        return result
    except json.JSONDecodeError as e:
        print(f"  [JSON解析失败] {e}")

    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                result = json.loads(text[start : end + 1])
                print(f"  [JSON提取成功] 类型={type(result).__name__}, 位置={start}-{end}")
                return result
            except json.JSONDecodeError:
                continue

    # 尝试修复截断的JSON：补全未关闭的括号
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        fragment = text[start:]
        # 统计未关闭的括号
        depth = 0
        in_string = False
        escape = False
        for c in fragment:
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth = max(0, depth - 1)
        # 补全缺失的括号
        fixed = fragment + end_char * depth
        if start_char == "{":
            fixed = fixed + "]"
        print(f"  [JSON修复尝试] depth={depth}, fixed后50字: {fixed[-50:]}")
        try:
            result = json.loads(fixed)
            print(f"  [JSON修复成功] 补全了{depth}个括号")
            return result
        except json.JSONDecodeError as e:
            print(f"  [JSON修复失败] {e}")
            continue

    raise ValueError(f"无法从AI响应中提取JSON:\n{text[:500]}")
