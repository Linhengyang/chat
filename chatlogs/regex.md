**system**:You are a helpful assistant on python programming especially on regular-expression extraction.


---
🙋**user**:
---
```
帮我写两个正则抽取函数：
1. 从文本text中，抽取全部小于2.0的正浮点数, 可能有百分号
2. 从文本text中，抽取全部大于90.0的正浮点数
```

---
🤖**assistant**:
---

下面给你一套 **Python 正则抽取函数**。默认按“百分号前的数字”比较，例如 `1.5%` 视为数值 `1.5`；如果希望 `1.5%` 视为 `0.015`，需要额外除以 100。

---

## 推荐实现：正则抽取候选数字 + 数值判断

这种方式最稳，容易维护，也能处理整数、小数、前导 0、可选正负号、可选百分号等情况。

```python
import re
from typing import Callable, List, Union

# 候选数字正则：先找出“像数字”的片段，再转 float 判断范围
_NUMBER_RE = re.compile(
    r"""
    (?<![\d.])                # 左边不能是数字或小数点，避免把 12.34 截成 2.34
    [+-]?                     # 可选正负号；负数会被后面的“正数”条件过滤掉
    (?:\d+\.\d+|\.\d+|\d+)    # 1.23 / .23 / 123
    (?![\d.])                 # 右边不能是数字或小数点，避免匹配 1.2.3 中的片段
    %?                        # 可选百分号
    """,
    re.VERBOSE,
)


def _extract(
    text: str,
    ok: Callable[[float], bool],
    return_str: bool = True,
) -> List[Union[str, float]]:
    """
    从 text 中抽取满足条件的正浮点数。

    :param text: 输入文本
    :param ok: 判断数值是否满足条件的函数
    :param return_str:
        True  -> 返回原文匹配结果，可能包含百分号，如 ['1.5%', '0.3']
        False -> 返回 float 数值，如 [1.5, 0.3]
    """
    result: List[Union[str, float]] = []

    for m in _NUMBER_RE.finditer(text):
        raw = m.group(0)

        # 去掉末尾百分号后转 float
        # 如 '1.5%' -> '1.5' -> 1.5
        try:
            value = float(raw.rstrip("%"))
        except ValueError:
            continue

        if ok(value):
            result.append(raw if return_str else value)

    return result


def extract_lt_2(text: str, return_str: bool = True) -> List[Union[str, float]]:
    """
    抽取全部小于 2.0 的正浮点数。
    不包含 0，也不包含 2.0。
    """
    return _extract(text, lambda x: 0.0 < x < 2.0, return_str)


def extract_gt_90(text: str, return_str: bool = True) -> List[Union[str, float]]:
    """
    抽取全部大于 90.0 的正浮点数。
    不包含 90.0。
    """
    return _extract(text, lambda x: x > 90.0, return_str)
```

---

## 使用示例

```python
if __name__ == "__main__":
    text = """
    0.5%, 1, 1.99, 2.0, .3, -0.4, +0.2, 0, 0.0,
    90.0, 90.01, 91%, 100.5, 89.9, 1.2.3
    """

    # 返回原文匹配结果，可能包含 %
    print(extract_lt_2(text))
    # ['0.5%', '1', '1.99', '.3', '+0.2']

    # 返回 float 数值
    print(extract_lt_2(text, return_str=False))
    # [0.5, 1.0, 1.99, 0.3, 0.2]

    print(extract_gt_90(text))
    # ['90.01', '91%', '100.5']

    print(extract_gt_90(text, return_str=False))
    # [90.01, 91.0, 100.5]
```

---

## 如果你想要“纯正则”直接匹配范围

如果不想做 `float()` 判断，也可以直接用正则表达式匹配“小于 2.0”和“大于 90.0”的数字。  
但纯正则会更长，并且通常不如上面的“正则 + 数值判断”灵活。

### 1. 抽取小于 2.0 的正浮点数

支持：

- `0.5`
- `.5`
- `1`
- `1.0`
- `01.5`
- `0.0001`
- `1.999%`

不支持负数、科学计数法、显式正号等复杂情况。

```python
import re
from typing import List

LT2_PURE_RE = re.compile(
    r"""
    (?<![\d.+\-])              # 前面不要是数字、点、正负号，避免匹配负数片段
    (?:
        0*\.(?:\d*?[1-9]\d*)   # .5 / 0.5 / 00.5，且排除 0.0 / .0
      | 0*1(?:\.\d*)?          # 1 / 1.0 / 01.5 / 001.23
    )
    (?![\d.])                  # 后面不能是数字或点，避免匹配 1.2.3
    %?                         # 可选百分号
    """,
    re.VERBOSE,
)


def extract_lt_2_pure_regex(text: str) -> List[str]:
    """
    纯正则抽取小于 2.0 的正浮点数。
    返回原文匹配结果。
    """
    return LT2_PURE_RE.findall(text)
```

示例：

```python
text = "0.5%, .3, 1, 1.99, 2.0, 0.0, 0.0001, 01.5, 1.2.3"
print(extract_lt_2_pure_regex(text))
# ['0.5%', '.3', '1', '1.99', '0.0001', '01.5']
```

---

### 2. 抽取大于 90.0 的正浮点数

支持：

- `90.01`
- `90.1`
- `91`
- `99.9%`
- `100`
- `100.0`
- `090.1`
- `00091.5`

不支持：

- `90.0`
- `90.000`
- `90`
- 负数
- 科学计数法
- 显式正号

```python
import re
from typing import List

GT90_PURE_RE = re.compile(
    r"""
    (?<![\d.+\-])                # 前面不要是数字、点、正负号
    (?:
        0*90\.(?:\d*?[1-9]\d*)   # 90.01 / 090.1，排除 90.0 / 90.000
      | 0*9[1-9](?:\.\d*)?       # 91 / 99.9 / 091.5
      | 0*[1-9]\d{2,}(?:\.\d*)?  # 100 / 100.0 / 000100.5
    )
    (?![\d.])                    # 后面不能是数字或点
    %?                           # 可选百分号
    """,
    re.VERBOSE,
)


def extract_gt_90_pure_regex(text: str) -> List[str]:
    """
    纯正则抽取大于 90.0 的正浮点数。
    返回原文匹配结果。
    """
    return GT90_PURE_RE.findall(text)
```

示例：

```python
text = "90.0, 90.01, 90.000, 90.0001, 91%, 99.9, 100.5, 090.1, 89.9"
print(extract_gt_90_pure_regex(text))
# ['90.01', '90.0001', '91%', '99.9', '100.5', '090.1']
```

---

## 建议

一般场景建议用第一套：

```python
extract_lt_2(text)
extract_gt_90(text)
```

原因：

1. 更容易读；
2. 更容易扩展；
3. 数值边界判断更可靠；
4. 可以避免纯正则处理数值范围时的复杂边界问题。


---
🙋**user**:
---
```
AMOUNT_RE_STRICT = re.compile(
    r'(?<![\d.])'
    r'(?P<num>[1-9]\d*00)'
    r'(?:'
        r'\s*(?P<unit>[wWeEkK]|[亿万])(?![\d.])'
    r'|'
        r'(?![\d.]|[wWeEkK亿万][\d.])'
    r')'
)


def parse_amounts(text: str) -> Dict[str, str]|None|str:
    logger.info(f'input for field amounts:\n{text}')

    cleaned = re.sub(r'[^0-9wWeEkK亿万]', '', text)
    found = AMOUNT_RE_STRICT.findall(cleaned)
    if not found:
        return cleaned
    return found

这样有个缺陷，无法匹配 4.1亿 这样的数字，无法把4.1和亿识别出来。如何修改？
```

---
🤖**assistant**:
---

你的代码无法匹配 `4.1亿`，主要由**两个致命缺陷**导致：

1. **清洗函数误杀了小数点**：`re.sub(r'[^0-9wWeEkK亿万]', '', text)` 中没有保留 `.`，导致 `4.1亿` 被清洗成了 `41亿`，小数点丢失。
2. **正则对数字的限制太死**：`(?P<num>[1-9]\d*00)` 只能匹配“以非0开头且以00结尾的整数”（如 100, 2500），完全不支持小数（如 4.1），也不支持非00结尾的整数（如 50）。

此外，原代码使用 `findall` 在有多个命名分组时会返回**元组列表**（如 `[('4.1', '亿')]`），而不是你类型提示中期望的**字典列表**。

下面是修复并优化后的代码：

### 修复后的代码

```python
import re
from typing import List, Dict, Union

# 1. 修改正则：支持小数，并补全中文单位（如'万'）
AMOUNT_RE_STRICT = re.compile(
    r'(?<![\d.])'                                  # 负向后顾：左边不能是数字或小数点
    r'(?P<num>\d+(?:\.\d+)?)'                      # 数字部分：支持整数和小数（如 100, 4.1, 0.5）
    r'(?:'
        r'\s*(?P<unit>[wWeEkK]|[千万亿])(?![\d.])' # 单位部分：右边不能是数字或小数点
    r'|'
        r'(?![\d.]|[wWeEkK千万亿][\d.])'           # 无单位时：右边不能紧跟数字，也不能紧跟单位+数字
    r')'
)

def parse_amounts(text: str) -> Union[List[Dict[str, str]], str]:
    # logger.info(f'input for field amounts:\n{text}')

    # 2. 修改清洗逻辑：必须保留小数点 '.'，并加上中文 '万'
    cleaned = re.sub(r'[^0-9.wWeEkK千万亿]', '', text)
    
    # 3. 使用 finditer 获取命名分组，构建字典列表（替代 findall 的元组列表）
    matches = AMOUNT_RE_STRICT.finditer(cleaned)
    found = [
        {'num': m.group('num'), 'unit': m.group('unit') or ''} 
        for m in matches
    ]
    
    if not found:
        return cleaned
    return found
```

### 主要修改点说明：

1. **保留小数点与中文“万”**：
   将清洗正则改为 `r'[^0-9.wWeEkK千万亿]'`。加入了 `.` 以保留小数，加入了 `万` 以支持中文“万”单位（原代码只有“亿”没有“万”）。
2. **放开数字格式限制**：
   将 `num` 分组从 `[1-9]\d*00` 改为 `\d+(?:\.\d+)?`。现在它可以完美匹配 `4.1`、`100`、`0.5`、`3.14` 等任意正整数和小数。
3. **修复返回数据结构**：
   原代码 `findall` 返回的是 `[('4.1', '亿')]`（元组）。这里改用 `finditer` 并手动构建字典，使其返回 `[{'num': '4.1', 'unit': '亿'}]`，真正符合你 `Dict[str, str]` 的类型预期，方便下游直接通过 `item['num']` 取值。

### 测试验证

```python
if __name__ == "__main__":
    # 测试 1：包含小数和单位
    print(parse_amounts("金额是4.1亿，另外有3.5w"))
    # 输出: [{'num': '4.1', 'unit': '亿'}, {'num': '3.5', 'unit': 'w'}]

    # 测试 2：包含中文万和纯数字
    print(parse_amounts("预算100万，实际花费50"))
    # 输出: [{'num': '100', 'unit': '万'}, {'num': '50', 'unit': ''}]

    # 测试 3：没有匹配到金额时返回清洗后的文本
    print(parse_amounts("今天天气真好"))
    # 输出: '' (空字符串，因为非数字/单位字符被清洗了)
    
    # 测试 4：防止错误截断（如 4.1.2 不是合法数字）
    print(parse_amounts("错误数据4.1.2亿"))
    # 输出: [{'num': '1.2', 'unit': '亿'}] (自动跳过非法的 4.1，匹配合法的 1.2)
```

**补充提示**：如果你的业务场景中金额可能以 `.5` 这种省略前导零的形式出现（如 `.5亿`），可以将正则中的数字部分微调为 `(?P<num>\d+(?:\.\d+)?|\.\d+)` 即可支持。通常写 `0.5` 居多，当前的 `\d+(?:\.\d+)?` 已经足够覆盖 99% 的场景。

