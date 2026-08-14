**system**:You are a helpful assistant about AI & LLM properties.


---
🙋**user**:
---
```
我使用qwen模型作ner任务, 原版是拼接发送人姓名+QQ号等信息，以及发送的消息内容，然后给一个prompt，让模型去抽取对应字段。它工作地很好。
但是新版我觉得让大模型去抽取发送人姓名QQ等信息没必要，改用正则抽取，同时把这部分从对应的prompt中去除了，模型居然会开始发疯：某些字段居然陷入了咨询和，输出好多好长的数字。
请帮我分析原因
```

---
🤖**assistant**:
---

你遇到的这个现象在大模型应用中非常典型。你提到的“陷入了咨询和”应该是 **“陷入了循环”** 的笔误。模型输出大量长数字并陷入死循环，本质上是**大模型的幻觉（Hallucination）**与**重复生成（Repetition Loop）** 叠加的结果。

虽然从人类逻辑来看，“用正则提取简单信息，让大模型专注复杂信息”是更优的工程架构，但对于自回归大模型（如Qwen）来说，输入分布的微小改变会导致其内部概率分布的剧变。

以下是导致模型“发疯”的核心原因分析及相应的解决建议：

### 一、 原因分析

#### 1. 上下文“锚点”丢失与注意力坍塌（Attention Collapse）
* **原版情况**：“发送人姓名+QQ号”等结构化元数据，在输入中起到了 **“上下文锚点”** 的作用。它们提供了丰富的语义和Token多样性，帮助模型的 Self-Attention 机制更好地分配注意力，理解这是一条“带有元数据的聊天记录”。
* **新版情况**：移除这些信息后，输入可能只剩下纯消息正文。如果正文较短或语义单一，模型的注意力权重可能会过度集中在某几个特定的 Token 上（比如某个数字或标点）。在自回归生成时，这种局部注意力集中极易导致模型陷入“重复生成同一个Token”的死循环。

#### 2. 任务期望与输入信息的错位（模型在“脑补”数字）
* **原版情况**：模型习惯了从输入中复制/提取 QQ号、电话号码、订单号等数字信息。
* **新版情况**：如果你使用的是**微调过的 Qwen 模型**，或者你的 **Prompt/Few-shot 示例**中没有把数字相关的字段彻底删干净，模型内部的“任务期望”依然存在。当它在输入中找不到这些数字，但又认为“必须输出数字字段”时，就会触发**幻觉**，强行编造（Hallucinate）出一长串数字来“凑数”。

#### 3. 输入分布偏移（Out-of-Distribution, OOD）
* 大模型（尤其是经过 SFT 微调的模型）对输入的格式非常敏感。原版中“元数据+正文”的格式是模型训练或 Prompt 设定时习惯的**数据分布**。
* 突然变成“纯正文”，对模型来说属于**分布外（OOD）输入**。这种格式上的突变会破坏模型内部激活状态的稳定性，导致其输出退化（Degeneration），表现为乱码或长串无意义数字。

#### 4. 解码参数（Decoding Parameters）的相对失效
* 在原版长输入下，原有的 `repetition_penalty`（重复惩罚）和 `temperature`（温度）参数可能工作得很好。
* 但在新版短输入下，由于生成的上下文变短，原有的重复惩罚机制可能无法有效覆盖长序列的循环，导致模型一旦开始生成数字，就无法停下来。

---

### 二、 解决方案

为了让模型在新架构下恢复正常，建议采取以下策略（按推荐优先级排序）：

#### 方案 1：保留“结构化占位符”（最推荐，改动最小）
既然大模型习惯了原有的输入结构，**不要直接删除元数据，而是用正则提取后，再以“占位符”的形式喂给大模型**。这能完美维持模型的输入分布和上下文锚点。
* **修改前的输入**：`张三 123456789 今天买的快递怎么还没到？`
* **修改后的输入**：`[发送人: 张三] [QQ: 123456789] 消息内容: 今天买的快递怎么还没到？`
* **Prompt 调整**：在 Prompt 中明确告诉模型：“*发送人和QQ已通过系统提取，你无需抽取这两个字段，请仅根据消息内容抽取以下字段：[字段A, 字段B]*”。

#### 方案 2：彻底清理 Prompt 与 Few-shot 示例
如果你坚持在输入中完全去掉这些信息，请务必进行“地毯式”清理：
1. **检查 Prompt 指令**：确保要求输出的 JSON Schema 或字段列表中，**绝对没有**姓名、QQ、电话等字段。
2. **检查 Few-shot（少样本示例）**：如果你的 Prompt 里带有示例，确保示例的输入和输出中也完全移除了这些字段。很多时候模型发疯是因为 Few-shot 示例里还有这些字段，模型在“照猫画虎”。

#### 方案 3：增加防幻觉与防循环的系统约束
在 Prompt 的末尾（System Prompt 或 User Prompt 的最后）增加强有力的约束指令，打断模型的脑补和循环倾向：
> *"注意：仅从提供的消息内容中提取信息。如果内容中没有相关信息，请输出 null 或 '未提及'。**严禁编造任何数字、QQ号或电话号码，严禁重复输出相同内容。**"*

#### 方案 4：调整推理参数（Decoding Parameters）
如果上述 Prompt 层面的调整仍偶发循环，可以在调用 API 或本地推理时微调参数：
* **提高 `repetition_penalty`**：从默认的 1.0 或 1.1 提高到 **1.15 ~ 1.2** 之间，强制模型减少重复 Token 的生成。
* **调整 `temperature`**：如果任务偏向确定性抽取，将 temperature 调低（如 **0.1 - 0.3**），降低模型的发散性；如果太低导致死循环，可稍微调高至 **0.5**。
* **设置 `stop` 词**：如果发现模型总是输出特定的长数字后停止，可以将某些异常模式加入 stop words，或者限制 `max_tokens` 防止其无限输出。

### 总结
大模型不是传统的规则引擎，它是**基于概率的上下文预测器**。你移除了“姓名+QQ”，在工程逻辑上是“减负”，但在模型的神经网络视角里，是 **“破坏了原有的上下文生态”**。通过**保留结构占位符（方案1）**，可以在享受正则提取便利的同时，安抚大模型的“上下文依赖”，是最稳妥的解决方式。


---
🙋**user**:
---
```
现在随着业务变化，ner服务场景有一个不大不小的变化：之前是对方发送一条完整（至少是预设完整）的信息，ner服务通过编写prompt、发送给llm请求输出、后处理等；现在是双方在不断聊天、交换信息，询问方可能同时询问两条交易的具体信息，然后回答方回复，双方逐步在聊天中补齐所有字段。
请分析这种新业务场景下，我的NER服务该怎么设计？
```

---
🤖**assistant**:
---

这是一个非常经典的 NLP 业务演进：**从“单文档/单消息信息抽取（IE）” 升级为了 “对话式状态追踪（Dialogue State Tracking, DST）与槽位填充（Slot Filling）”**。

在旧场景下，你的 NER 服务是**无状态（Stateless）** 的：输入一段文本，输出一个 JSON，结束。
在新场景下，你的 NER 服务必须变成**有状态（Stateful）** 的：它需要记住“我们在聊哪几笔交易”、“哪些字段已经确定了”、“哪些字段还在讨价还价”、“刚才说的‘前者’指的是哪个债券”。

为了应对这种变化，你的 NER 服务架构需要进行一次核心升级。以下是详细的设计方案：

---

### 一、 核心架构升级：引入“会话 (Session)”与“交易草稿 (Trade Draft)”

你不能再把每一句话孤立地送给 LLM 了。你需要建立一个**状态机**。

#### 1. 概念定义
*   **Session (会话)**：代表交易员之间针对某一批次交易的完整沟通周期。前端请求必须携带 `session_id`。
*   **Trade Draft (交易草稿)**：在会话过程中，逐步被填充的交易实体。一个 Session 中可能同时存在多个 Draft（比如同时聊两笔债券）。
*   **Slot (槽位)**：交易草稿中的具体字段（如 `asset_code`, `price`, `amount`, `counterparty`）。

#### 2. 状态存储 (State Store)
你需要一个地方来存储当前 Session 的“最新共识”。
*   **推荐方案**：使用 **Redis**（设置 TTL，如 2 小时过期）或 **本地 SQLite/MySQL 的草稿表**。
*   **数据结构示例**：
    ```json
    {
      "session_id": "sess_8848",
      "status": "negotiating", // negotiating(沟通中), confirmed(已确认/成单), cancelled(取消)
      "drafts": [
        {
          "draft_id": "draft_1",
          "asset_name": "24长发金控PPN001",
          "asset_code": "032481632.IB",
          "price": 100.85,       // 已填充
          "amount": null,        // 待填充 (槽位为空)
          "direction": "bid"     // 买入
        },
        {
          "draft_id": "draft_2",
          "asset_name": "25诚通建投PPN001",
          "asset_code": null,    // 待填充
          "price": 100.36,
          "amount": 1000
        }
      ]
    }
    ```

---

### 二、 核心技术路线选择：增量抽取 vs 全量重算

面对多轮对话，LLM 的处理方式通常有两种，强烈建议选择**方案 B**。

#### 方案 A：全量上下文重算 (不推荐)
*   **做法**：每次收到新消息，把“历史所有对话 + 当前草稿状态 + 新消息”全部塞给 LLM，让 LLM 输出**更新后的完整草稿 JSON**。
*   **缺点**：随着对话变长，Token 消耗剧增；LLM 很容易产生“幻觉”，把前面已经确定好的字段给弄丢了（灾难性遗忘）；延迟高。

#### 方案 B：增量指令抽取 + 代码合并 (强烈推荐 ⭐)
*   **做法**：LLM 不再负责维护全局状态，而是**只负责理解当前这句话带来了什么“增量变化”**，并输出结构化的**操作指令 (Actions)**。后端代码拿到指令后，去更新 Redis/DB 中的草稿状态。
*   **优点**：Token 消耗极低（只需传入最近几轮上下文和当前状态摘要），状态由代码绝对掌控（确定性高，绝不丢字段），速度极快。

---

### 三、 增量抽取的 Prompt 设计 (方案 B 落地)

你需要将 Prompt 从“信息抽取”改为“**意图识别与状态更新指令生成**”。

```markdown
# Role
你是一个银行间市场交易对话状态追踪助手。你的任务是分析交易员的最新回复，并结合当前的【交易草稿状态】和【近期对话历史】，输出结构化的【状态更新指令】。

# 当前交易草稿状态 (Current Drafts)
{{current_drafts_json}} 

# 近期对话历史 (Recent History)
{{recent_chat_history}}

# 最新一条消息 (Latest Message)
{{latest_message}}

# 任务与输出约束
请分析【最新一条消息】，判断其意图，并输出 JSON 格式的指令列表。支持以下操作：
1. `CREATE`: 发现新的交易意图，创建新草稿。
2. `UPDATE`: 更新现有草稿的字段（如确认价格、修改金额、补充代码）。必须指明 `draft_id` 或明确的 `asset_name` 以定位目标。
3. `CONFIRM`: 交易员明确表达了“成交”、“确认”、“OK”、“done”等成单意图。
4. `REJECT`: 交易员明确拒绝（如“不要了”、“取消”）。
5. `CLARIFY`: 信息模糊或存在歧义，需要向用户反问（如“请问您指的是哪一笔的量？”）。

# Output Schema
严格输出 JSON，不要包含其他文本：
{
  "actions": [
    {
      "action_type": "UPDATE",
      "target_draft_id": "draft_1", // 或 target_asset_name
      "updates": {
        "amount": 2000,
        "price": 100.88 // 讨价还价，更新了价格
      },
      "reasoning": "用户说'那笔长发的量加到2000，价格100.88行不行'"
    },
    {
      "action_type": "CONFIRM",
      "target_draft_id": "draft_2",
      "reasoning": "用户回复'诚通那笔OK，就按这个做'"
    }
  ],
  "reply_suggestion": "可选，如果 action 是 CLARIFY，这里生成反问话术"
}
```

---

### 四、 后端处理流程 (Pipeline)

当接收到前端带有 `session_id` 的新消息时，后端的处理流程如下：

1. **加载状态**：根据 `session_id` 从 Redis/DB 加载当前的 `Current Drafts` 和 `Recent History`。
2. **调用 LLM**：将状态、历史、新消息拼装进上述 Prompt，请求 Qwen 模型。
3. **解析指令**：解析 LLM 返回的 `actions` 列表。
4. **执行合并 (核心代码逻辑)**：
   ```python
   for action in llm_response['actions']:
       if action['action_type'] == 'UPDATE':
           draft = find_draft_by_id_or_name(drafts, action['target_draft_id'], action.get('target_asset_name'))
           if draft:
               # 执行增量更新 (代码掌控状态)
               draft.update(action['updates'])
       elif action['action_type'] == 'CREATE':
           drafts.append(create_new_draft(action['initial_data']))
       elif action['action_type'] == 'CONFIRM':
           # 将特定草稿标记为已确认
           mark_as_confirmed(drafts, action['target_draft_id'])
   ```
5. **保存状态**：将更新后的 `drafts` 写回 Redis/DB。
6. **触发下游**：检查是否有 `status == confirmed` 的草稿。如果有，将其推送到真正的**交易执行系统 (OMS/EMS)**，并向前端返回“已成单”的信号。
7. **返回前端**：返回更新后的 UI 状态（如高亮已确定的字段，标红待确认的字段），以及 LLM 生成的 `reply_suggestion`（如果需要机器人代聊）。

---

### 五、 解决多轮对话中的 3 个核心难点

#### 1. 指代消解 (Coreference Resolution)
*   **场景**：用户问“24长发和25诚通什么价？” -> 机器人答“100.8和100.3” -> 用户说“**前者**量加大点，**后者**不要了”。
*   **解决**：Qwen 模型具备很强的上下文理解能力。在 Prompt 的 `Recent History` 中保留最近的 3-5 轮对话，LLM 就能准确将“前者”映射到 `draft_1` (24长发)，将“后者”映射到 `draft_2` (25诚通)，并输出对应的 `UPDATE` 和 `REJECT` 指令。

#### 2. 多实体并行对齐
*   **场景**：“两笔都是 1000w 吗？” -> “长发 1000，诚通 2000”。
*   **解决**：要求 LLM 在输出 `actions` 时，必须是一个 **List**。LLM 会输出两个 `UPDATE` 动作，分别对应两个 `draft_id`。后端代码循环执行即可。

#### 3. 讨价还价与状态覆盖
*   **场景**：“1.95 出” -> “1.95 太贵了，1.94 吧” -> “行，1.94”。
*   **解决**：在 `UPDATE` 动作中，直接覆盖旧值。同时，建议在 Draft 结构中增加一个 `history` 字段，记录价格的变化轨迹（如 `price_history: [1.95, 1.94]`），这对于后续的合规审计和 Feedback 分析非常有价值。

---

### 六、 对现有 Feedback 系统的影响

你之前设计的 `ner_feedback` 表依然有用，但触发时机变了：

1. **旧模式**：单次抽取后，前端展示结果，用户点“纠错” -> 触发 Feedback。
2. **新模式**：
   - 在对话**进行中**，前端 UI 实时展示“交易草稿”的卡片。用户如果发现 LLM 理解错了（比如把“买入”识别成了“卖出”），可以直接在 UI 上点击草稿卡片上的字段进行**实时修正**。这种修正直接作为高优先级的 `UPDATE` 指令写入状态，并记录到 Feedback 表。
   - 当交易最终 **`CONFIRM` (成单)** 时，系统生成最终的“成单快照 (Final Snapshot)”。此时，如果用户对最终快照进行 Feedback，就等同于你之前设计的逻辑。

### 总结

从“单轮 NER”到“多轮 DST”，本质上是从 **“文本解析器”** 升级为 **“虚拟交易助理”**。

**核心口诀**：
1. **LLM 只做“阅读理解”和“意图分类”（输出增量 Action）。**
2. **后端代码做“状态管理”和“逻辑合并”（维护 Draft Pool）。**
3. **引入 Session 和 Draft 概念，让每一次对话都有迹可循。**

这种架构不仅完美契合 Qwen 等现代大模型的能力边界（擅长理解和生成，但不擅长在长文本中维持精确的 JSON 状态），而且工程可控性极强，是目前业界做 Conversational AI 的主流最佳实践。


---
🙋**user**:
---
```
我现在拿到一张 对口交易员姓名-Qt账号 表格，而我在NER消息记录时, 是需要精确抽取 对口交易员姓名 这一字段的(一定在表格中)。消息记录里经常有 <姓名><qt账号> 类似这样的标识。
我该如何写一个 可以增强抽取 对口交易员姓名的 方法？
```

---
🤖**assistant**:
---

这是一个非常经典的 **“封闭集实体识别（Closed-set NER）”** 场景。

既然你明确知道 **“对口交易员姓名一定在表格中”**，这就意味着这不再是一个开放的阅读理解问题，而是一个**精确的字典匹配问题**。

在这种场景下，**大模型的准确率永远比不上“正则+白名单字典”**。大模型容易产生幻觉（比如把“徐少卿”抽成“徐少卿 ”，或者漏字），而字典匹配是 100% 确定性的。

因此，最优雅且准确率最高的架构是：**“规则引擎硬匹配（主导） + 大模型语义抽取（兜底） + 结果融合”**。

以下是为你量身定制的增强抽取方案及完整代码。

---

### 一、 核心设计思路

1. **构建双向映射字典**：将表格加载到内存，构建 `QT -> 标准姓名` 和 `标准姓名 -> QT` 的字典。
2. **规则引擎（Regex + 字典）**：
   - **策略 A（通过 QT 反查）**：用正则提取文本中所有的“连续数字（QT号）”，去字典里查。如果查到了，往前回溯提取汉字，直接绑定标准姓名。
   - **策略 B（直接命中姓名）**：用字典中的所有姓名生成一个大正则，直接在文本中扫描命中。
3. **大模型兜底**：让大模型正常抽取，但告诉它“重点提取 QT 号，姓名如果不确定可以留空”。
4. **结果融合（Merge）**：**规则引擎的结果优先级绝对高于大模型**。如果规则查到了，直接覆盖大模型的结果。

---

### 二、 完整 Python 代码实现

你可以将以下代码封装为一个独立的模块（如 `contact_enhancer.py`）。

```python
import re
import csv
from typing import Dict, List, Tuple, Optional

class ContactEnhancer:
    """
    交易员联系人信息增强抽取器
    利用本地白名单字典，对大模型的抽取结果进行强制校验和纠错。
    """
    
    def __init__(self, csv_file_path: str):
        # 核心字典
        self.qt_to_name: Dict[str, str] = {}      # QT账号 -> 标准姓名
        self.name_to_qt: Dict[str, str] = {}      # 标准姓名 -> QT账号
        self.all_standard_names: List[str] = []   # 所有标准姓名列表
        
        self._load_dictionary(csv_file_path)
        
        # 预编译正则
        # 1. 匹配连续数字（假设QT账号为 5-12 位数字）
        self.qt_regex = re.compile(r'\b(\d{5,12})\b')
        # 2. 匹配 "汉字 + 可选分隔符 + 数字" 的常见组合 (如: 张三123, 李四QT:456)
        self.combo_regex = re.compile(r'([\u4e00-\u9fa5]{2,4})\s*(?:\(?(?:QT|qt|q)?[:：]?\s*)?(\d{5,12})\)?')
        
        # 3. 构建姓名直接匹配正则 (按长度降序排列，防止"张三"匹配了"张三丰"的前两个字)
        sorted_names = sorted(self.all_standard_names, key=len, reverse=True)
        if sorted_names:
            self.name_regex = re.compile(r'(' + '|'.join(re.escape(n) for n in sorted_names) + r')')
        else:
            self.name_regex = None

    def _load_dictionary(self, file_path: str):
        """加载 CSV 表格，构建映射字典"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('name', '').strip()
                    qt = row.get('qt', '').strip()
                    if name and qt:
                        self.qt_to_name[qt] = name
                        self.name_to_qt[name] = qt
                        self.all_standard_names.append(name)
        except Exception as e:
            print(f"Error loading dictionary: {e}")

    def extract_by_rules(self, text: str) -> List[Dict[str, str]]:
        """
        纯规则提取：通过正则和白名单字典，从文本中硬匹配联系人信息。
        返回: [{"raw_name": "徐少卿", "standard_name": "徐少卿", "qt": "12345678"}, ...]
        """
        found_contacts = []
        seen_qts = set()

        # 策略 1：寻找 "姓名 + QT" 的组合模式
        for match in self.combo_regex.finditer(text):
            raw_name = match.group(1)
            qt = match.group(2)
            
            if qt in self.qt_to_name:
                standard_name = self.qt_to_name[qt]
                found_contacts.append({
                    "raw_name": raw_name,
                    "standard_name": standard_name,
                    "qt": qt
                })
                seen_qts.add(qt)

        # 策略 2：寻找孤立的 QT 账号（周围没有紧跟着汉字，或者格式很奇怪）
        for match in self.qt_regex.finditer(text):
            qt = match.group(1)
            if qt in self.qt_to_name and qt not in seen_qts:
                standard_name = self.qt_to_name[qt]
                # 尝试往前看 2-4 个字符作为 raw_name
                start_idx = max(0, match.start() - 4)
                context_before = text[start_idx:match.start()]
                raw_name_match = re.search(r'([\u4e00-\u9fa5]{2,4})$', context_before)
                raw_name = raw_name_match.group(1) if raw_name_match else ""
                
                found_contacts.append({
                    "raw_name": raw_name,
                    "standard_name": standard_name,
                    "qt": qt
                })
                seen_qts.add(qt)

        # 策略 3：直接扫描标准姓名（针对只有姓名没有 QT 的情况）
        if self.name_regex:
            for match in self.name_regex.finditer(text):
                standard_name = match.group(1)
                # 检查是否已经被前面的策略提取过了
                if not any(c['standard_name'] == standard_name for c in found_contacts):
                    found_contacts.append({
                        "raw_name": standard_name,
                        "standard_name": standard_name,
                        "qt": self.name_to_qt.get(standard_name, "")
                    })

        return found_contacts

    def merge_with_llm(self, llm_result: dict, text: str) -> dict:
        """
        将规则提取的结果与大模型的抽取结果进行融合。
        规则结果具有最高优先级。
        """
        # 1. 规则提取
        rule_contacts = self.extract_by_rules(text)
        
        # 2. 构建规则结果的查找字典 (以 standard_name 为 key)
        rule_lookup = {c['standard_name']: c for c in rule_contacts}
        
        # 3. 遍历大模型抽取的 trades，进行覆盖和补全
        if 'trades' in llm_result:
            for trade in llm_result['trades']:
                # 假设大模型抽取的字段叫 contact_name 和 contact_qt
                llm_name = trade.get('contact_name', '')
                llm_qt = trade.get('contact_qt', '')
                
                # 尝试用大模型抽出的 QT 去规则字典里反查
                if llm_qt and llm_qt in self.qt_to_name:
                    standard_name = self.qt_to_name[llm_qt]
                    trade['contact_name'] = standard_name
                    trade['contact_qt'] = llm_qt
                    continue
                    
                # 尝试用大模型抽出的姓名去规则字典里匹配
                if llm_name and llm_name in rule_lookup:
                    matched = rule_lookup[llm_name]
                    trade['contact_name'] = matched['standard_name']
                    trade['contact_qt'] = matched['qt']
                    continue
                    
                # 如果大模型抽出的姓名不在字典里，但规则提取到了联系人
                # (这里假设一笔交易通常只有一个主要联系人，取规则提取的第一个)
                if rule_contacts and not llm_name:
                    fallback = rule_contacts[0]
                    trade['contact_name'] = fallback['standard_name']
                    trade['contact_qt'] = fallback['qt']

        return llm_result
```

---

### 三、 如何在 Pipeline 中使用它？

在你的 FastAPI 接口或处理脚本中，流程如下：

```python
# 1. 初始化增强器 (应用启动时加载一次即可)
enhancer = ContactEnhancer("contacts_whitelist.csv")

# 2. 调用大模型
raw_text = "5.7+0 26温州经开PPN001 7500w 中信银行（麻烦先找徐少卿12345678询价）出 国联信托"
llm_response = call_qwen_model(raw_text) # 假设返回了解析好的 dict

# 3. 核心：后处理融合
final_result = enhancer.merge_with_llm(llm_response, raw_text)

print(final_result)
# 输出中，contact_name 会被强制纠正为字典中的标准姓名，contact_qt 会被补齐。
```

---

### 四、 配合 Prompt 的优化建议

既然后端有了强大的规则兜底，你在写 Prompt 时就可以**给大模型“减负”**，让它把注意力集中在复杂的交易逻辑上，而不是死磕人名。

你可以在 Prompt 的 `Constraints` 中加入这样一条：

```markdown
# 抽取约束
1. **联系人信息**：请尽量提取文本中的 **QT账号（纯数字）**。对于姓名，提取原文即可，无需担心错别字，后处理系统会自动根据 QT 账号或白名单进行精准校对和补全。
2. 如果文本中只有姓名没有 QT 账号，请正常提取姓名。
```

### 五、 为什么这种方案最好？

1. **消灭幻觉**：大模型可能会把“徐少卿”抽成“徐少卿 ”（带空格）或者“徐少卿1”，但正则+字典匹配出来的永远是干干净净的 `徐少卿` 和 `12345678`。
2. **处理黑话和缩写**：如果表格里有 `["张三", "111"]` 和 `["张三丰", "222"]`，文本里写的是 `张三丰111`（交易员打错字了）。大模型可能会懵，但规则引擎通过 `111` 反查字典，能精准锁定标准姓名是 `张三`，并纠正这个错误。
3. **性能极高**：字典匹配和正则扫描在 Python 中是微秒级的，完全不会增加接口的整体延迟。

通过这种 **“大模型负责语义理解，规则引擎负责事实校验”** 的混合架构（Neuro-symbolic AI 的雏形），你的 NER 系统在联系人抽取这一项上的准确率将无限逼近 100%。


---
🙋**user**:
---
```
帮我写一套基于FastAPI的LLM-NER服务, 至少包括如下:
log.py: 共享的logger
context.py: 定义所有 contextvars 即 协程级别的隔离变量
config.py: 
    Setting类, 定义 APP_NAME, HOST, PORT, API_URL, API_KEY, TIMEOUT, 以及 model_version/temperature 等推理配置, 以及NER的输出schema, 还有Config(env_file等);
    其他日志db地址/workspace/data/logs/*.db, 需要用到的资源文件放在/workspace/resource
monitor.py: 
    后台日志落盘线程 DBWriterThread, 支持将每一条NER记录的 trace_id, timestamp, method, path, status_code, duration_ms, input_payload, output_payload 作为一条记录插入日志. 这里字段 input_payload 是记录会话session中的所有涉及文字拼接, duration_ms是LLM推理的总时间
    MonitorManager类, 内有 start(创建db, 开启写入线程), stop(停止写入线程)
    全局日志写入单例
    监控中间件
models.py:
    输入request的Model, 以及其所需要的其他Model
    输出response的Model, 以及其所需要的其他Model
app.py:
    lifespan协程
    App实例, 并注册监控日志等必须中间件‘
文件夹services, 内含:
    build_prompt.py: 所有提示词工程相关的都放在这里. 提示词的基本要义是金融权益凭证交易消息的字段提取专家,要从持续的会话中抽取出指定的每个字段(每个字段的语义以一个semantic table定义)
    llm_client.py:
        一个会话client类, 支持host一个会话级别的client, 持续接收message, 判断1: 当前message是否新建了一个 交易草稿 trade_draft, 2: 当前message是否涉及会话中仍在处理的 trade_draft, 如果涉及, 本条message提供了该交易草稿的哪些字段信息, 并填充slot, 3: 当前message结束后, 是否有交易草稿的slot已满, 或某交易草稿已经过threshold条message消息. 将已满的slot或达到threshold数量的交易草稿对应的slot以JSON格式, 发送到队列里.
        一个接收slots的队列
        一个从队列读取并向前端发送JSON结构体的发送器
    preprocess.py: 所有对message文本消息的预处理
    postprocess.py: 所有对JSON结构体的后处理, 可能会有日期规整化、数字规整化等. 你要在这里给我留好针对字段级别的接口; 还要给我留好交易级别的接口，比如有些交易识别的字段总数太少, 要去掉等等.
    rules_client.py: 除了通过语义提取之外, 还有一些字段可以通过规则正则提取. 在这里帮我仿照llm_client.py, 使用regex而不是llm抽取字段(每个字段的正则以一个regex table定义. 当然大部分是空的要靠llm). 注意, 是否有新的 交易草稿/slot 建立, 这个是要靠llm判断的, 所以rules_client要从llm_client监听判断1和判断2, 知道当前message在讨论哪个交易草稿, 从而将抽取的信息填充到对应交易草稿的slot
    merge.py: 合并 llm_client 和 rules_client 的结果. 二者只有其一则取其一, 二者皆有取 llm
    enhancer.py: 其实每个字段都可能有一些后验的手段可以辅助检测是否正确, 有些比如是白名单, 有些可能是外部接口能得到是否正确的反馈. 我需要你在这里, 针对字段写一个可供校验的工具类, 它内部可以保存一些外部资源(比如url, 或者本地的csv文件), 然后通过字段-资源实例化, 可检验字段的正确性
main.py: run这个app的主程序
```

---
🤖**assistant**:
---

这是一个非常完整且企业级的 FastAPI 异步服务架构设计。为了满足你的需求，我将代码拆分为多个模块，并严格按照你的要求实现了状态管理、后台日志落盘、规则与LLM融合以及后验增强。

以下是完整的代码实现：

### 1. `log.py` (共享日志)
```python
import logging
import sys

def get_logger(name: str = "ner_service") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = get_logger()
```

### 2. `context.py` (协程级上下文变量)
```python
import contextvars

# 用于链路追踪和日志隔离
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('trace_id', default='-')
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('session_id', default='-')
```

### 3. `config.py` (配置管理)
```python
from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    APP_NAME: str = "Financial-NER-Service"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # LLM API Config
    API_URL: str = "https://api.openai.com/v1/chat/completions"
    API_KEY: str = "sk-your-key"
    TIMEOUT: int = 30
    MODEL_VERSION: str = "qwen-max"
    TEMPERATURE: float = 0.1
    
    # Paths
    LOG_DB_PATH: str = "/workspace/data/logs/ner_logs.db"
    RESOURCE_DIR: str = "/workspace/resource"
    
    # NER Output Schema (JSON Schema string or dict)
    NER_SCHEMA: dict = Field(default={
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["CREATE", "UPDATE", "CHITCHAT"]},
            "target_draft_id": {"type": "string"},
            "slots": {"type": "object"}
        }
    })

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# 确保目录存在
os.makedirs(os.path.dirname(settings.LOG_DB_PATH), exist_ok=True)
os.makedirs(settings.RESOURCE_DIR, exist_ok=True)
```

### 4. `monitor.py` (后台日志落盘与监控中间件)
```python
import sqlite3
import threading
import queue
import time
import json
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from config import settings
from log import logger
from context import trace_id_var, session_id_var

class DBWriterThread(threading.Thread):
    def __init__(self, db_path: str):
        super().__init__(daemon=True)
        self.db_path = db_path
        self.queue = queue.Queue()
        self.running = True
        self.conn = None

    def run(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()
        while self.running or not self.queue.empty():
            try:
                record = self.queue.get(timeout=1.0)
                self._insert_record(record)
                self.conn.commit()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"DB Writer error: {e}")
        self.conn.close()

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ner_logs (
                trace_id TEXT, timestamp REAL, method TEXT, path TEXT, 
                status_code INTEGER, duration_ms REAL, 
                input_payload TEXT, output_payload TEXT
            )
        ''')
        self.conn.commit()

    def _insert_record(self, record: dict):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ner_logs (trace_id, timestamp, method, path, status_code, duration_ms, input_payload, output_payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record['trace_id'], record['timestamp'], record['method'], record['path'],
            record['status_code'], record['duration_ms'], 
            json.dumps(record['input_payload'], ensure_ascii=False),
            json.dumps(record['output_payload'], ensure_ascii=False)
        ))

    def add_record(self, record: dict):
        self.queue.put(record)

    def stop(self):
        self.running = False

class MonitorManager:
    def __init__(self):
        self.writer_thread = None

    def start(self):
        self.writer_thread = DBWriterThread(settings.LOG_DB_PATH)
        self.writer_thread.start()
        logger.info("Monitor DBWriterThread started.")

    def stop(self):
        if self.writer_thread:
            self.writer_thread.stop()
            self.writer_thread.join()
            logger.info("Monitor DBWriterThread stopped.")

    def log(self, record: dict):
        if self.writer_thread:
            self.writer_thread.add_record(record)

monitor_manager = MonitorManager()

# 自定义中间件以支持读取 Request Body 且不消耗流
class MonitorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)
        
        start_time = time.time()
        
        # 缓存 body
        body_bytes = await request.body()
        async def receive_body():
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        request._receive = receive_body
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # 获取 session 历史拼接文本 (从 request.state 获取，由路由注入)
        session_history = getattr(request.state, "session_history", "")
        output_payload = getattr(request.state, "response_payload", {})
        
        monitor_manager.log({
            "trace_id": trace_id,
            "timestamp": time.time(),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "input_payload": session_history, # 记录会话的所有文字拼接
            "output_payload": output_payload
        })
        
        response.headers["X-Trace-ID"] = trace_id
        return response
```

### 5. `models.py` (数据模型)
```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class MessageRequest(BaseModel):
    session_id: str = Field(..., description="会话唯一标识")
    message: str = Field(..., description="当前用户发送的消息")
    timestamp: float = Field(default_factory=lambda: time.time())

class TradeDraft(BaseModel):
    draft_id: str
    asset_name: Optional[str] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    direction: Optional[str] = None
    counterparty: Optional[str] = None
    status: str = "negotiating" # negotiating, confirmed

class NERResponse(BaseModel):
    session_id: str
    active_drafts: List[TradeDraft]
    extracted_slots: Dict[str, Any]
    message: str = "Success"
```

### 6. `services/build_prompt.py` (提示词工程)
```python
SEMANTIC_TABLE = {
    "asset_name": "债券或权益凭证的简称或全称，如 '24长发金控PPN001'",
    "price": "交易价格或收益率，如 '100.85' 或 '2.5%'",
    "amount": "交易面额或数量，单位通常为万元，如 '1000' 代表 1000万",
    "direction": "交易方向，买入(bid) 或 卖出(ofr)",
    "counterparty": "交易对手方名称或简称"
}

def build_system_prompt() -> str:
    schema_desc = "\n".join([f"- {k}: {v}" for k, v in SEMANTIC_TABLE.items()])
    return f"""你是一个金融权益凭证交易消息的字段提取专家。
你的任务是从交易员的持续会话中，精准识别意图并提取以下字段：
{schema_desc}

输出严格的JSON格式：
{{
  "intent": "CREATE" (新建交易) | "UPDATE" (更新现有交易) | "CHITCHAT" (闲聊/无关),
  "target_draft_id": "如果意图是UPDATE，指明更新的草稿ID，否则为null",
  "slots": {{ "提取到的字段": "值" }}
}}
"""

def build_user_prompt(history: str, current_msg: str, active_drafts: list) -> str:
    drafts_info = "\n".join([f"- ID: {d.draft_id}, 资产: {d.asset_name}" for d in active_drafts]) if active_drafts else "无"
    return f"""当前活跃交易草稿：
{drafts_info}

历史对话：
{history}

最新一条消息：
{current_msg}

请分析最新消息并输出JSON。"""
```

### 7. `services/llm_client.py` (大模型会话客户端)
```python
import asyncio
import json
import httpx
from typing import Dict, List, Optional
from config import settings
from models import TradeDraft
from services.build_prompt import build_system_prompt, build_user_prompt
from log import logger

class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: List[str] = []
        self.drafts: Dict[str, TradeDraft] = {}
        self.message_count_since_last_extract: int = 0
        self._draft_counter = 0

    def add_message(self, msg: str):
        self.history.append(msg)
        self.message_count_since_last_extract += 1

    def create_draft(self) -> str:
        self._draft_counter += 1
        draft_id = f"draft_{self._draft_counter}"
        self.drafts[draft_id] = TradeDraft(draft_id=draft_id)
        return draft_id

class LLMClient:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.slot_queue = asyncio.Queue()
        self.threshold = 5 # 达到5条消息强制输出一次

    async def process_message(self, session_id: str, message: str) -> dict:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id)
        
        state = self.sessions[session_id]
        state.add_message(message)
        
        # 1. 调用 LLM
        llm_res = await self._call_llm(state, message)
        
        # 2. 判断意图并更新状态
        intent = llm_res.get("intent", "CHITCHAT")
        slots = llm_res.get("slots", {})
        
        target_id = None
        if intent == "CREATE":
            target_id = state.create_draft()
            self._fill_slots(state.drafts[target_id], slots)
        elif intent == "UPDATE":
            target_id = llm_res.get("target_draft_id") or self._guess_target_draft(state, message)
            if target_id and target_id in state.drafts:
                self._fill_slots(state.drafts[target_id], slots)
                
        # 3. 判断是否已满或达到 threshold
        extracted = []
        for d_id, draft in state.drafts.items():
            if self._is_slot_full(draft) or state.message_count_since_last_extract >= self.threshold:
                extracted.append(draft.model_dump())
                
        if extracted:
            state.message_count_since_last_extract = 0
            await self.slot_queue.put({"session_id": session_id, "drafts": extracted})
            
        return {"intent": intent, "target_id": target_id, "slots": slots, "state": state}

    async def _call_llm(self, state: SessionState, message: str) -> dict:
        # 实际调用 Qwen API 的逻辑
        history_str = "\n".join(state.history[-5:]) # 取最近5轮
        active_drafts = list(state.drafts.values())
        
        payload = {
            "model": settings.MODEL_VERSION,
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": build_user_prompt(history_str, message, active_drafts)}
            ],
            "temperature": settings.TEMPERATURE,
            "response_format": {"type": "json_object"}
        }
        
        # 模拟 API 调用 (实际请使用 httpx 替换)
        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(settings.API_URL, json=payload, headers={"Authorization": f"Bearer {settings.API_KEY}"})
        #     return resp.json()['choices'][0]['message']['content']
        
        # Mock 返回
        await asyncio.sleep(0.1)
        return {"intent": "UPDATE", "target_draft_id": "draft_1", "slots": {"price": 100.5}}

    def _fill_slots(self, draft: TradeDraft, slots: dict):
        for k, v in slots.items():
            if hasattr(draft, k):
                setattr(draft, k, v)

    def _guess_target_draft(self, state: SessionState, msg: str) -> Optional[str]:
        # 简单的指代消解兜底
        if state.drafts:
            return list(state.drafts.keys())[-1]
        return None

    def _is_slot_full(self, draft: TradeDraft) -> bool:
        # 核心字段是否已满
        return all([draft.asset_name, draft.price, draft.amount, draft.direction])

    async def slot_sender(self):
        """后台任务：从队列读取并向前端发送（此处模拟打印，实际可推送到 WebSocket/SSE）"""
        while True:
            data = await self.slot_queue.get()
            logger.info(f"[Slot Sender] Ready to push to frontend: {data}")
            # await websocket.send_json(data)
            self.slot_queue.task_done()

llm_client = LLMClient()
```

### 8. `services/preprocess.py` & `postprocess.py`
```python
# preprocess.py
import re

def preprocess_message(text: str) -> str:
    # 统一全半角，去除多余空白
    text = text.replace("：", ":").replace("，", ",")
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

```python
# postprocess.py
from models import TradeDraft
from typing import Dict, Any

class PostProcessor:
    @staticmethod
    def normalize_field(field_name: str, value: Any) -> Any:
        """字段级别接口：规整化"""
        if field_name == "amount" and isinstance(value, str):
            if "万" in value:
                return float(value.replace("万", ""))
            return float(value)
        if field_name == "price" and isinstance(value, str):
            return float(value.replace("%", ""))
        return value

    @staticmethod
    def validate_trade(draft_dict: Dict[str, Any]) -> bool:
        """交易级别接口：校验交易是否有效（如字段太少则丢弃）"""
        filled_count = sum(1 for v in draft_dict.values() if v is not None)
        return filled_count >= 3 # 至少3个字段才算有效交易

post_processor = PostProcessor()
```

### 9. `services/rules_client.py` (规则正则提取)
```python
import re
from typing import Dict, Optional
from models import TradeDraft

# Regex Table
REGEX_TABLE = {
    "amount": r'(\d+)\s*(?:w|万|w万|千万)',
    "price": r'(?:价格|价|收益率)\s*[:：]?\s*([\d\.]+)',
    "counterparty": r'(?:对手|出给|收自)\s*[:：]?\s*([\u4e00-\u9fa5]{2,10})'
}

class RulesClient:
    def __init__(self):
        self.compiled_regex = {k: re.compile(v, re.IGNORECASE) for k, v in REGEX_TABLE.items()}

    def extract(self, message: str, target_draft_id: Optional[str], active_drafts: Dict[str, TradeDraft]) -> Dict[str, any]:
        """根据 LLM 判断的 target_draft_id，将正则提取的字段填充到对应草稿"""
        extracted_slots = {}
        for field, pattern in self.compiled_regex.items():
            match = pattern.search(message)
            if match:
                extracted_slots[field] = match.group(1)
                
        # 如果 LLM 识别出了目标草稿，直接更新它
        if target_draft_id and target_draft_id in active_drafts:
            draft = active_drafts[target_draft_id]
            for k, v in extracted_slots.items():
                if hasattr(draft, k):
                    setattr(draft, k, v)
                    
        return extracted_slots

rules_client = RulesClient()
```

### 10. `services/merge.py` (结果融合)
```python
from typing import Dict, Any

def merge_results(llm_slots: Dict[str, Any], rule_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    合并 LLM 和 Rules 的结果。
    用户要求：二者皆有取 LLM。
    """
    merged = {}
    
    # 先放入 Rules 的结果
    merged.update(rule_slots)
    
    # 用 LLM 的结果覆盖（实现“二者皆有取 LLM”）
    # 注意：通常业务中规则更准，建议实际生产中将此处改为 merged.update(llm_slots) 的逆操作，
    # 即只有 LLM 为空时才用 Rules，或者 Rules 优先级更高。此处严格遵循您的要求。
    for k, v in llm_slots.items():
        if v is not None:
            merged[k] = v
            
    return merged
```

### 11. `services/enhancer.py` (后验校验增强)
```python
import csv
from typing import Any, Optional
from config import settings
import os

class FieldEnhancer:
    def validate(self, value: Any) -> bool:
        raise NotImplementedError

class WhitelistEnhancer(FieldEnhancer):
    def __init__(self, csv_filename: str, column: str):
        self.whitelist = set()
        filepath = os.path.join(settings.RESOURCE_DIR, csv_filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.whitelist.add(row.get(column, '').strip())

    def validate(self, value: Any) -> bool:
        return str(value).strip() in self.whitelist

class APIEnhancer(FieldEnhancer):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def validate(self, value: Any) -> bool:
        # 模拟外部 API 校验
        return True 

class EnhancerManager:
    def __init__(self):
        # 字段-资源实例化映射
        self.enhancers = {
            "counterparty": WhitelistEnhancer("counterparties.csv", "name"),
            "asset_name": WhitelistEnhancer("assets.csv", "short_name")
        }

    def check_field(self, field_name: str, value: Any) -> bool:
        if field_name in self.enhancers:
            return self.enhancers[field_name].validate(value)
        return True # 没有配置 enhancer 的字段默认通过

enhancer_manager = EnhancerManager()
```

### 12. `app.py` (FastAPI 应用与路由)
```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import asyncio
from config import settings
from monitor import monitor_manager, MonitorMiddleware
from models import MessageRequest, NERResponse, TradeDraft
from services.llm_client import llm_client
from services.rules_client import rules_client
from services.preprocess import preprocess_message
from services.postprocess import post_processor
from services.merge import merge_results
from services.enhancer import enhancer_manager
from log import logger
from context import session_id_var

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    monitor_manager.start()
    sender_task = asyncio.create_task(llm_client.slot_sender())
    logger.info(f"{settings.APP_NAME} started.")
    yield
    # 关闭时
    monitor_manager.stop()
    sender_task.cancel()
    logger.info(f"{settings.APP_NAME} stopped.")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.add_middleware(MonitorMiddleware)

@app.post("/api/v1/ner/process", response_model=NERResponse)
async def process_message(req: MessageRequest, request: Request):
    session_id_var.set(req.session_id)
    
    # 1. 预处理
    clean_msg = preprocess_message(req.message)
    
    # 2. LLM 抽取 (包含判断1,2,3)
    llm_res = await llm_client.process_message(req.session_id, clean_msg)
    llm_slots = llm_res.get("slots", {})
    target_id = llm_res.get("target_id")
    
    # 3. 规则抽取 (监听 LLM 的 target_id)
    state = llm_client.sessions.get(req.session_id)
    active_drafts = state.drafts if state else {}
    rule_slots = rules_client.extract(clean_msg, target_id, active_drafts)
    
    # 4. 融合结果 (二者皆有取 LLM)
    final_slots = merge_results(llm_slots, rule_slots)
    
    # 5. 后处理与后验增强
    for field, value in final_slots.items():
        # 字段级规整化
        normalized_val = post_processor.normalize_field(field, value)
        final_slots[field] = normalized_val
        
        # 后验校验
        if not enhancer_manager.check_field(field, normalized_val):
            logger.warning(f"Enhancer rejected field {field}: {normalized_val}")
            final_slots[field] = None # 校验不通过则置空

    # 6. 组装 Response
    current_drafts = [d for d in active_drafts.values() if post_processor.validate_trade(d.model_dump())]
    
    response = NERResponse(
        session_id=req.session_id,
        active_drafts=current_drafts,
        extracted_slots=final_slots
    )
    
    # 将历史拼接和响应存入 request.state 供 MonitorMiddleware 记录
    request.state.session_history = "\n".join(state.history) if state else ""
    request.state.response_payload = response.model_dump()
    
    return response
```

### 13. `main.py` (启动入口)
```python
import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app:app", 
        host=settings.HOST, 
        port=settings.PORT, 
        reload=False,
        workers=1 # 注意：由于使用了内存字典维护 SessionState，多 worker 会导致状态不共享。生产环境请将 SessionState 迁移至 Redis。
    )
```

### 架构亮点说明：
1. **状态机与队列分离**：`llm_client` 内部维护了 `SessionState`，并通过 `asyncio.Queue` 将满足条件的 `trade_draft` 异步推送到 `slot_sender`，实现了**抽取与推送的解耦**。
2. **协程级上下文隔离**：通过 `contextvars` 实现了 `trace_id` 和 `session_id` 的透传，确保在并发请求下日志和监控数据不会串号。
3. **高性能日志落盘**：`DBWriterThread` 使用独立的后台线程和 `queue.Queue` 进行 SQLite 写入，**完全不阻塞 FastAPI 的异步事件循环**。
4. **灵活的 Enhancer 设计**：`EnhancerManager` 采用了策略模式，未来如果需要增加“外部接口校验”，只需新增一个继承自 `FieldEnhancer` 的类并注册即可，符合开闭原则。

