**system**:You are a helpful assistant on python programming especially on regular-expression extraction.


---
🙋**user**:
---
```
诸如 【申港to国泰海通】、【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】、【兴业银行 韩立i0123456789 出给 浙商城投】
反正是诸如 <某金融机构名>to/卖给/出给<某金融机构名>，有时候交易方是<某金融机构名+该机构联系人名+该联系人qq账号>这样更详细的文本。
我希望用 正则的方法把元素解析开来，首先：
1. 用 to/卖给/出给/出 等中间词将前后两端分开，然后分别对前后两端实行以下
2. 如果有10位数字，那么找出来，去掉i/QT/QQ这样的10位数字前置符之后，再提取纯粹的中文字和空白符，实行以下
3. 如果含有一个空格，那么前后分别就是机构名和人名；如果含有多个空格，去掉全部空格，实行以下
4. 如果字数是2-3个字，那么就是机构名；如果字数正好4字，那么机构名是前4字，人名是后2字；如果字数正好5字，那么机构名是前2字，人名是后3字；如果字数正好6字，那么机构名是前4字，人名是后2字；如果字数正好是7字，那么机构名是前4字，人名是后3字；如果字数是8及以上，那么机构名是前4字，人名是后3字。
帮我写成代码。
未来我考虑用LLM代替这些死板的规则。顺便帮我写一份提取 卖出方和买入方的 prompt，其中卖出方和买入方都可能由 机构名+人名+数字号组成，其中机构名必有。
```

---
🤖**assistant**:
---

下面给你一套可直接运行的 Python 正则/规则解析代码，以及一份未来可替换为 LLM 的 Prompt。

我先按你的描述做了两处工程化说明：

1. 你第 4 条里“如果字数正好4字，机构名是前4字，人名是后2字”在字符串长度上不可能成立。结合你给的例子：`国泰海通`、`浙商城投`，我按“4字整体作为机构名”处理。  
2. “含有一个空格”我代码里默认理解为“有一个空白分隔块”，也就是连续多个空格也当作一个分隔符，这样更稳。如果你希望严格“只有一个空格字符才切分”，我也在代码里留了注释位置。

---

## 1. 正则规则版代码

```python
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ==============================
# 1. 分隔词：卖出方 -> 买入方
# ==============================
# 可自行扩充。长词会优先匹配。
SEP_WORDS = [
    "卖出给",
    "出给",
    "卖给",
    "卖出",
    "出售",
    "转让",
    "出",
    "to",
    "->",
    "→",
]

SEP_RE = re.compile(
    r"\s*(?:"
    + "|".join(re.escape(w) for w in sorted(SEP_WORDS, key=len, reverse=True))
    + r")\s*",
    re.IGNORECASE,
)


# ==============================
# 2. 10位数字账号识别
# ==============================
# 支持：
#   QT 0123456789
#   qq0123456789
#   i0123456789
#   QQ号：0123456789
#   联系方式 0123456789
# 等。
ACCOUNT_PREFIX_WORDS = [
    "QQ号",
    "QQ",
    "QT号",
    "QT",
    "微信号",
    "微信",
    "VX",
    "WX",
    "账号",
    "账户",
    "联系人",
    "联系方式",
    "手机",
    "电话",
    "联系",
    "I",
    "Q",
]

_prefix_alt = "|".join(
    re.escape(x) for x in sorted(ACCOUNT_PREFIX_WORDS, key=len, reverse=True)
)

_account_prefix = rf"(?:{_prefix_alt})\s*[:：]?\s*"

# 提取10位数字本身
ACCOUNT_RE = re.compile(
    rf"(?i)(?<!\d)(?:{_account_prefix})?(\d{{10}})(?!\d)"
)

# 删除10位数字及其前置符，避免影响后续机构名/人名解析
REMOVE_ACCOUNT_RE = re.compile(
    rf"(?i)\s*(?:{_account_prefix})?(?<!\d)\d{{10}}(?!\d)"
)

# 只保留中文字符和空白符
KEEP_CN_AND_SPACE_RE = re.compile(r"[^\u4e00-\u9fff\s]+")


# ==============================
# 3. 数据结构
# ==============================
@dataclass
class Party:
    raw: str
    org: str = ""
    person: Optional[str] = None
    account: Optional[str] = None
    accounts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "org": self.org,
            "person": self.person,
            "account": self.account,
            "accounts": self.accounts,
        }


# ==============================
# 4. 工具函数
# ==============================
def _strip_boundary(text: str) -> str:
    """
    去掉首尾常见括号、空白。
    """
    return text.strip().strip("【】[]{}()（）<>《》").strip()


def _clean_party_text(text: str) -> str:
    """
    删除账号、前置符、英文、数字、标点，只保留中文和空白。
    """
    s = text.replace("\u3000", " ")

    # 删除10位数字及前置符
    s = REMOVE_ACCOUNT_RE.sub("", s)

    # 只保留中文和空白
    s = KEEP_CN_AND_SPACE_RE.sub("", s)

    # 去掉零宽字符
    s = re.sub(r"[\u200b-\u200f\ufeff]", "", s)

    return s.strip()


def _split_by_length(text: str) -> Tuple[str, Optional[str]]:
    """
    按中文字数切机构名和人名。

    你的规则：
    - 2-3字：机构名
    - 4字：机构名
    - 5字：前2机构，后3人名
    - 6字：前4机构，后2人名
    - 7字：前4机构，后3人名
    - 8字及以上：前4机构，后3人名

    注意：
    8字及以上取“后3字”是你给的规则，但可能会丢掉中间字。
    如果你希望取“机构名后紧跟的3个字”作为人名，可以改成：
        return s[:4], s[4:7]
    """
    s = re.sub(r"\s+", "", text)
    n = len(s)

    if n == 0:
        return "", None

    if n <= 3:
        return s, None

    if n == 4:
        # 按你的示例修正：4字一般整体是机构名
        return s, None

    if n == 5:
        return s[:2], s[2:]

    if n == 6:
        return s[:4], s[4:]

    if n == 7:
        return s[:4], s[4:]

    # n >= 8
    return s[:4], s[-3:]


def _split_org_person(cleaned_text: str) -> Tuple[str, Optional[str]]:
    """
    根据空格和中文字数切分机构名、人名。
    """
    s = cleaned_text.strip()
    if not s:
        return "", None

    # 按连续空白切分
    segments = [seg for seg in re.split(r"\s+", s) if seg]

    # 如果空白分隔后正好两段，则认为：机构名 人名
    # 例如：国泰海通 林宇昂
    #
    # 如果你希望严格按“只有一个空格字符才切分”，可以改成：
    #   ws_count = len(re.findall(r"\s", s))
    #   if ws_count == 1:
    #       ...
    if len(segments) == 2:
        return segments[0], segments[1]

    # 否则去掉全部空格，按字数规则切
    no_space = "".join(segments)
    return _split_by_length(no_space)


# ==============================
# 5. 单侧解析
# ==============================
def parse_party(raw: str) -> Party:
    """
    解析交易一方。

    输入可能形如：
      申港
      国泰海通
      国泰海通 林宇昂
      国泰海通 林宇昂 QT 0123456789
      兴业银行 韩立i0123456789
    """
    s = _strip_boundary(raw)

    # 先找10位数字账号
    accounts = ACCOUNT_RE.findall(s)
    account = accounts[0] if accounts else None

    # 清洗文本：去掉数字、字母、标点、账号前置符等
    cleaned = _clean_party_text(s)

    # 切机构名、人名
    org, person = _split_org_person(cleaned)

    return Party(
        raw=s,
        org=org,
        person=person,
        account=account,
        accounts=accounts,
    )


# ==============================
# 6. 整条交易解析
# ==============================
def parse_trade(text: str) -> Dict[str, Any]:
    """
    解析整条交易文本。

    例如：
      【申港to国泰海通】
      【国泰海通 林宇昂 QT 0123456789 to 华创杨文昊】
      【兴业银行 韩立i0123456789 出给 浙商城投】
    """
    s = text.strip()

    m = SEP_RE.search(s)
    if not m:
        return {
            "ok": False,
            "raw": s,
            "error": "未找到分隔词，可补充 SEP_WORDS，例如：to/卖给/出给/出/卖出",
            "seller": None,
            "buyer": None,
        }

    seller_raw = s[: m.start()]
    buyer_raw = s[m.end() :]

    seller = parse_party(seller_raw)
    buyer = parse_party(buyer_raw)

    return {
        "ok": True,
        "raw": s,
        "separator": m.group(0).strip(),
        "seller": seller.to_dict(),
        "buyer": buyer.to_dict(),
    }


# ==============================
# 7. 测试示例
# ==============================
if __name__ == "__main__":
    import json

    examples = [
        "【申港to国泰海通】",
        "【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】",
        "【兴业银行 韩立i0123456789 出给 浙商城投】",
        "招商证券 王五 QQ 1234567890 卖给 平安理财",
        "中金公司李明qt2233445566出给浦发银行",
    ]

    for text in examples:
        result = parse_trade(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-" * 80)
```

---

## 2. 示例输出

以：

```text
【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】
```

为例，大致会得到：

```json
{
  "ok": true,
  "raw": "【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】",
  "separator": "to",
  "seller": {
    "raw": "国泰海通 林宇昂 QT 0123456789",
    "org": "国泰海通",
    "person": "林宇昂",
    "account": "0123456789",
    "accounts": [
      "0123456789"
    ]
  },
  "buyer": {
    "raw": "华创杨文昊",
    "org": "华创",
    "person": "杨文昊",
    "account": null,
    "accounts": []
  }
}
```

---

## 3. 未来用 LLM 替代规则时的 Prompt

下面这个 Prompt 可以直接用于让 LLM 抽取“卖出方”和“买入方”。  
建议调用时将 `temperature` 设为 `0` 或很低，并要求模型只输出 JSON。

```text
你是金融产品交易要素抽取器。请从用户输入的短文本中抽取“卖出方”和“买入方”。

输入文本通常类似：
- 【申港to国泰海通】
- 【国泰海通 林宇昂 QT 0123456789 to 华创杨文昊】
- 【兴业银行 韩立i0123456789 出给 浙商城投】
- 招商证券 王五 QQ 1234567890 卖给 平安理财

你需要识别：
1. 卖出方：通常是 to/卖给/出给/卖出/出售/转让 等分隔词左侧。
2. 买入方：通常是这些分隔词右侧。
3. 每一方都可能包含：
   - 机构名：必有字段，必须尽量抽取出来。
   - 联系人姓名：可选。
   - 数字账号：可选，例如 QQ、微信、手机号等。

只输出合法 JSON，不要输出 Markdown，不要输出解释，不要输出多余文本。

输出格式必须如下：
{
  "seller": {
    "org": string,
    "person": string | null,
    "account": string | null
  },
  "buyer": {
    "org": string,
    "person": string | null,
    "account": string | null
  },
  "errors": string[]
}

抽取规则：

1. 方向判断
   - 如果文本为 A to B、A 卖给 B、A 出给 B、A 卖出 B、A 出售给 B，则 A 是卖出方，B 是买入方。
   - 如果语义明确表示一方卖出、另一方买入，按语义判断。
   - 不要编造原文中不存在的一方。

2. 机构名
   - 每个交易方必须抽取机构名 org。
   - 保留原文中的机构简称，不要扩写，不要翻译。
   - 例如：申港、国泰海通、华创、浙商城投、兴业银行 都应作为机构名。
   - 如果某一方无法识别机构名，将 org 设为空字符串，并在 errors 中加入对应错误：
     - "seller_org_missing"
     - "buyer_org_missing"

3. 人名
   - 人名通常是联系人姓名，一般为2到3个汉字。
   - 如果机构名和人名连在一起，请根据上下文拆分。
   - 例如：华创杨文昊 应拆为机构名 华创，人名 杨文昊。
   - 如果不确定某个片段是否是人名，返回 null，不要强行猜测。

4. 数字账号
   - 数字账号通常是 QQ、微信、手机号等连续数字。
   - 优先识别10位数字，但不要绝对排斥其他长度；如果上下文明显是联系方式，也可以抽取。
   - 保留前导0，输出为字符串。
   - 去掉数字前的 i、QT、QQ、qq、QQ号、微信、微信号 等前缀。
   - 例如：
     - QT 0123456789 -> account: "0123456789"
     - 韩立i0123456789 -> person: "韩立", account: "0123456789"
     - 王五 QQ 1234567890 -> person: "王五", account: "1234567890"

5. 清洗规则
   - 去除括号【】、分隔词、标点、多余空格。
   - 不要把分隔词、账号前缀、标点符号混入机构名或人名。
   - 不要把机构后缀如 证券、银行、资管、基金、信托、期货、城投 等误认为人名。

6. 输出要求
   - 必须只输出 JSON。
   - 如果字段不存在，使用 null。
   - errors 为空数组表示成功。

示例1：
输入：
【申港to国泰海通】
输出：
{
  "seller": {
    "org": "申港",
    "person": null,
    "account": null
  },
  "buyer": {
    "org": "国泰海通",
    "person": null,
    "account": null
  },
  "errors": []
}

示例2：
输入：
【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】
输出：
{
  "seller": {
    "org": "国泰海通",
    "person": "林宇昂",
    "account": "0123456789"
  },
  "buyer": {
    "org": "华创",
    "person": "杨文昊",
    "account": null
  },
  "errors": []
}

示例3：
输入：
【兴业银行 韩立i0123456789 出给 浙商城投】
输出：
{
  "seller": {
    "org": "兴业银行",
    "person": "韩立",
    "account": "0123456789"
  },
  "buyer": {
    "org": "浙商城投",
    "person": null,
    "account": null
  },
  "errors": []
}

现在请处理下面输入：
{{用户输入}}
```

---

## 4. 后续建议

如果你未来真的迁移到 LLM，建议：

1. 保留现在的规则版作为 fallback。
2. LLM 输出强制 JSON。
3. 对 `org` 为空的样本单独告警。
4. 对账号字段做后置校验：
   ```python
   re.fullmatch(r"\d{5,12}", account or "")
   ```
5. 对机构名做轻量归一化，比如：
   - 申港 -> 申港证券
   - 国泰海通 -> 国泰海通证券
   - 华创 -> 华创证券

但归一化建议放在规则解析之后，不要污染原始抽取结果。


---
🙋**user**:
---
```
我忘了过桥方，有时候会这样写：
【兴业银行 韩立i0123456789 to 国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】
它代表的意思是 卖方兴业银行，过桥方国泰海通，买方华创。
考虑这种情况，重新写
```

---
🤖**assistant**:
---

可以。你现在这个场景本质上不是单纯的一对一交易，而是可能出现：

```text
卖方 to 买方
卖方 to 过桥方 to 买方
卖方 to 过桥方1 to 过桥方2 to 买方
```

所以更合理的做法是：

1. 先用 `to / 卖给 / 出给 / 出 / 卖出 / 转让` 等分隔词把整句切成多段；
2. 第一段作为 `seller` 卖出方；
3. 最后一段作为 `buyer` 买入方；
4. 中间所有段都作为 `bridges` 过桥方/中间方；
5. 每一段再单独解析：机构名、人名、10位数字账号。

下面我重新给你一版完整代码。

---

## 一、支持过桥方的正则规则版代码

```python
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ======================================================
# 1. 分隔词：用于切分交易链条
# ======================================================
# 长词优先匹配。
# 如果你发现“出”容易误切，可以把单独的 "出" 删掉，只保留 "出给"。
SEP_WORDS = [
    "卖出给",
    "出售给",
    "出给",
    "卖给",
    "卖出",
    "出售",
    "转让",
    "出",
    "to",
    "->",
    "→",
]

SEP_RE = re.compile(
    r"\s*(?:"
    + "|".join(re.escape(w) for w in sorted(SEP_WORDS, key=len, reverse=True))
    + r")\s*",
    re.IGNORECASE,
)


# ======================================================
# 2. 10位数字账号识别
# ======================================================
# 支持：
#   QT 0123456789
#   qq0123456789
#   i0123456789
#   QQ号：0123456789
#   联系方式 0123456789
# 等。
ACCOUNT_PREFIX_WORDS = [
    "QQ号",
    "QQ",
    "QT号",
    "QT",
    "微信号",
    "微信",
    "VX",
    "WX",
    "账号",
    "账户",
    "联系人",
    "联系方式",
    "手机",
    "电话",
    "联系",
    "I",
    "Q",
]

_prefix_alt = "|".join(
    re.escape(x) for x in sorted(ACCOUNT_PREFIX_WORDS, key=len, reverse=True)
)

_account_prefix = rf"(?:{_prefix_alt})\s*[:：]?\s*"

# 提取10位数字本身
ACCOUNT_RE = re.compile(
    rf"(?i)(?<!\d)(?:{_account_prefix})?(\d{{10}})(?!\d)"
)

# 删除10位数字及其前置符，避免影响后续机构名/人名解析
# 这里替换成空格，避免删除账号后把前后中文直接粘在一起
REMOVE_ACCOUNT_RE = re.compile(
    rf"(?i)\s*(?:{_account_prefix})?(?<!\d)\d{{10}}(?!\d)"
)

# 只保留中文字符和空白符
KEEP_CN_AND_SPACE_RE = re.compile(r"[^\u4e00-\u9fff\s]+")


# ======================================================
# 3. 数据结构
# ======================================================
@dataclass
class Party:
    raw: str
    org: str = ""
    person: Optional[str] = None
    account: Optional[str] = None
    accounts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw": self.raw,
            "org": self.org,
            "person": self.person,
            "account": self.account,
            "accounts": self.accounts,
        }


# ======================================================
# 4. 基础清洗函数
# ======================================================
_OPEN_CHARS = "【[（(《<{｛『"
_CLOSE_CHARS = "】]）)》>}｝』"


def _strip_boundary(text: str) -> str:
    """
    去掉首尾常见括号、空白。
    """
    s = text.strip()

    # 如果有成对的外层括号，先剥掉
    while len(s) >= 2 and s[0] in _OPEN_CHARS and s[-1] in _CLOSE_CHARS:
        s = s[1:-1].strip()

    # 再兜底去掉首尾残留括号/空白
    s = s.strip("".join(_OPEN_CHARS + _CLOSE_CHARS)).strip()
    return s


def _clean_party_text(text: str) -> str:
    """
    删除账号、前置符、英文、数字、标点，只保留中文和空白。
    """
    s = text.replace("\u3000", " ")

    # 删除10位数字及前置符，并用空格替代，避免前后文本粘连
    s = REMOVE_ACCOUNT_RE.sub(" ", s)

    # 只保留中文和空白
    s = KEEP_CN_AND_SPACE_RE.sub("", s)

    # 去掉零宽字符
    s = re.sub(r"[\u200b-\u200f\ufeff]", "", s)

    # 压缩空白
    s = re.sub(r"\s+", " ", s).strip()

    return s


# ======================================================
# 5. 机构名/人名切分规则
# ======================================================
def _split_by_length(text: str) -> Tuple[str, Optional[str]]:
    """
    按中文字数切机构名和人名。

    你的规则：
    - 2-3字：机构名
    - 4字：机构名
    - 5字：前2机构，后3人名
    - 6字：前4机构，后2人名
    - 7字：前4机构，后3人名
    - 8字及以上：前4机构，后3人名

    注意：
    你原始描述中“4字时机构名是前4字，人名是后2字”不可能成立，
    我按“4字整体作为机构名”处理。
    """
    s = re.sub(r"\s+", "", text)
    n = len(s)

    if n == 0:
        return "", None

    if n <= 3:
        return s, None

    if n == 4:
        # 例如：国泰海通、浙商城投
        return s, None

    if n == 5:
        # 例如：华创杨文昊 -> 华创 / 杨文昊
        return s[:2], s[2:]

    if n == 6:
        # 例如：兴业银行韩立 -> 兴业银行 / 韩立
        return s[:4], s[4:]

    if n == 7:
        # 例如：国泰海通林宇昂 -> 国泰海通 / 林宇昂
        return s[:4], s[4:]

    # n >= 8
    # 你给的规则是：机构名取前4字，人名取后3字。
    # 这会丢弃中间字。
    #
    # 如果你希望长文本保留完整机构名，例如：
    # 国泰海通证券林宇昂 -> 国泰海通证券 / 林宇昂
    # 可以改成：
    #   return s[:-3], s[-3:]
    return s[:4], s[-3:]


def _split_org_person(cleaned_text: str) -> Tuple[str, Optional[str]]:
    """
    根据空格和中文字数切分机构名、人名。
    """
    s = cleaned_text.strip()
    if not s:
        return "", None

    # 按连续空白切分
    segments = [seg for seg in re.split(r"\s+", s) if seg]

    # 如果空白分隔后正好两段，则认为：机构名 人名
    # 例如：国泰海通 林宇昂
    #
    # 如果你希望严格按“只有一个空格字符才切分”，可以改成：
    #   ws_count = len(re.findall(r"\s", s))
    #   if ws_count == 1 and len(segments) == 2:
    #       return segments[0], segments[1]
    if len(segments) == 2:
        return segments[0], segments[1]

    # 否则去掉全部空格，按字数规则切
    no_space = "".join(segments)
    return _split_by_length(no_space)


# ======================================================
# 6. 单侧解析
# ======================================================
def parse_party(raw: str) -> Party:
    """
    解析交易一方。

    输入可能形如：
      申港
      国泰海通
      国泰海通 林宇昂
      国泰海通 林宇昂 QT 0123456789
      兴业银行 韩立i0123456789
    """
    s = _strip_boundary(raw)
    s = s.replace("\u3000", " ")

    # 先找10位数字账号
    accounts = ACCOUNT_RE.findall(s)
    account = accounts[0] if accounts else None

    # 清洗文本：去掉数字、字母、标点、账号前置符等
    cleaned = _clean_party_text(s)

    # 切机构名、人名
    org, person = _split_org_person(cleaned)

    return Party(
        raw=s,
        org=org,
        person=person,
        account=account,
        accounts=accounts,
    )


# ======================================================
# 7. 整条交易链解析
# ======================================================
def parse_trade(text: str) -> Dict[str, Any]:
    """
    解析整条交易文本。

    支持：
      【申港to国泰海通】
      【国泰海通 林宇昂 QT 0123456789 to 华创杨文昊】
      【兴业银行 韩立i0123456789 出给 浙商城投】
      【兴业银行 韩立i0123456789 to 国泰海通 林宇昂 QT 0123456789 to 华创杨文昊】

    返回：
      seller: 卖出方
      bridge: 第一个过桥方，便于查看
      bridges: 所有过桥方列表
      buyer: 买入方
    """
    original = text.strip()
    s = _strip_boundary(original)
    s = s.replace("\u3000", " ")

    # 找出所有分隔词
    separators = [m.group(0).strip() for m in SEP_RE.finditer(s)]

    # 按分隔词切段
    parts_raw = [p.strip() for p in SEP_RE.split(s) if p and p.strip()]

    if len(parts_raw) < 2:
        return {
            "ok": False,
            "raw": original,
            "normalized": s,
            "separators": separators,
            "errors": [
                "no_valid_separator",
                "未找到有效分隔词，可补充 SEP_WORDS，例如：to/卖给/出给/出/卖出",
            ],
            "seller": None,
            "bridge": None,
            "bridges": [],
            "buyer": None,
            "parties": [],
        }

    parties = [parse_party(p) for p in parts_raw]

    seller = parties[0]
    buyer = parties[-1]
    bridges = parties[1:-1] if len(parties) >= 3 else []

    errors = []

    if not seller.org:
        errors.append("seller_org_missing")

    for idx, bridge in enumerate(bridges, start=1):
        if not bridge.org:
            errors.append(f"bridge_{idx}_org_missing")

    if not buyer.org:
        errors.append("buyer_org_missing")

    # 构造带角色的 parties 列表
    roles = ["seller"] + ["bridge"] * len(bridges) + ["buyer"]
    parties_payload = [
        {
            "role": role,
            **party.to_dict(),
        }
        for role, party in zip(roles, parties)
    ]

    return {
        "ok": True,
        "raw": original,
        "normalized": s,
        "separators": separators,
        "errors": errors,
        "seller": seller.to_dict(),
        "bridge": bridges[0].to_dict() if bridges else None,
        "bridges": [b.to_dict() for b in bridges],
        "buyer": buyer.to_dict(),
        "parties": parties_payload,
    }


# ======================================================
# 8. 测试示例
# ======================================================
if __name__ == "__main__":
    import json

    examples = [
        "【申港to国泰海通】",
        "【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】",
        "【兴业银行 韩立i0123456789 出给 浙商城投】",
        "【兴业银行 韩立i0123456789 to 国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】",
        "招商证券 王五 QQ 1234567890 卖给 平安理财 to 中信证券 赵六",
    ]

    for text in examples:
        result = parse_trade(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-" * 100)
```

---

## 二、你这个过桥例子的解析结果

输入：

```text
【兴业银行 韩立i0123456789 to 国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】
```

核心结果会是：

```json
{
  "ok": true,
  "separators": ["to", "to"],
  "errors": [],
  "seller": {
    "raw": "兴业银行 韩立i0123456789",
    "org": "兴业银行",
    "person": "韩立",
    "account": "0123456789",
    "accounts": ["0123456789"]
  },
  "bridge": {
    "raw": "国泰海通 林宇昂 QT 0123456789",
    "org": "国泰海通",
    "person": "林宇昂",
    "account": "0123456789",
    "accounts": ["0123456789"]
  },
  "bridges": [
    {
      "raw": "国泰海通 林宇昂 QT 0123456789",
      "org": "国泰海通",
      "person": "林宇昂",
      "account": "0123456789",
      "accounts": ["0123456789"]
    }
  ],
  "buyer": {
    "raw": "华创杨文昊",
    "org": "华创",
    "person": "杨文昊",
    "account": null,
    "accounts": []
  }
}
```

---

## 三、几个关键设计说明

### 1. 为什么用 `SEP_RE.split`？

因为一旦有过桥方，就不能只找第一个分隔词了。

例如：

```text
兴业银行 to 国泰海通 to 华创
```

如果只找第一个 `to`，会错误地认为：

```text
卖方：兴业银行
买方：国泰海通 to 华创
```

所以必须先切成：

```text
["兴业银行", "国泰海通", "华创"]
```

然后：

```text
parts[0]  -> seller
parts[-1] -> buyer
parts[1:-1] -> bridges
```

---

### 2. 为什么中间段可能有多个过桥方？

你当前例子是一个过桥方：

```text
A to B to C
```

但实际业务里可能出现：

```text
A to B to C to D
```

这时我建议：

```text
A: seller
B: bridge
C: bridge
D: buyer
```

所以代码里用的是：

```python
bridges = parties[1:-1]
```

如果你确定永远只有一个过桥方，也可以只取：

```python
bridge = bridges[0] if bridges else None
```

---

### 3. 关于单独的“出”字

你现在提到中间词有：

```text
to / 卖给 / 出给 / 出
```

我把单独的 `出` 也加进去了。

但注意，单独的 `出` 比较容易误切，比如：

```text
某机构出资
某机构出表
某机构出品
```

如果你发现误切严重，建议把：

```python
"出",
```

从 `SEP_WORDS` 里删掉，只保留：

```python
"出给",
"卖出",
"出售",
"卖给",
```

---

## 四、未来用 LLM 替代规则时的 Prompt，支持过桥方

下面这个 Prompt 可以让 LLM 输出结构化 JSON，支持：

```text
卖方
过桥方
买方
```

建议调用 LLM 时设置：

```python
temperature = 0
```

并强制模型只输出 JSON。

---

```text
你是金融产品交易要素抽取器。请从用户输入的短文本中抽取“卖出方”“过桥方/中间方”“买入方”。

输入文本通常类似：
- 【申港to国泰海通】
- 【国泰海通 林宇昂 QT 0123456789 to 华创杨文昊】
- 【兴业银行 韩立i0123456789 出给 浙商城投】
- 【兴业银行 韩立i0123456789 to 国泰海通 林宇昂 QT 0123456789 to 华创杨文昊】

你需要识别：
1. 卖出方：交易链最左侧，通常是 to/卖给/出给/卖出/出售/转让 等分隔词左侧的第一段。
2. 买入方：交易链最右侧，通常是最后一个分隔词右侧的最后一段。
3. 过桥方/中间方：如果存在 A to B to C，则 A 是卖出方，B 是过桥方，C 是买入方。
4. 如果存在 A to B to C to D，则 A 是卖出方，D 是买入方，B 和 C 都按顺序作为过桥方。
5. 每一方都可能包含：
   - 机构名：必有字段，必须尽量抽取出来。
   - 联系人姓名：可选。
   - 数字账号：可选，例如 QQ、微信、手机号等。

只输出合法 JSON，不要输出 Markdown，不要输出解释，不要输出多余文本。

输出格式必须如下：
{
  "seller": {
    "org": string,
    "person": string | null,
    "account": string | null
  },
  "bridges": [
    {
      "org": string,
      "person": string | null,
      "account": string | null
    }
  ],
  "buyer": {
    "org": string,
    "person": string | null,
    "account": string | null
  },
  "errors": string[]
}

抽取规则：

1. 方向判断
   - 如果文本为 A to B，则 A 是卖出方，B 是买入方，bridges 为空数组。
   - 如果文本为 A to B to C，则 A 是卖出方，B 是过桥方，C 是买入方。
   - 如果文本为 A 卖给 B，A 是卖出方，B 是买入方。
   - 如果文本为 A 出给 B，A 是卖出方，B 是买入方。
   - 如果出现多个连续交易方，按从左到右顺序理解：第一个是卖出方，最后一个是买入方，中间都是过桥方。
   - 不要编造原文中不存在的一方。

2. 机构名
   - 每个交易方必须抽取机构名 org。
   - 保留原文中的机构简称，不要扩写，不要翻译。
   - 例如：申港、国泰海通、华创、浙商城投、兴业银行 都应作为机构名。
   - 如果某一方无法识别机构名，将 org 设为空字符串，并在 errors 中加入对应错误：
     - "seller_org_missing"
     - "buyer_org_missing"
     - "bridge_org_missing"

3. 人名
   - 人名通常是联系人姓名，一般为2到3个汉字。
   - 如果机构名和人名连在一起，请根据上下文拆分。
   - 例如：华创杨文昊 应拆为机构名 华创，人名 杨文昊。
   - 例如：国泰海通林宇昂 应拆为机构名 国泰海通，人名 林宇昂。
   - 例如：兴业银行韩立 应拆为机构名 兴业银行，人名 韩立。
   - 如果不确定某个片段是否是人名，返回 null，不要强行猜测。

4. 数字账号
   - 数字账号通常是 QQ、微信、手机号等连续数字。
   - 优先识别10位数字，但不要绝对排斥其他长度；如果上下文明显是联系方式，也可以抽取。
   - 保留前导0，输出为字符串。
   - 去掉数字前的 i、QT、QQ、qq、QQ号、微信、微信号 等前缀。
   - 例如：
     - QT 0123456789 -> account: "0123456789"
     - 韩立i0123456789 -> person: "韩立", account: "0123456789"
     - 王五 QQ 1234567890 -> person: "王五", account: "1234567890"

5. 过桥方
   - 如果没有过桥方，bridges 必须是空数组 []。
   - 如果只有一个过桥方，bridges 是长度为1的数组。
   - 如果有多个中间方，按原文出现顺序放入 bridges。
   - 过桥方也需要尽量抽取机构名、人名、账号。

6. 清洗规则
   - 去除括号【】、分隔词、标点、多余空格。
   - 不要把分隔词、账号前缀、标点符号混入机构名或人名。
   - 不要把机构后缀如 证券、银行、资管、基金、信托、期货、城投 等误认为人名。

7. 输出要求
   - 必须只输出 JSON。
   - 如果字段不存在，使用 null。
   - errors 为空数组表示成功。

示例1：
输入：
【申港to国泰海通】
输出：
{
  "seller": {
    "org": "申港",
    "person": null,
    "account": null
  },
  "bridges": [],
  "buyer": {
    "org": "国泰海通",
    "person": null,
    "account": null
  },
  "errors": []
}

示例2：
输入：
【国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】
输出：
{
  "seller": {
    "org": "国泰海通",
    "person": "林宇昂",
    "account": "0123456789"
  },
  "bridges": [],
  "buyer": {
    "org": "华创",
    "person": "杨文昊",
    "account": null
  },
  "errors": []
}

示例3：
输入：
【兴业银行 韩立i0123456789 出给 浙商城投】
输出：
{
  "seller": {
    "org": "兴业银行",
    "person": "韩立",
    "account": "0123456789"
  },
  "bridges": [],
  "buyer": {
    "org": "浙商城投",
    "person": null,
    "account": null
  },
  "errors": []
}

示例4：
输入：
【兴业银行 韩立i0123456789 to 国泰海通 林宇昂 QT 0123456789   to 华创杨文昊】
输出：
{
  "seller": {
    "org": "兴业银行",
    "person": "韩立",
    "account": "0123456789"
  },
  "bridges": [
    {
      "org": "国泰海通",
      "person": "林宇昂",
      "account": "0123456789"
    }
  ],
  "buyer": {
    "org": "华创",
    "person": "杨文昊",
    "account": null
  },
  "errors": []
}

现在请处理下面输入：
{{用户输入}}
```

---

## 五、后续如果上 LLM，我建议的最终结构

你最终可以保留两套逻辑：

```text
规则版：快、便宜、可解释，适合明确格式。
LLM版：容错强，适合脏数据、非标准表达。
```

推荐流程：

```text
1. 先用规则版 parse_trade()
2. 如果解析失败，或者 org 缺失，则调用 LLM
3. LLM 返回 JSON 后，再做一层校验：
   - seller 是否存在
   - buyer 是否存在
   - bridges 是否为 list
   - account 是否为字符串
   - org 是否为空
4. 最后落库
```

这样可以既控制成本，又提高脏数据下的鲁棒性。


---
🙋**user**:
---
```
我确定只有一个bridge。帮我精简最后的parse_trade函数
```

---
🤖**assistant**:
---

可以。如果**确定最多只有一个过桥方**，`parse_trade` 可以精简成下面这样：

- 2 段：`卖方 to 买方`
- 3 段：`卖方 to 过桥方 to 买方`
- 超过 3 段：默认视为异常，或者你也可以选择只取第一个过桥方。

下面给你一个精简版，只返回：

```python
seller
bridge
buyer
```

不再返回 `bridges` 列表。

---

## 精简版 `parse_trade`

```python
def parse_trade(text: str) -> Dict[str, Any]:
    s = text.strip()
    s = s.strip("【】[]{}()（）<>《》").strip()
    s = s.replace("\u3000", " ")

    parts = [p.strip() for p in SEP_RE.split(s) if p.strip()]

    if len(parts) < 2:
        return {
            "ok": False,
            "raw": text.strip(),
            "error": "未找到有效分隔词或交易方不足",
            "seller": None,
            "bridge": None,
            "buyer": None,
        }

    if len(parts) == 2:
        seller_raw, buyer_raw = parts
        bridge_raw = None

    elif len(parts) == 3:
        seller_raw, bridge_raw, buyer_raw = parts

    else:
        return {
            "ok": False,
            "raw": text.strip(),
            "error": f"交易段数为{len(parts)}，超过预期的最多1个过桥方",
            "seller": None,
            "bridge": None,
            "buyer": None,
        }

    seller = parse_party(seller_raw)
    bridge = parse_party(bridge_raw) if bridge_raw else None
    buyer = parse_party(buyer_raw)

    errors = []

    if not seller.org:
        errors.append("seller_org_missing")

    if bridge and not bridge.org:
        errors.append("bridge_org_missing")

    if not buyer.org:
        errors.append("buyer_org_missing")

    return {
        "ok": not errors,
        "raw": text.strip(),
        "errors": errors,
        "seller": seller.to_dict(),
        "bridge": bridge.to_dict() if bridge else None,
        "buyer": buyer.to_dict(),
    }
```

---

## 如果你希望超过 3 段时也不要报错，而是强制只取一个过桥方

可以改成这个版本：

```python
def parse_trade(text: str) -> Dict[str, Any]:
    s = text.strip()
    s = s.strip("【】[]{}()（）<>《》").strip()
    s = s.replace("\u3000", " ")

    parts = [p.strip() for p in SEP_RE.split(s) if p.strip()]

    if len(parts) < 2:
        return {
            "ok": False,
            "raw": text.strip(),
            "error": "未找到有效分隔词或交易方不足",
            "seller": None,
            "bridge": None,
            "buyer": None,
        }

    seller_raw = parts[0]
    buyer_raw = parts[-1]

    if len(parts) >= 3:
        bridge_raw = parts[1]
    else:
        bridge_raw = None

    seller = parse_party(seller_raw)
    bridge = parse_party(bridge_raw) if bridge_raw else None
    buyer = parse_party(buyer_raw)

    errors = []

    if not seller.org:
        errors.append("seller_org_missing")

    if bridge and not bridge.org:
        errors.append("bridge_org_missing")

    if not buyer.org:
        errors.append("buyer_org_missing")

    return {
        "ok": not errors,
        "raw": text.strip(),
        "errors": errors,
        "seller": seller.to_dict(),
        "bridge": bridge.to_dict() if bridge else None,
        "buyer": buyer.to_dict(),
    }
```

---

## 推荐你用哪个？

如果你业务上**确定只有一个过桥方**，但数据可能偶尔脏，我建议用第二个版本：

```python
seller_raw = parts[0]
buyer_raw = parts[-1]
bridge_raw = parts[1] if len(parts) >= 3 else None
```

这样即使出现：

```text
A to B to C to D
```

它也会解析成：

```text
seller = A
bridge = B
buyer = D
```

不会因为多一个分隔词直接失败。

但如果你希望数据严格规范，出现超过 3 段就报警，用第一个版本。


---
🙋**user**:
---
```
帮我写一个函数 _sanitize_org_name, 它尽量从诸如:
【卖出 国泰证券】【买入 兴业银行】
这样的文字中，含金融机构常见字（比如证、银、投、资、金等）最多的连续非空字符
```

---
🤖**assistant**:
---

可以。这里给你一个 `_sanitize_org_name`，它会：

1. 把括号、空白、标点等当作分隔符；
2. 找出候选连续文本块；
3. 过滤掉 `卖出`、`买入`、`过桥` 这类非机构词；
4. 按“金融机构常见字”出现次数打分；
5. 同分时优先选更长的；
6. 还同分时取先出现的。

例如：

```text
【卖出 国泰证券】【买入 兴业银行】
```

会优先返回：

```text
国泰证券
```

因为 `国泰证券` 和 `兴业银行` 都含 2 个机构常见字，但 `国泰证券` 出现在前面。

---

## 函数代码

```python
import re

# 金融机构常见字，可自行增删
_ORG_HINT_CHARS = set("证银投资金信基财融控股权期券行保托管理")

# 常见非机构词，避免“卖出”“买入”被选中
_ORG_STOPWORDS = {
    "卖出",
    "买入",
    "卖方",
    "买方",
    "过桥",
    "过桥方",
    "中间",
    "中间方",
    "出让",
    "受让",
    "出售",
    "转让",
    "出给",
    "卖给",
    "出",
    "给",
    "to",
}

# 用非中文/字母/数字字符切块，等价于把括号、空白、标点当分隔符
_NON_ORG_TOKEN_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]+")

# 判断是否含中文
_CN_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _sanitize_org_name(text: str) -> str:
    """
    从一段脏文本中尽量选出最像金融机构名的连续字符块。

    规则：
    1. 括号、空白、标点作为分隔符；
    2. 过滤卖出、买入、过桥等非机构词；
    3. 优先选择含金融机构常见字最多的块；
    4. 同分时选择更长的块；
    5. 仍同分时选择先出现的块。
    """
    if not text:
        return ""

    text = text.replace("\u3000", " ")

    # 切成候选块
    tokens = [t for t in _NON_ORG_TOKEN_RE.split(text) if t]

    if not tokens:
        return ""

    # 过滤明显不是机构名的词
    tokens = [
        t for t in tokens
        if t.lower() not in _ORG_STOPWORDS
    ]

    if not tokens:
        return ""

    # 优先保留含中文的候选，避免 QT、QQ、纯数字账号干扰
    cn_tokens = [
        t for t in tokens
        if _CN_CHAR_RE.search(t) and not t.isdigit()
    ]

    if cn_tokens:
        tokens = cn_tokens

    def _score(token: str):
        # 机构常见字数量
        hint_count = sum(1 for ch in token if ch in _ORG_HINT_CHARS)

        # 同分时，偏好稍长一点的候选，但避免超长文本无限加分
        length_score = min(len(token), 12)

        return hint_count, length_score

    best = max(tokens, key=_score)
    return best
```

---

## 简单测试

```python
texts = [
    "【卖出 国泰证券】【买入 兴业银行】",
    "【卖出 国泰证券】",
    "【买入 兴业银行】",
    "国泰海通 林宇昂 QT 0123456789",
    "华创杨文昊",
    "兴业银行 韩立i0123456789",
    "浙商城投",
    "卖出 申港",
]

for text in texts:
    print(text, "=>", _sanitize_org_name(text))
```

输出大致会是：

```text
【卖出 国泰证券】【买入 兴业银行】 => 国泰证券
【卖出 国泰证券】 => 国泰证券
【买入 兴业银行】 => 兴业银行
国泰海通 林宇昂 QT 0123456789 => 国泰海通
华创杨文昊 => 华创杨文昊
兴业银行 韩立i0123456789 => 兴业银行
浙商城投 => 浙商城投
卖出 申港 => 申港
```

---

## 如果你希望同分时返回最后一个

比如：

```text
【卖出 国泰证券】【买入 兴业银行】
```

你想返回 `兴业银行`，可以把最后这一句：

```python
best = max(tokens, key=_score)
```

改成：

```python
best = max(reversed(tokens), key=_score)
```

这样同分时会优先取后出现的候选。

---

## 如果你希望返回所有最高分候选

可以写一个小变体：

```python
def _sanitize_org_names(text: str) -> list[str]:
    if not text:
        return []

    text = text.replace("\u3000", " ")

    tokens = [t for t in _NON_ORG_TOKEN_RE.split(text) if t]
    tokens = [t for t in tokens if t.lower() not in _ORG_STOPWORDS]

    if not tokens:
        return []

    cn_tokens = [
        t for t in tokens
        if _CN_CHAR_RE.search(t) and not t.isdigit()
    ]

    if cn_tokens:
        tokens = cn_tokens

    def _score(token: str):
        hint_count = sum(1 for ch in token if ch in _ORG_HINT_CHARS)
        length_score = min(len(token), 12)
        return hint_count, length_score

    best_score = max(_score(t) for t in tokens)

    return [
        t for t in tokens
        if _score(t) == best_score
    ]
```

测试：

```python
print(_sanitize_org_names("【卖出 国泰证券】【买入 兴业银行】"))
```

输出：

```python
['国泰证券', '兴业银行']
```

---

## 一个额外建议

如果你明确知道文本里有：

```text
【卖出 国泰证券】
【买入 兴业银行】
```

其实更好的做法是先按角色切，再调用 `_sanitize_org_name`。

例如：

```python
def _extract_org_by_role(text: str, role: str) -> str:
    """
    从类似 【卖出 国泰证券】【买入 兴业银行】 的文本中按角色提取机构名。
    role 可以是：卖出、买入、卖方、买方、过桥
    """
    pattern = re.compile(
        r"【\s*" + re.escape(role) + r"\s*([^】]*)】",
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if not m:
        return ""
    return _sanitize_org_name(m.group(1))
```

测试：

```python
text = "【卖出 国泰证券】【买入 兴业银行】"

print(_extract_org_by_role(text, "卖出"))  # 国泰证券
print(_extract_org_by_role(text, "买入"))  # 兴业银行
```

这样比把整段都丢进 `_sanitize_org_name` 更稳定。


---
🙋**user**:
---
```
我有一张交易员姓名-qq号白名单csv格式，我希望从文本text中，以一定的逻辑梯次，一次完成 姓名+qq号的提取：
1. 如果匹配到了 姓名+10位qq号（中间相隔不多的字符），那根据 白名单给出标准姓名+qq号，置信度10
2. 如果只匹配到了10为qq号（前面最多只有一些前置符比如i、qq、qt等），那根据白名单给出标准名字+qq号，置信度10
3. 如果只匹配到了姓名，那么根据白名单给出名字+qq号，置信度6
4. 如果没有匹配到白名单中的姓名和qq号，但是我有一个从LLM输出的姓名，那么尝试根据白名单给出最接近的名字+qq号，置信度4
```

---
🤖**assistant**:
---

下面给你一个**一次性按梯次提取交易员标准姓名 + QQ 号**的函数。

它的逻辑是：

1. **优先级 10：姓名 + 10位QQ号近距离共现**
   - 文本里同时出现白名单姓名和 10 位数字；
   - 两者距离不超过 `max_gap`；
   - 返回白名单中的标准姓名和标准 QQ；
   - 置信度 `10`。

2. **优先级 10：只匹配到白名单中的 10位QQ号**
   - 文本里没有明确白名单姓名，或者姓名不重要；
   - 但 10 位 QQ 号在白名单中；
   - 返回白名单中的标准姓名和标准 QQ；
   - 置信度 `10`。

3. **优先级 6：只匹配到白名单姓名**
   - 文本里出现白名单姓名；
   - 没匹配到有效白名单 QQ；
   - 返回白名单中的标准姓名和标准 QQ；
   - 置信度 `6`。

4. **优先级 4：文本没命中白名单，但有 LLM 输出的姓名**
   - 使用 `llm_name` 和白名单做模糊匹配；
   - 返回最接近的白名单姓名和 QQ；
   - 置信度 `4`。

---

## 一、完整代码

```python
import csv
import difflib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


# ============================================================
# 基础正则
# ============================================================

# 10位QQ号，前后不能还有数字，避免从11位手机号中间切出10位
QQ_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")

# 中文姓名最小长度，避免单字误匹配
MIN_NAME_LEN = 2

# 白名单CSV可能使用的列名
_NAME_KEYS = {
    "name",
    "姓名",
    "交易员",
    "交易员姓名",
    "交易员名称",
    "trader",
    "trader_name",
    "用户名",
}

_QQ_KEYS = {
    "qq",
    "qq号",
    "qq账号",
    "qq_account",
    "account",
    "账号",
    "账户",
    "联系方式",
}


# ============================================================
# 数据结构
# ============================================================

@dataclass(frozen=True)
class Trader:
    name: str
    qq: str


# Span: start, end, value
Span = Tuple[int, int, str]


# ============================================================
# 白名单读取
# ============================================================

def _get_field(row: Dict[str, Any], keys: set) -> str:
    """
    从dict行里按候选列名取字段。
    支持列名大小写不一致。
    """
    for k, v in row.items():
        if k is None:
            continue
        if str(k).strip().lower() in keys:
            return "" if v is None else str(v).strip()
    return ""


def load_trader_whitelist(
    source: Union[str, Path, List[Dict[str, Any]]],
    encoding: str = "utf-8-sig",
) -> List[Trader]:
    """
    读取交易员白名单。

    支持：
      1. CSV文件路径
      2. List[Dict]，例如 csv.DictReader 读出来的结果

    CSV列名支持：
      - name / 姓名 / 交易员 / 交易员姓名
      - qq / QQ号 / qq账号 / 账号

    返回：
      [Trader(name='张三', qq='1234567890'), ...]
    """
    if isinstance(source, (str, Path)):
        with open(source, encoding=encoding, newline="") as f:
            rows = list(csv.DictReader(f))
    elif isinstance(source, list):
        rows = source
    else:
        raise TypeError("whitelist 必须是 CSV 路径或 List[Dict]")

    traders: List[Trader] = []
    seen = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        name = _get_field(row, _NAME_KEYS)
        qq_raw = _get_field(row, _QQ_KEYS)

        # 去掉姓名中的空白
        name = re.sub(r"\s+", "", name)

        # QQ只保留数字，保留前导0
        qq = re.sub(r"\D", "", qq_raw)

        if not name:
            continue

        if len(qq) != 10:
            continue

        key = (name, qq)
        if key in seen:
            continue

        seen.add(key)
        traders.append(Trader(name=name, qq=qq))

    return traders


def _build_indexes(
    traders: List[Trader],
) -> Tuple[Dict[str, List[Trader]], Dict[str, Trader]]:
    """
    构建：
      name -> [Trader]
      qq -> Trader
    """
    name_to_records: Dict[str, List[Trader]] = {}
    qq_to_record: Dict[str, Trader] = {}

    for trader in traders:
        name_to_records.setdefault(trader.name, []).append(trader)

        # 如果QQ重复，默认保留第一个
        if trader.qq not in qq_to_record:
            qq_to_record[trader.qq] = trader

    return name_to_records, qq_to_record


# ============================================================
# 文本中找到姓名、QQ号的位置
# ============================================================

def _dedupe_spans(spans: List[Span]) -> List[Span]:
    """
    去除重叠的候选片段。
    优先保留更长的片段。
    """
    spans = sorted(
        spans,
        key=lambda x: (-(x[1] - x[0]), x[0]),
    )

    kept: List[Span] = []

    for s, e, val in spans:
        overlapped = False
        for ks, ke, _ in kept:
            # 有重叠
            if not (e <= ks or s >= ke):
                overlapped = True
                break

        if not overlapped:
            kept.append((s, e, val))

    return sorted(kept, key=lambda x: x[0])


def _find_name_spans(
    text: str,
    names: Iterable[str],
    min_name_len: int = MIN_NAME_LEN,
) -> List[Span]:
    """
    在text中查找白名单姓名出现的位置。
    """
    spans: List[Span] = []

    # 长姓名优先，避免短姓名覆盖长姓名
    for name in sorted(set(names), key=len, reverse=True):
        if len(name) < min_name_len:
            continue

        for m in re.finditer(re.escape(name), text):
            spans.append((m.start(), m.end(), name))

    return _dedupe_spans(spans)


def _find_qq_spans(text: str) -> List[Span]:
    """
    在text中查找10位QQ号。
    """
    return [
        (m.start(), m.end(), m.group(1))
        for m in QQ_RE.finditer(text)
    ]


def _gap(span_a: Span, span_b: Span) -> int:
    """
    两个span之间的间隔字符数。
    如果重叠，返回0。
    """
    s1, e1, _ = span_a
    s2, e2, _ = span_b

    if e1 <= s2:
        return s2 - e1

    if e2 <= s1:
        return s1 - e2

    return 0


# ============================================================
# 模糊匹配：用于LLM姓名兜底
# ============================================================

def _normalize_name(name: Optional[str]) -> str:
    """
    只保留中文、字母、数字，去掉空白和标点。
    """
    if not name:
        return ""

    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", name)


def _fuzzy_match_name(
    llm_name: str,
    names: List[str],
    threshold: float = 0.62,
) -> Tuple[Optional[str], float, str]:
    """
    用LLM输出的姓名模糊匹配白名单姓名。

    返回：
      匹配到的白名单姓名, 相似度, 匹配方式
    """
    q = _normalize_name(llm_name)

    if not q:
        return None, 0.0, ""

    unique_names = list(dict.fromkeys(names))

    # 1. 如果LLM输出里直接包含白名单姓名，优先选最长的
    contained = [
        name
        for name in unique_names
        if len(name) >= MIN_NAME_LEN and name in q
    ]

    if contained:
        best = max(contained, key=len)
        return best, 1.0, "contained"

    # 2. 完全相等
    if q in unique_names:
        return q, 1.0, "exact"

    # 3. 模糊匹配
    candidates: List[Tuple[float, int, str]] = []

    for name in unique_names:
        score = difflib.SequenceMatcher(None, q, name).ratio()

        # 如果LLM输出带有机构名，比如：华创杨文浩
        # 直接全串相似度可能偏低，可以再看尾部2-3个字
        if len(q) >= 2 and len(name) >= 2:
            tail_len = min(3, len(q), len(name))
            tail_score = difflib.SequenceMatcher(
                None,
                q[-tail_len:],
                name[-tail_len:],
            ).ratio()

            # 尾部相似只作为辅助，略微降权，避免误配
            score = max(score, tail_score * 0.95)

        if score >= threshold:
            candidates.append((score, len(name), name))

    if not candidates:
        return None, 0.0, ""

    best_score, best_len, best_name = max(
        candidates,
        key=lambda x: (x[0], x[1]),
    )

    return best_name, best_score, "fuzzy"


# ============================================================
# 结果封装
# ============================================================

def _result(
    found: bool,
    name: Optional[str] = None,
    qq: Optional[str] = None,
    confidence: int = 0,
    matched_by: str = "",
    evidence: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "found": found,
        "name": name,
        "qq": qq,
        "confidence": confidence,
        "matched_by": matched_by,
        "evidence": evidence or {},
        "warnings": warnings or [],
    }


# ============================================================
# 主函数：从text中提取交易员姓名+QQ
# ============================================================

def extract_trader(
    text: str,
    whitelist: Union[str, Path, List[Trader], List[Dict[str, Any]]],
    llm_name: Optional[str] = None,
    max_gap: int = 10,
    encoding: str = "utf-8-sig",
) -> Dict[str, Any]:
    """
    从text中提取交易员标准姓名 + QQ号。

    参数：
      text:
        待匹配文本，建议传入某一方的原始文本，比如：
          "国泰海通 林宇昂 QT 0123456789"
        不建议把整条 A to B to C 都传进来，除非你只想从中找某一个交易员。

      whitelist:
        白名单，可以是：
          1. CSV路径
          2. List[Dict]
          3. List[Trader]

      llm_name:
        可选。当text里没有命中白名单姓名和QQ时，
        如果你有一个LLM输出的姓名，可以用它做模糊兜底。

      max_gap:
        姓名和10位QQ号之间允许的最大间隔字符数。

    返回：
      {
        "found": bool,
        "name": 标准姓名,
        "qq": 标准QQ,
        "confidence": 10/6/4/0,
        "matched_by": 匹配逻辑,
        "evidence": 证据,
        "warnings": 警告
      }
    """
    # 读取白名单
    if isinstance(whitelist, list) and whitelist and isinstance(whitelist[0], Trader):
        traders = whitelist
    else:
        traders = load_trader_whitelist(whitelist, encoding=encoding)

    if not traders:
        return _result(
            False,
            matched_by="empty_whitelist",
            warnings=["whitelist is empty"],
        )

    text = text.replace("\u3000", " ")

    name_to_records, qq_to_record = _build_indexes(traders)
    names = list(name_to_records.keys())

    name_spans = _find_name_spans(text, names)
    qq_spans = _find_qq_spans(text)

    warnings: List[str] = []

    # ========================================================
    # 优先级1：白名单姓名 + 白名单QQ 同时出现，且距离较近
    # ========================================================
    best_exact = None

    for rec in traders:
        ns_list = [x for x in name_spans if x[2] == rec.name]
        qs_list = [x for x in qq_spans if x[2] == rec.qq]

        if not ns_list or not qs_list:
            continue

        for ns in ns_list:
            for qs in qs_list:
                gap = _gap(ns, qs)

                if gap <= max_gap:
                    candidate = (gap, ns[0], qs[0], rec, ns, qs)

                    if best_exact is None or candidate[:3] < best_exact[:3]:
                        best_exact = candidate

    if best_exact:
        gap, _, _, rec, ns, qs = best_exact

        return _result(
            True,
            rec.name,
            rec.qq,
            10,
            "name_and_qq_in_whitelist",
            {
                "text_name": ns[2],
                "text_qq": qs[2],
                "gap": gap,
            },
        )

    # ========================================================
    # 优先级1.5：白名单姓名 + 附近任意10位QQ
    #
    # 用于：
    #   文本里姓名命中白名单，QQ格式正确但可能不在白名单中。
    #   此时仍按白名单姓名返回标准QQ。
    #
    # 注意：
    #   如果这个10位QQ属于白名单里的另一个人，则不采用，
    #   交给后面的QQ精确匹配。
    # ========================================================
    best_name_qq = None

    if name_spans and qq_spans:
        for ns in name_spans:
            recs = name_to_records.get(ns[2], [])

            if not recs:
                continue

            for qs in qq_spans:
                gap = _gap(ns, qs)

                if gap > max_gap:
                    continue

                qq_rec = qq_to_record.get(qs[2])

                # 如果QQ属于白名单中的另一个人，不要让姓名强行覆盖它
                if qq_rec and qq_rec.name != ns[2]:
                    continue

                rec = qq_rec or recs[0]

                # 越小越优先：
                # 1. 距离近
                # 2. 文本QQ和白名单QQ一致
                # 3. 姓名更长
                # 4. 出现位置靠前
                score = (
                    gap,
                    0 if qs[2] == rec.qq else 1,
                    -len(ns[2]),
                    ns[0],
                )

                if best_name_qq is None or score < best_name_qq[0]:
                    best_name_qq = (score, rec, ns, qs)

        if best_name_qq:
            _, rec, ns, qs = best_name_qq

            if qs[2] != rec.qq:
                warnings.append("text_qq_differs_from_whitelist")

            return _result(
                True,
                rec.name,
                rec.qq,
                10,
                "name_plus_nearby_qq",
                {
                    "text_name": ns[2],
                    "text_qq": qs[2],
                    "gap": _gap(ns, qs),
                },
                warnings=warnings,
            )

    # ========================================================
    # 优先级2：只匹配到白名单中的10位QQ号
    # ========================================================
    exact_qq_candidates = []

    for idx, qs in enumerate(qq_spans):
        rec = qq_to_record.get(qs[2])

        if not rec:
            continue

        # 如果这个QQ对应的姓名也在文本里，并且离得近，则更优先
        related_name_span = next(
            (
                ns
                for ns in name_spans
                if ns[2] == rec.name
            ),
            None,
        )

        if related_name_span is not None:
            gap = _gap(related_name_span, qs)
            nearby = 0 if gap <= max_gap else 1
        else:
            gap = 9999
            nearby = 2

        exact_qq_candidates.append(
            (nearby, gap, idx, rec, qs)
        )

    if exact_qq_candidates:
        _, _, _, rec, qs = min(
            exact_qq_candidates,
            key=lambda x: x[:3],
        )

        return _result(
            True,
            rec.name,
            rec.qq,
            10,
            "qq_only_in_whitelist",
            {
                "text_qq": qs[2],
            },
        )

    # ========================================================
    # 优先级3：只匹配到白名单姓名
    # ========================================================
    if name_spans:
        name_counter = Counter(x[2] for x in name_spans)

        first_pos: Dict[str, int] = {}
        for s, e, val in name_spans:
            if val not in first_pos:
                first_pos[val] = s

        best_name = max(
            name_counter,
            key=lambda n: (
                name_counter[n],   # 出现次数多优先
                len(n),            # 更长的姓名优先
                -first_pos[n],     # 更靠前的优先
            ),
        )

        rec = name_to_records[best_name][0]

        return _result(
            True,
            rec.name,
            rec.qq,
            6,
            "name_only_in_whitelist",
            {
                "text_name": best_name,
                "occurrences": name_counter[best_name],
            },
        )

    # ========================================================
    # 优先级4：文本没命中白名单，但有LLM输出的姓名
    # ========================================================
    if llm_name:
        matched_name, score, method = _fuzzy_match_name(
            llm_name,
            names,
        )

        if matched_name:
            rec = name_to_records[matched_name][0]

            return _result(
                True,
                rec.name,
                rec.qq,
                4,
                f"llm_name_fuzzy:{method}",
                {
                    "llm_name": llm_name,
                    "matched_name": matched_name,
                    "similarity": round(score, 4),
                },
            )

        warnings.append("llm_name_not_matched")

    else:
        warnings.append("no_llm_name")

    return _result(
        False,
        confidence=0,
        matched_by="not_found",
        warnings=warnings,
    )
```

---

## 二、使用示例

假设你有一个白名单 CSV：

```csv
姓名,QQ
林宇昂,0123456789
韩立,9876543210
杨文昊,1122334455
```

代码：

```python
whitelist = "trader_whitelist.csv"

texts = [
    "国泰海通 林宇昂 QT 0123456789",
    "QT 9876543210",
    "韩立 出给 浙商城投",
    "华创杨文浩",
]

for text in texts:
    result = extract_trader(
        text=text,
        whitelist=whitelist,
        llm_name="杨文浩" if "杨文浩" in text else None,
    )
    print(result)
```

---

## 三、预期结果

### 1. 姓名 + QQ 近距离共现

输入：

```text
国泰海通 林宇昂 QT 0123456789
```

返回：

```python
{
    "found": True,
    "name": "林宇昂",
    "qq": "0123456789",
    "confidence": 10,
    "matched_by": "name_and_qq_in_whitelist",
    "evidence": {
        "text_name": "林宇昂",
        "text_qq": "0123456789",
        "gap": 4
    },
    "warnings": []
}
```

---

### 2. 只匹配到白名单 QQ

输入：

```text
QT 9876543210
```

返回：

```python
{
    "found": True,
    "name": "韩立",
    "qq": "9876543210",
    "confidence": 10,
    "matched_by": "qq_only_in_whitelist",
    "evidence": {
        "text_qq": "9876543210"
    },
    "warnings": []
}
```

---

### 3. 只匹配到白名单姓名

输入：

```text
韩立 出给 浙商城投
```

返回：

```python
{
    "found": True,
    "name": "韩立",
    "qq": "9876543210",
    "confidence": 6,
    "matched_by": "name_only_in_whitelist",
    "evidence": {
        "text_name": "韩立",
        "occurrences": 1
    },
    "warnings": []
}
```

---

### 4. 文本没命中白名单，但 LLM 姓名可模糊匹配

假设白名单里是：

```text
杨文昊,1122334455
```

输入文本：

```text
华创杨文浩
```

同时传入：

```python
llm_name="杨文浩"
```

返回：

```python
{
    "found": True,
    "name": "杨文昊",
    "qq": "1122334455",
    "confidence": 4,
    "matched_by": "llm_name_fuzzy:fuzzy",
    "evidence": {
        "llm_name": "杨文浩",
        "matched_name": "杨文昊",
        "similarity": 0.667
    },
    "warnings": []
}
```

---

## 四、建议你怎么接入之前的交易解析流程

你之前的 `parse_trade` 会得到：

```python
seller["raw"]
bridge["raw"]
buyer["raw"]
```

建议不要直接把整条交易文本传给 `extract_trader`，而是对每一方分别调用：

```python
trade = parse_trade(text)

seller_trader = extract_trader(
    text=trade["seller"]["raw"],
    whitelist="trader_whitelist.csv",
    llm_name=None,
)

bridge_trader = None
if trade["bridge"]:
    bridge_trader = extract_trader(
        text=trade["bridge"]["raw"],
        whitelist="trader_whitelist.csv",
        llm_name=None,
    )

buyer_trader = extract_trader(
    text=trade["buyer"]["raw"],
    whitelist="trader_whitelist.csv",
    llm_name=None,
)
```

如果你后面有 LLM 输出的姓名，比如：

```python
llm_result = {
    "seller_person": "林宇昂",
    "bridge_person": None,
    "buyer_person": "杨文浩",
}
```

可以这样：

```python
seller_trader = extract_trader(
    text=trade["seller"]["raw"],
    whitelist="trader_whitelist.csv",
    llm_name=llm_result.get("seller_person"),
)

buyer_trader = extract_trader(
    text=trade["buyer"]["raw"],
    whitelist="trader_whitelist.csv",
    llm_name=llm_result.get("buyer_person"),
)
```

---

## 五、几个关键参数说明

### 1. `max_gap`

默认：

```python
max_gap=10
```

表示姓名和 10 位 QQ 之间最多允许 10 个字符间隔。

例如：

```text
林宇昂 QT 0123456789
```

中间是：

```text
 QT 
```

大概 4 个字符，可以命中。

如果你的数据里经常这样写：

```text
国泰海通 林宇昂 QT 0123456789
```

也建议按“单侧文本”传入，即传：

```text
林宇昂 QT 0123456789
```

或者：

```text
国泰海通 林宇昂 QT 0123456789
```

一般也能命中。

如果你发现误匹配太多，可以调小：

```python
max_gap=6
```

如果你发现漏匹配太多，可以调大：

```python
max_gap=15
```

---

### 2. 白名单 CSV 的 QQ 必须保留前导 0

例如：

```text
0123456789
```

最好不要让 Excel 自动转成数字，否则前导 0 会丢。

推荐 CSV 里这样保存：

```csv
姓名,QQ
林宇昂,"0123456789"
```

或者把 CSV 当纯文本处理，不要用 Excel 编辑后丢失前导 0。

---

### 3. 如果同名不同 QQ

代码支持一个姓名对应多个 QQ：

```csv
姓名,QQ
张三,1111111111
张三,2222222222
```

优先级如下：

1. 如果文本中同时出现 `张三` 和 `1111111111`，优先返回这个张三；
2. 如果只出现 `张三`，默认返回白名单中第一个张三；
3. 如果只出现某个 QQ，则按 QQ 精确返回。

---

## 六、如果你想要极简版

如果你不需要证据、警告、复杂冲突处理，只要一个简版，可以用下面这个：

```python
import csv
import difflib
import re
from typing import Optional, Tuple, Dict, Any


QQ_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")


def load_whitelist(csv_path: str, encoding: str = "utf-8-sig") -> Dict[str, str]:
    """
    返回：
      {
        "姓名": "QQ",
        ...
      }
    """
    name_to_qq = {}

    with open(csv_path, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            name = None
            qq = None

            for k, v in row.items():
                key = k.strip().lower()

                if key in {"name", "姓名", "交易员", "交易员姓名"}:
                    name = v.strip() if v else ""

                if key in {"qq", "qq号", "qq账号", "账号", "account"}:
                    qq = re.sub(r"\D", "", v or "")

            if name and len(qq) == 10:
                name_to_qq[name] = qq

    return name_to_qq


def extract_trader_simple(
    text: str,
    name_to_qq: Dict[str, str],
    llm_name: Optional[str] = None,
    max_gap: int = 10,
) -> Optional[Tuple[str, str, int]]:
    """
    返回：
      (标准姓名, 标准QQ, 置信度)

    找不到返回：
      None
    """
    text = text.replace("\u3000", " ")

    names = list(name_to_qq.keys())
    qq_to_name = {qq: name for name, qq in name_to_qq.items()}

    qq_matches = list(QQ_RE.finditer(text))

    name_matches = []
    for name in sorted(names, key=len, reverse=True):
        if len(name) < 2:
            continue
        for m in re.finditer(re.escape(name), text):
            name_matches.append((name, m.start(), m.end()))

    # 1. 姓名 + 10位QQ近距离共现
    for name, ns, ne in name_matches:
        for m in qq_matches:
            qs, qe = m.start(), m.end()

            if ne <= qs:
                gap = qs - ne
            elif qe <= ns:
                gap = ns - qe
            else:
                gap = 0

            if gap <= max_gap:
                return name, name_to_qq[name], 10

    # 2. 只匹配到白名单QQ
    for m in qq_matches:
        qq = m.group(1)
        if qq in qq_to_name:
            return qq_to_name[qq], qq, 10

    # 3. 只匹配到白名单姓名
    if name_matches:
        name = name_matches[0][0]
        return name, name_to_qq[name], 6

    # 4. LLM姓名模糊匹配
    if llm_name:
        best_name = None
        best_score = 0.0

        for name in names:
            score = difflib.SequenceMatcher(None, llm_name, name).ratio()

            if name in llm_name or llm_name in name:
                score = max(score, 0.9)

            if score > best_score:
                best_score = score
                best_name = name

        if best_name and best_score >= 0.6:
            return best_name, name_to_qq[best_name], 4

    return None
```

使用：

```python
name_to_qq = load_whitelist("trader_whitelist.csv")

print(
    extract_trader_simple(
        "国泰海通 林宇昂 QT 0123456789",
        name_to_qq,
    )
)
```

输出：

```python
('林宇昂', '0123456789', 10)
```

---

我建议你生产环境用上面**完整版**，因为完整版处理了这些细节：

1. 姓名和 QQ 距离；
2. 多个候选姓名；
3. 多个候选 QQ；
4. QQ 属于另一个白名单交易员时的冲突；
5. 文本 QQ 和白名单 QQ 不一致时的警告；
6. LLM 姓名带机构名时的模糊匹配；
7. 返回证据，便于你后续排查。


---
🙋**user**:
---
```
我从 trade_parties / cust_info 等得到了多个的如下结构的 客户信息：
{
"raw":
"org":
"person":
"account":
"accounts":
}
seller、buyer如果分隔正确，也在其中。我现在希望实现如下逻辑：
当seller 和 buyer正确分隔出来时，希望从其他所有的结构体收集信息，将org、person、account三个字段补齐
```

---
🤖**assistant**:
---

可以。你这个需求建议做成一个**只补不覆盖**的 enrich 逻辑：

- `seller`、`buyer` 已经正确分隔出来后，以它们为目标；
- 从其他候选结构体里找“同一个客户/交易员”的信息；
- 用已有字段做关联，优先级建议是：
  1. `account / accounts` 相同；
  2. `person` 相同；
  3. `org` 相同或包含；
  4. `raw` 相同或包含；
- 只补齐目标里为空的 `org`、`person`、`account`；
- 不覆盖已经有值的字段。

下面给你一套完整代码。

---

## 1. 完整代码

```python
import re
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple


Party = Dict[str, Any]

# 需要补齐的字段
FILL_FIELDS = ("org", "person", "account")


# ============================================================
# 基础工具
# ============================================================

def _is_empty(value: Any) -> bool:
    """
    判断字段是否为空。
    """
    return value is None or str(value).strip() == ""


def _norm_text(value: Any) -> str:
    """
    文本归一化：只保留中文、字母、数字，并转小写。
    用于匹配，不用于最终输出。
    """
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", str(value or "")).lower()


def _clean_qq(value: Any) -> str:
    """
    清洗QQ/账号：只保留数字，并且只认为10位数字是有效QQ。
    保留前导0。
    """
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 else ""


def _get_accounts(party: Party) -> List[str]:
    """
    从一个party结构中提取所有有效10位QQ。
    优先使用 account，再使用 accounts。
    """
    if not party:
        return []

    accounts: List[str] = []

    source = [party.get("account")]
    source.extend(party.get("accounts") or [])

    for acc in source:
        qq = _clean_qq(acc)
        if qq and qq not in accounts:
            accounts.append(qq)

    return accounts


def _get_field_values(party: Party, field: str) -> List[str]:
    """
    获取某个party中某个字段的可填值列表。
    """
    if not party:
        return []

    if field == "account":
        return _get_accounts(party)

    value = party.get(field)

    if _is_empty(value):
        return []

    value = str(value).strip()

    # 人名通常不应保留空格
    if field == "person":
        value = re.sub(r"\s+", "", value)

    return [value] if value else []


def _completeness(party: Party) -> int:
    """
    计算一个party已有字段的完整度。
    越完整越优先。
    """
    if not party:
        return 0

    return sum(
        1
        for field in FILL_FIELDS
        if not _is_empty(party.get(field))
    )


# ============================================================
# 候选匹配打分
# ============================================================

def _match_score(target: Party, candidate: Party) -> Tuple[int, List[str]]:
    """
    判断 candidate 是否可能和 target 是同一个交易方。

    打分规则：
      - account相同：100
      - person相同：80
      - org完全相同：70
      - org包含关系：60
      - org模糊相似：可选低分
      - raw完全相同：65
      - raw包含关系：18

    返回：
      (分数, 匹配原因)
    """
    if not target or not candidate:
        return 0, []

    score = 0
    reasons: List[str] = []

    # 1. account相同，最强
    t_accounts = set(_get_accounts(target))
    c_accounts = set(_get_accounts(candidate))

    if t_accounts & c_accounts:
        score += 100
        reasons.append("account")

    # 2. person相同
    t_person = _norm_text(target.get("person"))
    c_person = _norm_text(candidate.get("person"))

    if t_person and c_person and t_person == c_person:
        score += 80
        reasons.append("person")

    # 3. org相同或包含
    t_org = _norm_text(target.get("org"))
    c_org = _norm_text(candidate.get("org"))

    if t_org and c_org:
        if t_org == c_org:
            score += 70
            reasons.append("org")

        elif t_org in c_org or c_org in t_org:
            score += 60
            reasons.append("org_contains")

        else:
            sim = SequenceMatcher(None, t_org, c_org).ratio()

            # 模糊机构名默认分数不高。
            # 如果你希望模糊机构名也能补，可以把 min_score 调到40或更低。
            if sim >= 0.78:
                score += int(30 + 25 * sim)
                reasons.append("org_fuzzy")

    # 4. raw相同或包含
    t_raw = _norm_text(target.get("raw"))
    c_raw = _norm_text(candidate.get("raw"))

    if t_raw and c_raw:
        if t_raw == c_raw:
            score += 65
            reasons.append("raw_same")

        elif len(t_raw) >= 4 and len(c_raw) >= 4 and (t_raw in c_raw or c_raw in t_raw):
            score += 18
            reasons.append("raw_contains")

    return score, reasons


# ============================================================
# 从候选中投票选择最佳补齐值
# ============================================================

def _choose_best_value(
    field: str,
    scored_candidates: List[Tuple[int, int, int, Party]],
) -> Optional[str]:
    """
    从候选中选择某个字段的最佳补齐值。

    选择依据：
      1. 总匹配分数高；
      2. 出现次数多；
      3. 单条候选最高匹配分数高；
      4. 候选结构完整度高；
      5. 出现更早。
    """
    votes: Dict[str, Dict[str, Any]] = {}
    order = 0

    for score, completeness, _, cand in scored_candidates:
        values = _get_field_values(cand, field)

        for value in values:
            if field == "account":
                key = value
            else:
                key = _norm_text(value)

            if not key:
                continue

            if key not in votes:
                votes[key] = {
                    "value": value,
                    "score_sum": 0,
                    "count": 0,
                    "best_score": 0,
                    "best_completeness": 0,
                    "first_order": order,
                }

            item = votes[key]
            item["score_sum"] += score
            item["count"] += 1

            if (
                score > item["best_score"]
                or (
                    score == item["best_score"]
                    and completeness > item["best_completeness"]
                )
            ):
                item["best_score"] = score
                item["best_completeness"] = completeness

            order += 1

    if not votes:
        return None

    best = max(
        votes.values(),
        key=lambda x: (
            x["score_sum"],
            x["count"],
            x["best_score"],
            x["best_completeness"],
            -x["first_order"],
        ),
    )

    return best["value"]


# ============================================================
# 单个party补齐
# ============================================================

def enrich_party(
    party: Optional[Party],
    candidates: Iterable[Party],
    fields: Iterable[str] = FILL_FIELDS,
    min_score: int = 60,
    max_rounds: int = 2,
    inplace: bool = False,
) -> Optional[Party]:
    """
    用候选结构体补齐一个party的 org / person / account。

    参数：
      party:
        目标结构体，比如 seller 或 buyer。

      candidates:
        其他候选结构体列表。

      fields:
        需要补齐的字段，默认是 ("org", "person", "account")。

      min_score:
        候选匹配最低分。
        默认60：
          - account相同可补
          - person相同可补
          - org完全相同可补
          - org包含可补
          - raw完全相同可补
        如果你希望模糊机构名也参与，可以调低到40。

      max_rounds:
        补齐轮数。
        例如目标只有 account：
          第一轮通过 account 补出 org；
          第二轮可以通过新补出的 org 再补 person。
        默认2轮。

      inplace:
        是否直接修改原party。
        False：返回deepcopy后的新party。
        True：直接修改原party。

    返回：
      补齐后的party。
    """
    if not party:
        return party

    out = party if inplace else deepcopy(party)
    fields = tuple(fields)
    candidates = [c for c in candidates or [] if c]

    for _ in range(max(1, max_rounds)):
        scored = []

        for cand in candidates:
            # 不拿自己补自己
            if cand is party:
                continue

            score, _ = _match_score(out, cand)

            if score >= min_score:
                scored.append(
                    (
                        score,
                        _completeness(cand),
                        len(_get_accounts(cand)),
                        cand,
                    )
                )

        if not scored:
            break

        scored.sort(
            key=lambda x: (
                -x[0],  # 匹配分数高优先
                -x[1],  # 字段完整度高优先
                -x[2],  # 账号多者优先
            )
        )

        filled_this_round = False

        for field in fields:
            if not _is_empty(out.get(field)):
                continue

            value = _choose_best_value(field, scored)

            if value is None:
                continue

            out[field] = value

            if field == "account":
                accounts = out.get("accounts") or []
                if value not in accounts:
                    accounts.append(value)
                out["accounts"] = accounts

            filled_this_round = True

        if not filled_this_round:
            break

    return out


# ============================================================
# seller / buyer 批量补齐
# ============================================================

def enrich_seller_buyer(
    seller: Optional[Party],
    buyer: Optional[Party],
    candidates: Iterable[Party],
    bridge: Optional[Party] = None,
    exclude: Iterable[Party] = (),
    fields: Iterable[str] = FILL_FIELDS,
    min_score: int = 60,
    max_rounds: int = 2,
    inplace: bool = False,
) -> Tuple[Optional[Party], Optional[Party]]:
    """
    补齐 seller 和 buyer。

    参数：
      seller:
        已经正确分隔出来的卖方结构体。

      buyer:
        已经正确分隔出来的买方结构体。

      candidates:
        用于补齐的其他候选结构体。
        建议不要包含 seller / buyer / bridge 本身。
        如果包含了，且是同一个Python对象，这里会按对象id排除。

      bridge:
        如果有过桥方，可以传入，默认会被排除。

      exclude:
        额外需要排除的结构体。

      inplace:
        是否直接修改原结构体。

    返回：
      (补齐后的seller, 补齐后的buyer)
    """
    if not seller or not buyer:
        return seller, buyer

    fields = tuple(fields)

    exclude_ids = {
        id(p)
        for p in (seller, buyer, bridge, *exclude)
        if p is not None
    }

    candidate_list = [
        c
        for c in candidates or []
        if c is not None and id(c) not in exclude_ids
    ]

    seller_out = enrich_party(
        seller,
        candidate_list,
        fields=fields,
        min_score=min_score,
        max_rounds=max_rounds,
        inplace=inplace,
    )

    buyer_out = enrich_party(
        buyer,
        candidate_list,
        fields=fields,
        min_score=min_score,
        max_rounds=max_rounds,
        inplace=inplace,
    )

    return seller_out, buyer_out
```

---

## 2. 使用示例

### 示例一：用外部客户信息补齐 `seller`、`buyer`

```python
seller = {
    "raw": "兴业银行",
    "org": "兴业银行",
    "person": None,
    "account": None,
    "accounts": [],
}

buyer = {
    "raw": "华创",
    "org": "华创",
    "person": None,
    "account": None,
    "accounts": [],
}

cust_info = [
    {
        "raw": "兴业银行 韩立 i9876543210",
        "org": "兴业银行",
        "person": "韩立",
        "account": "9876543210",
        "accounts": ["9876543210"],
    },
    {
        "raw": "华创杨文昊",
        "org": "华创",
        "person": "杨文昊",
        "account": None,
        "accounts": [],
    },
]

seller, buyer = enrich_seller_buyer(
    seller=seller,
    buyer=buyer,
    candidates=cust_info,
)

print(seller)
print(buyer)
```

结果大致是：

```python
{
    "raw": "兴业银行",
    "org": "兴业银行",
    "person": "韩立",
    "account": "9876543210",
    "accounts": ["9876543210"]
}
```

```python
{
    "raw": "华创",
    "org": "华创",
    "person": "杨文昊",
    "account": None,
    "accounts": []
}
```

---

### 示例二：目标只有账号，通过账号补机构名和人名

```python
seller = {
    "raw": "QT0123456789",
    "org": None,
    "person": None,
    "account": "0123456789",
    "accounts": ["0123456789"],
}

buyer = {
    "raw": "华创",
    "org": "华创",
    "person": None,
    "account": None,
    "accounts": [],
}

cust_info = [
    {
        "raw": "国泰海通 林宇昂",
        "org": "国泰海通",
        "person": "林宇昂",
        "account": "0123456789",
        "accounts": ["0123456789"],
    }
]

seller, buyer = enrich_seller_buyer(
    seller=seller,
    buyer=buyer,
    candidates=cust_info,
)

print(seller)
```

结果：

```python
{
    "raw": "QT0123456789",
    "org": "国泰海通",
    "person": "林宇昂",
    "account": "0123456789",
    "accounts": ["0123456789"]
}
```

---

### 示例三：目标只有人名，通过人名补账号

```python
buyer = {
    "raw": "杨文昊",
    "org": None,
    "person": "杨文昊",
    "account": None,
    "accounts": [],
}

cust_info = [
    {
        "raw": "华创 杨文昊",
        "org": "华创",
        "person": "杨文昊",
        "account": "1122334455",
        "accounts": ["1122334455"],
    }
]

buyer = enrich_party(buyer, cust_info)

print(buyer)
```

结果：

```python
{
    "raw": "杨文昊",
    "org": "华创",
    "person": "杨文昊",
    "account": "1122334455",
    "accounts": ["1122334455"]
}
```

---

## 3. 接入你现有 `parse_trade` 结果

如果你现在的解析结果类似：

```python
result = {
    "ok": True,
    "seller": {...},
    "bridge": {...},
    "buyer": {...},
}
```

同时你还有：

```python
cust_info = [...]
trade_parties = [...]
```

可以这样：

```python
if result.get("ok") and result.get("seller") and result.get("buyer"):

    candidates = []

    # 如果有外部客户信息
    candidates.extend(cust_info)

    # 如果有交易链里的其他候选结构体
    # 注意：如果里面已经有 seller / buyer / bridge 的同一个对象，
    # enrich_seller_buyer 会按对象id排除。
    candidates.extend(trade_parties)

    result["seller"], result["buyer"] = enrich_seller_buyer(
        seller=result["seller"],
        buyer=result["buyer"],
        candidates=candidates,
        bridge=result.get("bridge"),
        inplace=False,
    )
```

---

## 4. 如果你的所有结构体都在一个列表里

假设你有：

```python
parties = [
    seller_party,
    bridge_party,
    buyer_party,
    cust_info_1,
    cust_info_2,
    ...
]
```

并且 `seller_party`、`buyer_party`、`bridge_party` 就是列表中的对象引用，那么可以：

```python
seller = parties[0]
bridge = parties[1]
buyer = parties[2]

seller, buyer = enrich_seller_buyer(
    seller=seller,
    buyer=buyer,
    candidates=parties,
    bridge=bridge,
)
```

因为 `enrich_seller_buyer` 默认会排除：

```python
seller
buyer
bridge
```

这三个对象。

---

## 5. 如果你希望更激进地模糊匹配机构名

默认：

```python
min_score = 60
```

这表示：

- `account` 相同：可补；
- `person` 相同：可补；
- `org` 完全相同：可补；
- `org` 包含关系：可补；
- `raw` 完全相同：可补；
- 模糊机构名：默认大概率不参与。

如果你希望模糊机构名也能补，比如：

```text
国泰海通
国泰海通证券
```

或者更模糊的别名，可以调低：

```python
seller, buyer = enrich_seller_buyer(
    seller=seller,
    buyer=buyer,
    candidates=cust_info,
    min_score=40,
)
```

但我建议生产环境先用：

```python
min_score=60
```

因为太低容易把不同机构的人名、账号串在一起。

---

## 6. 几个重要注意事项

### 1. 这个逻辑是“只补缺失字段”，不是“覆盖已有字段”

比如目标已经是：

```python
{
    "org": "兴业银行",
    "person": "张三",
    "account": None,
}
```

那么只会补 `account`，不会覆盖 `person`。

如果你以后想做“高置信度覆盖低置信度”，需要额外维护每个字段的置信度。

---

### 2. 最好不要把 `buyer` 的信息用来补 `seller`

所以 `enrich_seller_buyer` 会排除 `seller`、`buyer`、`bridge`。

如果你的 `candidates` 里还有已知角色的结构体，建议也通过 `exclude` 传入：

```python
seller, buyer = enrich_seller_buyer(
    seller=seller,
    buyer=buyer,
    candidates=all_parties,
    bridge=bridge,
    exclude=[other_known_role_party],
)
```

---

### 3. 如果你的候选结构体不是同一个对象引用

`enrich_seller_buyer` 默认按对象 `id` 排除 `seller`、`buyer`、`bridge`。

如果你的 `candidates` 里面放的是 `seller`、`buyer` 的复制版，不是同一个对象，那么它不一定能自动排除。

这种情况下建议你手动准备 `candidates`：

```python
candidates = [
    p
    for p in all_parties
    if p is not seller and p is not buyer and p is not bridge
]
```

或者更稳一点，给每个结构体加一个稳定 `party_id` / `source` / `role` 字段。

---

### 4. 账号默认只认 10 位数字

代码里：

```python
def _clean_qq(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 else ""
```

也就是说：

```text
0123456789
```

会被保留。

但：

```text
13812345678
```

11位手机号会被丢弃。

如果你未来希望手机号也参与，可以把这里改成：

```python
return digits if len(digits) >= 5 else ""
```

不过当前场景是交易员 QQ，我建议先只认 10 位。

