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

