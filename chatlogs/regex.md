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

