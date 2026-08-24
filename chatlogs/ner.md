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
我消化一下：
1. 建立状态机。状态储存在redis或本地sqlite db里。存储的维度是session_id-trade_draft-slot
2. 增量更新方案。LLM作为处理机，每次有最新消息进来时，执行 读取该session当前所有trade_draft状态、该session近期对话历史、最新消息，输出结构化的操作指令Actions
3. Actions要包括对涉及的每一条trade_draft的定位id、动作、字段值和理由等。根据Actions定位到对应trade_draft, 再去去更新对应的存储状态
我有如下问题：
1. 目前系统接收的会话，会是连续不断的消息记录(with发送人id)。你说前端请求要带session_id, 想问下这怎么带？
2. 就目前的架构，我没看到session_id起到的作用: 定位靠trade_draft，填充的是slot。session_id仅是trade_draft的集合，没看到起作用的点
```

---
🤖**assistant**:
---

你消化的方向是对的，但我建议你把 `session_id` 从“trade_draft 的集合”这个理解，升级成：

> **session 是一次“交易协商上下文”的边界。**  
> 它不是简单地把多个 trade_draft 放在一起，而是决定了：  
> “当前这句话属于哪一场谈判、能看见哪些候选交易草稿、允许更新哪些字段、什么时候结束、成单后归属哪次协商。”

你的两个问题非常关键，下面分别展开。

---

# 一、如果系统现在只接收连续消息记录，`session_id` 怎么带？

你不一定要求前端天然传一个标准 `session_id`。更现实的做法是：

> **前端或上游消息系统能带就带；不能带，就在你的服务入口做 Session Resolver，由后端推断。**

也就是说，`session_id` 可以不是前端传的，而是你的 NER 服务自己“算出来”的。

---

## 1. 最理想情况：上游本来就有会话概念

如果你们的聊天系统里有下面任何一种 ID，都可以直接映射成 `session_id` 或生成 `session_id` 的基础：

| 上游已有概念 | 可映射为什么 |
|---|---|
| 私聊窗口 | `conversation_id` |
| 群聊 / 交易群 | `conversation_id` 或 `room_id` |
| 消息线程 / 引用回复 | `thread_id` |
| 某个交易请求单 | `deal_request_id` |
| 某个机器人任务 | `task_id` |
| 交易员之间的一次询价 | `inquiry_id` |

比如消息可以长这样：

```json
{
  "message_id": "msg_1001",
  "sender_id": "trader_A",
  "receiver_id": "trader_B",
  "channel": "qq",
  "conversation_id": "conv_8899",
  "content": "24长发和25诚通有量吗？",
  "ts": 1730000000
}
```

你可以先定义：

```text
conversation_id = 通信层会话
session_id = 业务层交易协商会话
```

第一版可以简单粗暴：

```text
session_id = conversation_id + 时间窗口
```

例如：

```text
session_id = conv_8899:20260622:active
```

或者：

```text
session_id = conv_8899:session_0001
```

---

## 2. 如果上游没有明确会话，只有一条连续消息流怎么办？

这是你描述的情况：

> 系统接收的是连续不断的消息记录，只有发送人 ID、内容、时间等。

那就需要在你的服务入口加一层：

> **Session Resolver：会话切分器。**

它的任务是：  
每来一条新消息，判断这条消息属于哪个 `session`。

---

## 3. Session Resolver 的最简规则

你可以先从简单规则开始，不需要一上来做很复杂。

### 方案 A：按“通信对象 + 时间窗口”切分

例如：

```text
conversation_key = sender_id + receiver_id
```

或者如果是群聊：

```text
conversation_key = group_id
```

然后：

```text
如果 conversation_key 当前有活跃 session，并且最近 30 分钟内有消息：
    归入当前 session
否则：
    创建新 session
```

示例：

```text
10:00 A: 24长发有量吗？
10:01 B: 100.8 有 2000
10:02 A: 价格再看看
10:03 B: 100.75 可以

10:45 A: 另外问一笔 25诚通
```

如果空闲阈值是 30 分钟，那么 10:45 这条可能会开启新 session。

---

### 方案 B：按“交易日 + 通信对象”切分

金融交易场景里，很多时候可以按交易日切：

```text
session_id = trader_pair + trading_day
```

例如：

```text
A_B_20260622_session
```

这种方式简单稳定，适合交易员一天内围绕若干笔交易持续沟通。

---

### 方案 C：按“显式开始 / 结束”切分

如果业务上允许，最好有显式信号：

```text
开始：新需求 / 帮我开一笔 / 开始谈这个
结束：先这样 / 不做了 / 成交 / 取消 / 结束
```

例如：

```text
A: 我们聊一下 24长发
```

创建新 session。

```text
A: 这笔先不做了
```

关闭当前 session。

```text
A: OK done
```

把对应 trade_draft 标记 confirmed，并可能关闭整个 session。

---

### 方案 D：按“消息主题 / 标的”切分

当消息里出现新标的时，可以选择：

1. 在当前 session 里新增一个 `trade_draft`；
2. 或者开启一个新的 `session`。

对于你现在这个场景：

> 询问方可能同时询问两条交易的具体信息，然后回答方回复，双方逐步在聊天中补齐所有字段。

我更建议：

> **同一个 session 内允许多个 trade_draft。**

因为用户经常会说：

```text
前者 2000
后者不要了
两笔价格都行
刚才第二笔量改一下
```

这些表达需要共享上下文。如果把两笔交易拆成两个 session，反而不好处理“前者、后者、两笔都”这种说法。

---

## 4. 推荐的第一版做法

如果你们现在只有连续消息流，我建议第一版这样设计：

### 输入消息

```json
{
  "message_id": "msg_001",
  "sender_id": "user_123",
  "receiver_id": "user_456",
  "group_id": null,
  "content": "前者量加到2000",
  "ts": 1730000000
}
```

### 后端生成 `conversation_key`

如果是私聊：

```python
conversation_key = f"private:{min(sender_id, receiver_id)}:{max(sender_id, receiver_id)}"
```

如果是群聊：

```python
conversation_key = f"group:{group_id}"
```

### 查找活跃 session

Redis 里可以存：

```text
dst:conv:{conversation_key}:active_session
```

例如：

```text
dst:conv:group:8899:active_session = session_20260622_0001
```

### 如果不存在或过期，则创建新 session

```python
session_id = create_session(conversation_key, message)
```

然后写回：

```python
redis.set(
    f"dst:conv:{conversation_key}:active_session",
    session_id,
    ex=3600
)
```

### 如果存在，则继续用当前 session

```python
session_id = redis.get(f"dst:conv:{conversation_key}:active_session")
```

---

## 5. 前端到底要不要传？

可以分阶段。

### 第一阶段：前端不传也可以

你的服务接受原始消息：

```json
{
  "sender_id": "user_123",
  "receiver_id": "user_456",
  "content": "24长发 100.8 有量吗？",
  "ts": 1730000000
}
```

后端自己算：

```json
{
  "conversation_key": "private:user_123:user_456",
  "session_id": "session_20260622_0001"
}
```

这是最容易落地的。

---

### 第二阶段：前端或上游传一个 `conversation_id`

比如：

```json
{
  "conversation_id": "conv_8899",
  "sender_id": "user_123",
  "content": "前者量加到2000"
}
```

后端基于：

```text
conversation_id + 时间窗口
```

生成或查找 `session_id`。

---

### 第三阶段：前端显式传 `session_id`

如果前端有交易协商卡片、任务窗口、聊天面板，那么前端可以直接传：

```json
{
  "session_id": "session_20260622_0001",
  "content": "这笔确认"
}
```

这时后端最省心。

---

# 二、`session_id` 到底起什么作用？

你说：

> 定位靠 trade_draft，填充的是 slot。session_id 仅是 trade_draft 的集合，没看到起作用的点。

这个理解需要修正一下。

更准确地说：

```text
session_id 决定“候选上下文范围”；
trade_draft 决定“具体交易对象”；
slot 决定“交易字段值”。
```

`session_id` 的作用不是直接定位字段，而是解决下面这些关键问题。

---

# 1. 没有 `session`，模型不知道“当前有哪些候选交易”

你说定位靠 `trade_draft`，这没错。

但问题是：

> 模型怎么知道应该定位到哪一个 `trade_draft`？

比如用户说：

```text
前者量加到2000
```

模型必须知道：

1. 当前 session 里有哪些 `trade_draft`；
2. 它们的顺序是什么；
3. 它们的名称 / 代码 / 别名是什么；
4. 哪一个最近被提到；
5. 哪一个是“前者”。

这些信息来自当前 `session` 的状态。

如果没有 `session`，模型要么看不到上下文，要么只能看到全局所有历史交易草稿。全局历史会非常混乱。

例如系统里历史上有很多交易：

```text
draft_001: 24长发
draft_002: 25诚通
draft_003: 23城投
draft_004: 24长发
draft_005: 25诚通
...
```

用户现在说：

```text
前者可以
```

如果没有当前 session 范围，模型根本不知道是哪一个“前者”。

---

# 2. `session` 是多笔交易并行时的“谈判桌”

你可以把 `session` 理解成一张谈判桌。

例如：

```text
session_001 谈判桌上有：
  draft_1: 24长发
  draft_2: 25诚通
```

用户说：

```text
两笔都是1000吗？
```

模型知道它是在问这张谈判桌上的两个 draft。

如果没有 `session`，系统可能会把这句话关联到别的谈判桌上的交易。

所以：

```text
session 不是 trade_draft 的简单集合；
session 是“当前正在协商的一组交易草稿及其上下文”。
```

---

# 3. `session` 解决指代消解问题

多轮聊天里最难的是指代：

```text
前者
后者
这笔
那笔
刚才那个
第二笔
长发那笔
诚通那个
你刚报的那个
```

这些词本身不包含完整实体信息。

模型需要结合：

```text
当前 session 内的近期消息 + 当前 session 内的 trade_draft 列表
```

才能推断：

```text
前者 = draft_1
后者 = draft_2
```

如果没有 `session`，这些指代没有锚点。

---

# 4. `session` 决定状态生命周期

交易协商是有生命周期的。

比如一个 `session` 可以有状态：

```text
active       活跃中
negotiating  谈判中
confirmed    已确认
cancelled    已取消
expired      已过期
closed       已关闭
```

如果没有 `session`，你很难判断一句话是否还能更新某个交易。

例如：

```text
10:00 A: 24长发 100.8 可以吗？
10:01 B: 可以
10:02 A: done
```

这时应该关闭或确认相关交易。

之后 11:00 又来一句：

```text
价格再改一下
```

如果没有 `session`，系统不知道这句是不是还能更新刚才那笔已确认交易。

如果有 `session`，你可以判断：

```text
当前 session 已关闭 / 已确认
这句话不能直接更新原交易，而是需要新建协商或触发人工确认
```

---

# 5. `session` 控制 LLM 上下文成本

如果你没有 `session`，每次模型要理解当前消息，可能需要加载：

```text
所有历史交易草稿
所有历史消息
所有用户聊天
```

这会带来三个问题：

1. Token 成本高；
2. 上下文太长；
3. 模型容易被无关历史干扰。

有了 `session`，你只需要喂：

```text
当前 session 的 drafts
当前 session 最近 N 条消息
最新消息
```

例如：

```json
{
  "current_drafts": [
    {
      "draft_id": "draft_1",
      "asset_name": "24长发",
      "price": 100.85,
      "amount": null
    },
    {
      "draft_id": "draft_2",
      "asset_name": "25诚通",
      "price": 100.36,
      "amount": 1000
    }
  ],
  "recent_history": [
    "A: 24长发和25诚通有量吗？",
    "B: 长发100.85，诚通100.36",
    "A: 前者量加到2000"
  ]
}
```

这样模型更稳，成本也低。

---

# 6. `session` 是审计和反馈的归属单位

后续你一定会遇到这些问题：

```text
这笔交易为什么识别成这样？
模型哪一句话理解错了？
当时上下文是什么？
用户纠错的是哪一轮状态？
成单结果对应哪段聊天？
```

如果没有 `session`，你很难复盘。

有了 `session`，你可以把以下内容串起来：

```text
消息
模型输出
状态变更
用户纠错
最终成单
反馈记录
```

例如：

```text
session_id = session_001
message_id = msg_123
draft_id = draft_1
field = amount
old_value = 1000
new_value = 2000
reason = 用户说“前者量加到2000”
```

这会非常有用。

---

# 三、推荐的数据模型

你可以把模型设计成四层：

```text
Message 层：原始消息
Session 层：协商上下文
TradeDraft 层：交易草稿
Slot / Field 层：字段状态
Event 层：状态变更事件
```

---

## 1. Session 表

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    conversation_key TEXT,
    channel TEXT,
    status TEXT,
    started_at TIMESTAMP,
    updated_at TIMESTAMP,
    expired_at TIMESTAMP
);
```

示例：

```json
{
  "session_id": "session_001",
  "conversation_key": "group_8899",
  "channel": "qq",
  "status": "negotiating",
  "started_at": "2026-06-22 10:00:00",
  "updated_at": "2026-06-22 10:05:00"
}
```

---

## 2. Message 表

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT,
    sender_id TEXT,
    content TEXT,
    ts TIMESTAMP
);
```

示例：

```json
{
  "message_id": "msg_1001",
  "session_id": "session_001",
  "sender_id": "trader_A",
  "content": "前者量加到2000",
  "ts": "2026-06-22 10:05:00"
}
```

---

## 3. TradeDraft 表

```sql
CREATE TABLE trade_drafts (
    draft_id TEXT PRIMARY KEY,
    session_id TEXT,
    asset_name TEXT,
    asset_code TEXT,
    direction TEXT,
    amount REAL,
    price REAL,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

示例：

```json
{
  "draft_id": "draft_1",
  "session_id": "session_001",
  "asset_name": "24长发",
  "asset_code": null,
  "direction": "bid",
  "amount": 2000,
  "price": 100.85,
  "status": "negotiating"
}
```

---

## 4. Slot 状态

你可以一开始不用单独建 slot 表，而是把字段状态放进 JSON。

例如：

```json
{
  "draft_id": "draft_1",
  "slots": {
    "asset_name": {
      "value": "24长发",
      "status": "confirmed",
      "source_message_id": "msg_1000"
    },
    "price": {
      "value": 100.85,
      "status": "proposed",
      "source_message_id": "msg_1001"
    },
    "amount": {
      "value": 2000,
      "status": "proposed",
      "source_message_id": "msg_1005"
    }
  }
}
```

这里我建议每个字段不要只存值，而是存：

```json
{
  "value": 100.85,
  "status": "proposed",
  "source_message_id": "msg_1001",
  "confidence": 0.92
}
```

因为在交易场景里：

```text
提到 ≠ 确认
报价 ≠ 成交
修改 ≠ 最终确认
```

字段状态可以是：

```text
missing     缺失
proposed    已提出
confirmed   已确认
rejected    已拒绝
ambiguous   有歧义
```

---

## 5. Event 表，非常重要

强烈建议加一个状态变更事件表：

```sql
CREATE TABLE draft_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT,
    draft_id TEXT,
    message_id TEXT,
    action_type TEXT,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    reasoning TEXT,
    created_at TIMESTAMP
);
```

示例：

```json
{
  "event_id": "evt_001",
  "session_id": "session_001",
  "draft_id": "draft_1",
  "message_id": "msg_1005",
  "action_type": "UPDATE",
  "field": "amount",
  "old_value": 1000,
  "new_value": 2000,
  "reasoning": "用户说前者量加到2000，根据上下文前者指24长发"
}
```

这个表的价值很大：

1. 可审计；
2. 可回滚；
3. 可做 feedback；
4. 可分析模型错误；
5. 可解释为什么状态变成这样。

---

# 四、你现在的架构应该怎么跑？

可以抽象成下面这个流程。

---

## 1. 消息进入

```json
{
  "message_id": "msg_1005",
  "sender_id": "user_A",
  "receiver_id": "user_B",
  "content": "前者量加到2000",
  "ts": 1730000000
}
```

---

## 2. Session Resolver

```python
conversation_key = resolve_conversation_key(message)
session_id = get_active_session(conversation_key)

if not session_id or is_expired(session_id):
    session_id = create_session(conversation_key, message)
```

---

## 3. 加载当前状态

```python
session = load_session(session_id)
drafts = load_drafts(session_id)
history = load_recent_messages(session_id, limit=10)
```

---

## 4. 调用 LLM 做增量理解

给 Qwen 的输入大概是：

```json
{
  "current_drafts": [
    {
      "draft_id": "draft_1",
      "asset_name": "24长发",
      "price": 100.85,
      "amount": 1000
    },
    {
      "draft_id": "draft_2",
      "asset_name": "25诚通",
      "price": 100.36,
      "amount": 1000
    }
  ],
  "recent_history": [
    "A: 24长发和25诚通有量吗？",
    "B: 长发100.85，诚通100.36，各1000",
    "A: 前者量加到2000"
  ],
  "latest_message": {
    "sender_id": "user_A",
    "content": "前者量加到2000"
  }
}
```

---

## 5. LLM 输出 Actions

```json
{
  "actions": [
    {
      "action_type": "UPDATE",
      "target_draft_id": "draft_1",
      "updates": {
        "amount": 2000
      },
      "reasoning": "用户说前者，结合当前草稿顺序，前者指24长发；量加到2000表示更新amount"
    }
  ]
}
```

---

## 6. 后端执行 Actions

```python
for action in actions:
    if action["action_type"] == "UPDATE":
        draft = find_draft(drafts, action["target_draft_id"])
        apply_updates(draft, action["updates"], message_id)
```

---

## 7. 保存状态并写事件

```python
save_session(session)
save_drafts(drafts)
save_events(events)
```

---

# 五、`session_id` 的实际作用举例

下面这个例子可以说明为什么需要 `session_id`。

---

## 没有 session 的情况

系统里全局有很多草稿：

```text
draft_001: 24长发，昨天
draft_002: 25诚通，昨天
draft_003: 24长发，今天
draft_004: 25诚通，今天
```

用户现在说：

```text
前者可以
```

模型很难判断：

```text
前者 = draft_001？
前者 = draft_003？
前者 = 今天这笔？
前者 = 当前聊天里提到的那笔？
```

---

## 有 session 的情况

当前：

```json
{
  "session_id": "session_001",
  "drafts": [
    {
      "draft_id": "draft_003",
      "asset_name": "24长发"
    },
    {
      "draft_id": "draft_004",
      "asset_name": "25诚通"
    }
  ]
}
```

用户说：

```text
前者可以
```

模型只需要在当前 `session_001` 里判断：

```text
前者 = draft_003
```

这就清楚很多。

---

# 六、关于“定位靠 trade_draft”的进一步说明

你说定位靠 `trade_draft`，这没错，但要注意：

> 用户嘴里不会说 `draft_id`。

用户会说：

```text
前者
后者
这笔
那笔
长发
诚通
第二笔
刚才那个
你报的第二个
```

所以 LLM 输出的定位方式不一定直接是 `draft_id`，可以是一组定位线索。

例如：

```json
{
  "target": {
    "draft_id": "draft_1",
    "asset_name": "24长发",
    "ordinal": 1,
    "reference": "前者"
  }
}
```

后端再做最终匹配。

更稳妥的做法是：

```json
{
  "action_type": "UPDATE",
  "target": {
    "draft_id": "draft_1",
    "matched_by": "ordinal_reference",
    "confidence": 0.92
  },
  "updates": {
    "amount": 2000
  }
}
```

如果置信度低，就不要直接更新，而是反问：

```text
您说的“前者”是指 24长发 这一笔吗？
```

---

# 七、推荐你的 Action Schema

你可以把 LLM 输出的 Action 设计成下面这样。

```json
{
  "actions": [
    {
      "action_type": "CREATE | UPDATE | CONFIRM | REJECT | CLARIFY | CANCEL",
      "target": {
        "draft_id": "draft_1",
        "asset_name": "24长发",
        "asset_code": "032481632.IB",
        "reference_expression": "前者",
        "ordinal": 1
      },
      "updates": {
        "amount": 2000,
        "price": 100.88
      },
      "confidence": 0.93,
      "reasoning": "用户说前者量加到2000，结合当前草稿顺序，前者指24长发"
    }
  ],
  "clarify_question": null
}
```

---

## Action 类型建议

| action_type | 含义 |
|---|---|
| `CREATE` | 发现新的交易意图，创建新的 trade_draft |
| `UPDATE` | 更新某个 trade_draft 的字段 |
| `CONFIRM` | 用户确认某笔交易 |
| `REJECT` | 用户拒绝某笔交易 |
| `CANCEL` | 用户取消某笔交易 |
| `CLARIFY` | 信息不明确，需要反问 |
| `NOOP` | 当前消息没有有效状态变更 |

---

# 八、什么时候不应该直接更新，而应该反问？

交易场景里不能所有识别结果都直接落库。

比如用户说：

```text
量改一下
```

但没有说改哪笔，也没说改成多少。

这时应该：

```json
{
  "action_type": "CLARIFY"
}
```

反问：

```text
请问您要修改哪一笔的量？修改为多少？
```

再比如：

```text
后者价格不太对
```

但没有说正确价格是多少。

可以反问：

```text
请问 25诚通 的正确价格是多少？
```

---

# 九、最小可行架构建议

如果你现在要落地，我建议不要一开始做得太复杂。第一版可以这样：

---

## 1. 用 `conversation_key` 生成活跃 `session`

```python
conversation_key = f"{channel}:{sender_id}:{receiver_id}"
```

群聊则是：

```python
conversation_key = f"{channel}:{group_id}"
```

---

## 2. Redis 存活跃 session

```text
dst:conv:{conversation_key}:active_session
```

例如：

```text
dst:conv:qq:group_8899:active_session = session_001
```

过期时间：

```text
30 分钟 / 60 分钟 / 当日有效
```

---

## 3. Redis 或 SQLite 存 session 状态

Redis 适合做实时状态：

```text
dst:session:{session_id}:state
```

内容：

```json
{
  "session_id": "session_001",
  "status": "negotiating",
  "drafts": [
    {
      "draft_id": "draft_1",
      "asset_name": "24长发",
      "price": 100.85,
      "amount": 1000,
      "status": "negotiating"
    },
    {
      "draft_id": "draft_2",
      "asset_name": "25诚通",
      "price": 100.36,
      "amount": 1000,
      "status": "negotiating"
    }
  ]
}
```

如果需要审计和复盘，建议同步写 SQLite / MySQL / PostgreSQL。

---

## 4. 每次消息处理流程

```python
def on_message(message):
    conversation_key = resolve_conversation_key(message)
    session_id = session_resolver.resolve(conversation_key, message)

    session_state = load_session_state(session_id)
    recent_messages = load_recent_messages(session_id, limit=10)

    llm_result = llm_extract_actions(
        drafts=session_state["drafts"],
        history=recent_messages,
        latest_message=message
    )

    events = apply_actions(
        session_id=session_id,
        drafts=session_state["drafts"],
        actions=llm_result["actions"],
        message=message
    )

    save_session_state(session_state)
    save_messages(message, session_id)
    save_events(events)

    return session_state
```

---

# 十、你可以把 `session_id` 理解成什么？

可以用一个类比。

```text
session_id = 当前这桌谈判
trade_draft = 桌上正在谈的几笔交易
slot = 每笔交易里的具体条款
message = 双方刚才说的话
action = 这句话导致桌上哪个条款发生变化
event = 变化记录
```

如果没有 `session_id`，相当于所有交易员所有历史谈判都挤在同一张桌子上。  
这时有人说一句“前者可以”，系统根本不知道他在说哪张桌子上的哪笔交易。

---

# 十一、总结你的两个问题

## 问题 1：前端请求怎么带 `session_id`？

答案是：

> 能带最好；不能带就后端推断。

具体做法：

1. 如果上游有 `conversation_id / room_id / thread_id`，直接用它作为基础。
2. 如果没有，就用 `发送人 + 接收人 / 群组 + 时间窗口` 生成 `conversation_key`。
3. 在服务入口加 `Session Resolver`，维护活跃 `session`。
4. 第一版可以不让前端传，由后端消息接入层自动生成并绑定。

---

## 问题 2：`session_id` 到底有什么用？

答案是：

> `session_id` 不是简单的 `trade_draft` 集合，而是交易协商的上下文边界。

它的作用包括：

1. 限定模型当前可见的候选 `trade_draft`；
2. 支持“前者、后者、这笔、那笔”的指代消解；
3. 支持多笔交易并行协商；
4. 控制状态生命周期；
5. 隔离不同聊天上下文；
6. 降低 LLM 上下文成本；
7. 方便审计、反馈和错误复盘；
8. 避免已关闭交易被后续消息误更新。

---

# 十二、我建议你的最终心智模型

把系统从：

```text
消息 -> NER抽取字段
```

升级为：

```text
消息 -> Session Resolver -> 当前协商状态 -> LLM增量理解 -> Actions -> 状态合并 -> 交易草稿更新 -> 成单/反馈
```

其中：

```text
session_id 管“这是哪一场协商”
trade_draft_id 管“这是哪一笔交易”
slot 管“这笔交易的字段现在是什么状态”
message_id 管“这个状态是哪句话导致的”
event 管“状态是怎么变化的”
```

这样你的服务才能从单条消息 NER，真正升级成多轮交易对话理解服务。


---
🙋**user**:
---
```
好。那么请根据你给出的增量处理方案，落地一份代码。要求用Python-FastAPI框架，所有的落盘数据采用sqlite。session采用前端不带session_id，留一个sessionResolver接口。要求做好代码拆分：src/models.py存储所有Pydantic模型，/data存储所有sqlite db文件, 以及其他必要文件和目录
```

---
🤖**assistant**:
---

下面给你一份**最小可运行、可继续扩展**的落地代码。

这份代码实现了：

1. 前端不传 `session_id`
2. 后端通过 `SessionResolver` 自动推断 / 创建 / 复用 `session`
3. 使用 SQLite 落盘所有数据，数据库文件放在 `data/` 目录
4. 每次新消息进来：
   - 解析所属 `session`
   - 读取当前 `trade_drafts`
   - 读取最近历史消息
   - 调用 `ActionExtractor` 输出增量 `Actions`
   - 后端根据 `Actions` 更新 `trade_draft`
   - 记录状态变更事件
5. 代码拆分清晰：
   - `src/models.py`：所有 Pydantic 模型
   - `src/db.py`：SQLite 连接与初始化
   - `src/state_store.py`：状态存储与状态合并
   - `src/session_resolver.py`：session 解析接口
   - `src/llm.py`：LLM/ActionExtractor 接口，默认提供 Mock 实现
   - `src/service.py`：主流程编排
   - `src/api.py`：FastAPI 路由

---

# 1. 项目目录

建议按下面目录创建：

```text
trade-dialogue-ner/
├── main.py
├── requirements.txt
├── README.md
├── data/
│   └── .gitkeep
└── src/
    ├── __init__.py
    ├── config.py
    ├── models.py
    ├── db.py
    ├── state_store.py
    ├── session_resolver.py
    ├── llm.py
    ├── service.py
    └── api.py
```

---

# 2. requirements.txt

```txt
fastapi
uvicorn[standard]
pydantic>=2
```

---

# 3. data/.gitkeep

空文件即可：

```text
```

---

# 4. src/__init__.py

```python
```

---

# 5. src/config.py

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app.db"

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

# mock / qwen
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
```

---

# 6. src/models.py

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """
    原始聊天消息。
    前端不传 session_id。
    """
    message_id: Optional[str] = None
    sender_id: str
    receiver_id: Optional[str] = None
    group_id: Optional[str] = None
    channel: str = "default"
    content: str
    ts: Optional[datetime] = None


class ActionType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    CANCEL = "CANCEL"
    CLARIFY = "CLARIFY"
    NOOP = "NOOP"


class ActionTarget(BaseModel):
    """
    LLM 对交易草稿的定位线索。
    """
    draft_id: Optional[str] = None
    asset_name: Optional[str] = None
    asset_code: Optional[str] = None
    reference_expression: Optional[str] = None
    ordinal: Optional[int] = None


class Action(BaseModel):
    """
    单条增量操作指令。
    """
    action_type: ActionType
    target: Optional[ActionTarget] = None
    updates: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    reasoning: Optional[str] = None


class LLMActionsResponse(BaseModel):
    """
    LLM/ActionExtractor 输出。
    """
    actions: List[Action] = Field(default_factory=list)
    clarify_question: Optional[str] = None


class SlotState(BaseModel):
    """
    单个字段的状态。
    """
    value: Any
    status: str = "proposed"  # proposed / confirmed / rejected / ambiguous
    source_message_id: Optional[str] = None
    confidence: Optional[float] = None
    updated_at: Optional[datetime] = None


class TradeDraft(BaseModel):
    """
    一笔交易草稿。
    """
    draft_id: str
    session_id: str
    asset_name: Optional[str] = None
    asset_code: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[float] = None
    price: Optional[float] = None
    status: str = "negotiating"  # negotiating / confirmed / rejected / cancelled
    slots: Dict[str, SlotState] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Session(BaseModel):
    """
    一次交易协商上下文。
    """
    session_id: str
    conversation_key: str
    channel: str
    status: str = "negotiating"  # negotiating / closed / expired / cancelled
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None


class MessageRecord(BaseModel):
    """
    落盘后的消息记录。
    """
    message_id: str
    session_id: str
    sender_id: str
    receiver_id: Optional[str] = None
    group_id: Optional[str] = None
    channel: str = "default"
    content: str
    ts: datetime
    created_at: Optional[datetime] = None


class DraftEvent(BaseModel):
    """
    状态变更事件，用于审计、回滚、反馈。
    """
    event_id: str
    session_id: str
    draft_id: Optional[str] = None
    message_id: Optional[str] = None
    action_type: str
    field: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reasoning: Optional[str] = None
    created_at: Optional[datetime] = None


class ProcessResult(BaseModel):
    """
    单次消息处理结果。
    """
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    clarify_question: Optional[str] = None
    message_id: str


class SessionResolveResult(BaseModel):
    """
    SessionResolver 调试/解析接口返回。
    """
    session_id: str
    conversation_key: str
    created: bool
    session: Session


class SessionDetail(BaseModel):
    """
    查询 session 详情。
    """
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
    messages: List[MessageRecord] = Field(default_factory=list)
```

---

# 7. src/db.py

```python
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    conversation_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'negotiating',
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expired_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_conversation
ON sessions(conversation_key, status, updated_at);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    receiver_id TEXT,
    group_id TEXT,
    channel TEXT,
    content TEXT NOT NULL,
    ts TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_session
ON messages(session_id, ts);

CREATE TABLE IF NOT EXISTS trade_drafts (
    draft_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    asset_name TEXT,
    asset_code TEXT,
    direction TEXT,
    amount REAL,
    price REAL,
    status TEXT NOT NULL DEFAULT 'negotiating',
    slots_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_trade_drafts_session
ON trade_drafts(session_id);

CREATE TABLE IF NOT EXISTS draft_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    draft_id TEXT,
    message_id TEXT,
    action_type TEXT,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    reasoning TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_draft_events_session
ON draft_events(session_id);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA)
```

---

# 8. src/state_store.py

```python
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .models import (
    ActionType,
    DraftEvent,
    IncomingMessage,
    MessageRecord,
    Session,
    SlotState,
    TradeDraft,
)

ALLOWED_DRAFT_FIELDS = {
    "asset_name",
    "asset_code",
    "direction",
    "amount",
    "price",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def to_json_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def normalize_updates(updates: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    result = dict(updates or {})

    for field in ("amount", "price"):
        if field in result and result[field] is not None:
            try:
                result[field] = float(result[field])
            except Exception:
                pass

    return result


# ----------------------------
# row converters
# ----------------------------

def row_to_session(row) -> Session:
    return Session(
        session_id=row["session_id"],
        conversation_key=row["conversation_key"],
        channel=row["channel"],
        status=row["status"],
        started_at=parse_iso(row["started_at"]),
        updated_at=parse_iso(row["updated_at"]),
        expired_at=parse_iso(row["expired_at"]),
    )


def row_to_message(row) -> MessageRecord:
    return MessageRecord(
        message_id=row["message_id"],
        session_id=row["session_id"],
        sender_id=row["sender_id"],
        receiver_id=row["receiver_id"],
        group_id=row["group_id"],
        channel=row["channel"] or "default",
        content=row["content"],
        ts=parse_iso(row["ts"]),
        created_at=parse_iso(row["created_at"]),
    )


def row_to_draft(row) -> TradeDraft:
    slots_raw = json.loads(row["slots_json"] or "{}")
    slots = {
        key: SlotState(**value)
        for key, value in slots_raw.items()
    }

    return TradeDraft(
        draft_id=row["draft_id"],
        session_id=row["session_id"],
        asset_name=row["asset_name"],
        asset_code=row["asset_code"],
        direction=row["direction"],
        amount=row["amount"],
        price=row["price"],
        status=row["status"],
        slots=slots,
        created_at=parse_iso(row["created_at"]),
        updated_at=parse_iso(row["updated_at"]),
    )


def row_to_event(row) -> DraftEvent:
    return DraftEvent(
        event_id=row["event_id"],
        session_id=row["session_id"],
        draft_id=row["draft_id"],
        message_id=row["message_id"],
        action_type=row["action_type"],
        field=row["field"],
        old_value=row["old_value"],
        new_value=row["new_value"],
        reasoning=row["reasoning"],
        created_at=parse_iso(row["created_at"]),
    )


# ----------------------------
# session
# ----------------------------

def get_session(conn, session_id: str) -> Optional[Session]:
    row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    if not row:
        return None

    return row_to_session(row)


def find_active_session(
    conn,
    conversation_key: str,
    timeout_minutes: int,
) -> Optional[Session]:
    threshold = utcnow() - timedelta(minutes=timeout_minutes)

    row = conn.execute(
        """
        SELECT *
        FROM sessions
        WHERE conversation_key = ?
          AND status IN ('active', 'negotiating')
          AND updated_at >= ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (conversation_key, threshold.isoformat()),
    ).fetchone()

    if not row:
        return None

    return row_to_session(row)


def create_session(
    conn,
    conversation_key: str,
    channel: str,
    timeout_minutes: int = 30,
) -> Session:
    session_id = new_id("session")
    now = utcnow()
    expired_at = now + timedelta(minutes=timeout_minutes)

    conn.execute(
        """
        INSERT INTO sessions (
            session_id,
            conversation_key,
            channel,
            status,
            started_at,
            updated_at,
            expired_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            conversation_key,
            channel,
            "negotiating",
            iso(now),
            iso(now),
            iso(expired_at),
        ),
    )

    session = get_session(conn, session_id)
    assert session is not None
    return session


def touch_session(
    conn,
    session_id: str,
    timeout_minutes: int = 30,
) -> None:
    now = utcnow()
    expired_at = now + timedelta(minutes=timeout_minutes)

    conn.execute(
        """
        UPDATE sessions
        SET updated_at = ?, expired_at = ?
        WHERE session_id = ?
        """,
        (iso(now), iso(expired_at), session_id),
    )


# ----------------------------
# message
# ----------------------------

def upsert_message(
    conn,
    message: IncomingMessage,
    session_id: str,
) -> str:
    message_id = message.message_id or new_id("msg")
    ts = message.ts or utcnow()
    created_at = utcnow()

    conn.execute(
        """
        INSERT OR REPLACE INTO messages (
            message_id,
            session_id,
            sender_id,
            receiver_id,
            group_id,
            channel,
            content,
            ts,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            session_id,
            message.sender_id,
            message.receiver_id,
            message.group_id,
            message.channel,
            message.content,
            iso(ts),
            iso(created_at),
        ),
    )

    return message_id


def list_recent_messages(
    conn,
    session_id: str,
    limit: int = 20,
) -> List[MessageRecord]:
    rows = conn.execute(
        """
        SELECT *
        FROM messages
        WHERE session_id = ?
        ORDER BY ts ASC, rowid ASC
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()

    return [row_to_message(row) for row in rows]


# ----------------------------
# trade draft
# ----------------------------

def get_draft(conn, draft_id: str) -> Optional[TradeDraft]:
    row = conn.execute(
        "SELECT * FROM trade_drafts WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()

    if not row:
        return None

    return row_to_draft(row)


def list_drafts(conn, session_id: str) -> List[TradeDraft]:
    rows = conn.execute(
        """
        SELECT *
        FROM trade_drafts
        WHERE session_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (session_id,),
    ).fetchall()

    return [row_to_draft(row) for row in rows]


def create_draft(
    conn,
    session_id: str,
    updates: Dict[str, Any],
    message_id: Optional[str] = None,
) -> TradeDraft:
    updates = normalize_updates(updates)

    draft_id = new_id("draft")
    now = utcnow()

    asset_name = updates.get("asset_name")
    asset_code = updates.get("asset_code")
    direction = updates.get("direction")
    amount = updates.get("amount")
    price = updates.get("price")

    slots: Dict[str, Any] = {}

    for field in ALLOWED_DRAFT_FIELDS:
        value = updates.get(field)
        if value is None:
            continue

        slots[field] = SlotState(
            value=value,
            status="proposed",
            source_message_id=message_id,
            updated_at=now,
        ).model_dump(mode="json")

    conn.execute(
        """
        INSERT INTO trade_drafts (
            draft_id,
            session_id,
            asset_name,
            asset_code,
            direction,
            amount,
            price,
            status,
            slots_json,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            session_id,
            asset_name,
            asset_code,
            direction,
            amount,
            price,
            "negotiating",
            json.dumps(slots, ensure_ascii=False),
            iso(now),
            iso(now),
        ),
    )

    append_event(
        conn,
        session_id=session_id,
        draft_id=draft_id,
        message_id=message_id,
        action_type=ActionType.CREATE,
        field=None,
        old_value=None,
        new_value=updates,
        reasoning="create trade draft",
    )

    draft = get_draft(conn, draft_id)
    assert draft is not None
    return draft


def update_draft_fields(
    conn,
    draft_id: str,
    updates: Dict[str, Any],
    message_id: Optional[str],
    action_type: ActionType | str,
    reasoning: Optional[str] = None,
) -> List[str]:
    row = conn.execute(
        "SELECT * FROM trade_drafts WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()

    if not row:
        return []

    updates = normalize_updates(updates)
    slots = json.loads(row["slots_json"] or "{}")
    now = utcnow()

    action_name = (
        action_type.value
        if isinstance(action_type, ActionType)
        else str(action_type)
    )

    slot_status = (
        "confirmed"
        if action_name == ActionType.CONFIRM.value
        else "proposed"
    )

    changed_fields: List[str] = []

    for field, value in updates.items():
        if field not in ALLOWED_DRAFT_FIELDS:
            continue

        if value is None:
            continue

        old_value = row[field]

        if old_value == value:
            continue

        conn.execute(
            f"""
            UPDATE trade_drafts
            SET {field} = ?, updated_at = ?
            WHERE draft_id = ?
            """,
            (value, iso(now), draft_id),
        )

        slots[field] = SlotState(
            value=value,
            status=slot_status,
            source_message_id=message_id,
            updated_at=now,
        ).model_dump(mode="json")

        append_event(
            conn,
            session_id=row["session_id"],
            draft_id=draft_id,
            message_id=message_id,
            action_type=action_name,
            field=field,
            old_value=old_value,
            new_value=value,
            reasoning=reasoning,
        )

        changed_fields.append(field)

    if changed_fields:
        conn.execute(
            """
            UPDATE trade_drafts
            SET slots_json = ?, updated_at = ?
            WHERE draft_id = ?
            """,
            (
                json.dumps(slots, ensure_ascii=False),
                iso(now),
                draft_id,
            ),
        )

    return changed_fields


def set_draft_status(
    conn,
    draft_id: str,
    status: str,
    message_id: Optional[str],
    action_type: ActionType | str,
    reasoning: Optional[str] = None,
) -> None:
    row = conn.execute(
        "SELECT * FROM trade_drafts WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()

    if not row:
        return

    old_status = row["status"]

    if old_status == status:
        return

    now = utcnow()

    conn.execute(
        """
        UPDATE trade_drafts
        SET status = ?, updated_at = ?
        WHERE draft_id = ?
        """,
        (status, iso(now), draft_id),
    )

    append_event(
        conn,
        session_id=row["session_id"],
        draft_id=draft_id,
        message_id=message_id,
        action_type=action_type,
        field="status",
        old_value=old_status,
        new_value=status,
        reasoning=reasoning,
    )


# ----------------------------
# events
# ----------------------------

def append_event(
    conn,
    *,
    session_id: str,
    draft_id: Optional[str] = None,
    message_id: Optional[str] = None,
    action_type: ActionType | str,
    field: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    reasoning: Optional[str] = None,
) -> None:
    event_id = new_id("evt")
    now = utcnow()

    action_name = (
        action_type.value
        if isinstance(action_type, ActionType)
        else str(action_type)
    )

    conn.execute(
        """
        INSERT INTO draft_events (
            event_id,
            session_id,
            draft_id,
            message_id,
            action_type,
            field,
            old_value,
            new_value,
            reasoning,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            session_id,
            draft_id,
            message_id,
            action_name,
            field,
            to_json_value(old_value),
            to_json_value(new_value),
            reasoning,
            iso(now),
        ),
    )


def list_events(conn, session_id: str) -> List[DraftEvent]:
    rows = conn.execute(
        """
        SELECT *
        FROM draft_events
        WHERE session_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (session_id,),
    ).fetchall()

    return [row_to_event(row) for row in rows]
```

---

# 9. src/session_resolver.py

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .models import IncomingMessage, Session


class SessionResolver(ABC):
    """
    SessionResolver 接口。

    你后续可以替换成：
    1. 基于时间窗口
    2. 基于显式开始/结束
    3. 基于业务单号
    4. 基于模型判断
    """

    @abstractmethod
    def conversation_key(self, message: IncomingMessage) -> str:
        raise NotImplementedError

    @abstractmethod
    def resolve(self, conn, message: IncomingMessage) -> Session:
        raise NotImplementedError


class DefaultSessionResolver(SessionResolver):
    """
    默认规则：

    1. 如果有 group_id，则按群会话切分
    2. 如果是私聊，则按 sender_id + receiver_id 切分
    3. 在 SESSION_TIMEOUT_MINUTES 内有活跃 session，则复用
    4. 否则创建新 session
    """

    def conversation_key(self, message: IncomingMessage) -> str:
        if message.group_id:
            return f"{message.channel}:group:{message.group_id}"

        if message.receiver_id:
            a, b = sorted([message.sender_id, message.receiver_id])
            return f"{message.channel}:private:{a}:{b}"

        return f"{message.channel}:private:{message.sender_id}"

    def resolve(self, conn, message: IncomingMessage) -> Session:
        key = self.conversation_key(message)

        session = state_store.find_active_session(
            conn,
            conversation_key=key,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        if session:
            return session

        return state_store.create_session(
            conn,
            conversation_key=key,
            channel=message.channel,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )
```

---

# 10. src/llm.py

```python
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from .config import LLM_PROVIDER
from .models import (
    Action,
    ActionTarget,
    ActionType,
    IncomingMessage,
    LLMActionsResponse,
    MessageRecord,
    Session,
    TradeDraft,
)


CREATE_WORDS = [
    "新",
    "另外",
    "再开",
    "再加",
    "还有",
    "增加一笔",
    "新开",
]

REJECT_WORDS = [
    "不要了",
    "取消",
    "不做了",
    "拒绝",
    "算了",
]

CONFIRM_WORDS = [
    "确认",
    "成交",
    "done",
    "ok",
    "同意",
    "没问题",
]

STOP_SUFFIXES = "有量吗呢吧啊的了么和与跟及，。！？、；,：:"


class ActionExtractor(ABC):
    """
    增量动作抽取接口。

    生产环境建议替换为真实 Qwen / OpenAI-compatible API。
    """

    @abstractmethod
    def extract(
        self,
        *,
        session: Session,
        drafts: List[TradeDraft],
        history: List[MessageRecord],
        message: IncomingMessage,
    ) -> LLMActionsResponse:
        raise NotImplementedError


# ----------------------------
# helpers
# ----------------------------

def _extract_asset_names(text: str) -> List[str]:
    """
    非常粗糙的 mock 资产名抽取。

    仅用于演示，生产环境请交给 LLM。
    """
    raw = re.findall(
        r"\d{1,2}[\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9]{1,20}",
        text,
    )

    names: List[str] = []

    for token in raw:
        token = token.strip()

        while token and token[-1] in STOP_SUFFIXES:
            token = token[:-1]

        if len(token) >= 3:
            names.append(token)

    seen = set()
    result = []

    for name in names:
        if name not in seen:
            seen.add(name)
            result.append(name)

    return result


def _extract_amount(text: str) -> Optional[float]:
    m = re.search(
        r"(?:量|金额|面额|amount)[^\d]{0,10}?(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return float(m.group(1))

    m = re.search(r"加到\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))

    return None


def _extract_price(text: str) -> Optional[float]:
    m = re.search(
        r"(?:价格|净价|全价|价)[^\d]{0,10}?(\d+(?:\.\d+)?)",
        text,
    )
    if m:
        return float(m.group(1))

    if any(word in text for word in ["价格", "净价", "全价", "价"]):
        m = re.search(r"(\d+\.\d{1,4})", text)
        if m:
            return float(m.group(1))

    return None


def _parse_ordinal(text: str) -> int:
    if text.isdigit():
        return int(text)

    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }

    if text in mapping:
        return mapping[text]

    if "十" in text:
        parts = text.split("十", 1)
        left = parts[0]
        right = parts[1]

        left_value = mapping.get(left, 1) if left else 1
        right_value = mapping.get(right, 0) if right else 0

        return left_value * 10 + right_value

    return 1


def _name_exists(name: str, drafts: List[TradeDraft]) -> bool:
    lower_name = name.lower()

    for draft in drafts:
        if not draft.asset_name:
            continue

        lower_existing = draft.asset_name.lower()

        if lower_name in lower_existing or lower_existing in lower_name:
            return True

    return False


def _build_target(
    content: str,
    drafts: List[TradeDraft],
) -> Optional[ActionTarget]:
    lowered = content.lower()

    for draft in drafts:
        if draft.asset_name and draft.asset_name.lower() in lowered:
            return ActionTarget(
                draft_id=draft.draft_id,
                asset_name=draft.asset_name,
            )

        if draft.asset_code and draft.asset_code.lower() in lowered:
            return ActionTarget(
                draft_id=draft.draft_id,
                asset_code=draft.asset_code,
            )

    if any(word in content for word in ["前者", "第一笔", "第1笔"]):
        return ActionTarget(
            reference_expression="前者",
            ordinal=1,
        )

    if any(word in content for word in ["后者", "最后一笔", "最后的一笔", "第二笔", "第2笔"]):
        return ActionTarget(
            reference_expression="后者",
            ordinal=2,
        )

    m = re.search(r"第([0-9一二两三四五六七八九十]+)笔", content)
    if m:
        ordinal = _parse_ordinal(m.group(1))
        return ActionTarget(
            reference_expression=m.group(0),
            ordinal=ordinal,
        )

    if any(word in content for word in ["这笔", "当前这笔"]):
        return ActionTarget(reference_expression="这笔")

    if any(word in content for word in ["那笔"]):
        return ActionTarget(reference_expression="那笔")

    return None


# ----------------------------
# mock extractor
# ----------------------------

class MockActionExtractor(ActionExtractor):
    """
    本地规则 Mock。

    仅用于开发联调。
    生产环境请替换成真实 LLM。
    """

    def extract(
        self,
        *,
        session: Session,
        drafts: List[TradeDraft],
        history: List[MessageRecord],
        message: IncomingMessage,
    ) -> LLMActionsResponse:
        content = message.content.strip()
        content_lower = content.lower()

        actions: List[Action] = []
        clarify_question: Optional[str] = None

        asset_names = _extract_asset_names(content)
        new_names = [
            name
            for name in asset_names
            if not _name_exists(name, drafts)
        ]

        names_to_create: List[str] = []

        if not drafts and asset_names:
            names_to_create = asset_names
        elif new_names and any(word in content for word in CREATE_WORDS):
            names_to_create = new_names

        for name in names_to_create:
            actions.append(
                Action(
                    action_type=ActionType.CREATE,
                    target=ActionTarget(asset_name=name),
                    updates={"asset_name": name},
                    confidence=0.6,
                    reasoning="mock: create trade draft",
                )
            )

        target = _build_target(content, drafts)

        updates = {}

        amount = _extract_amount(content)
        if amount is not None:
            updates["amount"] = amount

        price = _extract_price(content)
        if price is not None:
            updates["price"] = price

        if any(word in content for word in REJECT_WORDS):
            actions.append(
                Action(
                    action_type=ActionType.REJECT,
                    target=target,
                    confidence=0.7,
                    reasoning="mock: reject/cancel",
                )
            )
        elif any(word.lower() in content_lower for word in CONFIRM_WORDS):
            actions.append(
                Action(
                    action_type=ActionType.CONFIRM,
                    target=target,
                    confidence=0.7,
                    reasoning="mock: confirm",
                )
            )
        elif updates:
            actions.append(
                Action(
                    action_type=ActionType.UPDATE,
                    target=target,
                    updates=updates,
                    confidence=0.7,
                    reasoning="mock: update fields",
                )
            )
        elif (
            not actions
            and len(drafts) > 1
            and target is None
            and ("?" in content or "？" in content or "哪" in content)
        ):
            clarify_question = "请问您指的是哪一笔？"

        return LLMActionsResponse(
            actions=actions,
            clarify_question=clarify_question,
        )


# ----------------------------
# qwen extractor placeholder
# ----------------------------

class QwenActionExtractor(ActionExtractor):
    """
    真实 Qwen 接入占位。

    这里已经给你准备好了 Prompt。
    你只需要把 Qwen API 返回的 JSON 解析成 LLMActionsResponse。
    """

    def extract(
        self,
        *,
        session: Session,
        drafts: List[TradeDraft],
        history: List[MessageRecord],
        message: IncomingMessage,
    ) -> LLMActionsResponse:
        prompt = build_prompt(
            session=session,
            drafts=drafts,
            history=history,
            message=message,
        )

        # TODO:
        # 1. 调用 Qwen API
        # 2. 要求模型严格输出 JSON
        # 3. 解析为 LLMActionsResponse
        #
        # 示例：
        # response = call_qwen_api(prompt)
        # return LLMActionsResponse.model_validate_json(response)

        raise NotImplementedError(
            "QwenActionExtractor 尚未接入真实 API。"
            "请先使用 LLM_PROVIDER=mock，或在 src/llm.py 中实现 Qwen 调用。\n"
            f"Prompt preview:\n{prompt[:500]}..."
        )


def get_action_extractor() -> ActionExtractor:
    provider = LLM_PROVIDER.lower()

    if provider == "mock":
        return MockActionExtractor()

    if provider == "qwen":
        return QwenActionExtractor()

    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


# ----------------------------
# prompt
# ----------------------------

def build_prompt(
    *,
    session: Session,
    drafts: List[TradeDraft],
    history: List[MessageRecord],
    message: IncomingMessage,
) -> str:
    drafts_payload = [
        {
            "draft_id": draft.draft_id,
            "asset_name": draft.asset_name,
            "asset_code": draft.asset_code,
            "direction": draft.direction,
            "amount": draft.amount,
            "price": draft.price,
            "status": draft.status,
        }
        for draft in drafts
    ]

    history_payload = [
        {
            "sender_id": item.sender_id,
            "content": item.content,
            "ts": str(item.ts),
        }
        for item in history[-10:]
    ]

    payload = {
        "session": {
            "session_id": session.session_id,
            "status": session.status,
        },
        "current_drafts": drafts_payload,
        "recent_history": history_payload,
        "latest_message": {
            "sender_id": message.sender_id,
            "content": message.content,
        },
    }

    return f"""
# Role
你是一个银行间市场交易对话状态追踪助手。

# Task
请根据【当前交易草稿状态】、【近期对话历史】和【最新一条消息】，分析最新消息带来了哪些增量状态变化。

# Rules
1. 你不要输出完整状态，只输出增量操作指令。
2. 支持动作：CREATE / UPDATE / CONFIRM / REJECT / CANCEL / CLARIFY / NOOP。
3. 如果能定位到具体 draft，请尽量输出 draft_id。
4. 如果用户使用“前者、后者、这笔、那笔、第一笔、第二笔”等指代，请结合当前草稿列表和近期历史判断。
5. 如果无法定位或信息不足，请输出 CLARIFY。
6. 严格输出 JSON，不要输出解释文本。

# Output Schema
{{
  "actions": [
    {{
      "action_type": "UPDATE",
      "target": {{
        "draft_id": "draft_xxx",
        "asset_name": "24长发",
        "reference_expression": "前者",
        "ordinal": 1
      }},
      "updates": {{
        "amount": 2000,
        "price": 100.88
      }},
      "confidence": 0.93,
      "reasoning": "用户说前者量加到2000"
    }}
  ],
  "clarify_question": null
}}

# Input
{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}
""".strip()
```

---

# 11. src/service.py

```python
from __future__ import annotations

from typing import List, Optional

from . import state_store
from .db import get_db
from .llm import ActionExtractor
from .models import (
    Action,
    ActionTarget,
    ActionType,
    IncomingMessage,
    ProcessResult,
    TradeDraft,
)
from .session_resolver import SessionResolver


def resolve_target(
    drafts: List[TradeDraft],
    target: Optional[ActionTarget],
) -> Optional[TradeDraft]:
    if not drafts:
        return None

    if target:
        if target.draft_id:
            for draft in drafts:
                if draft.draft_id == target.draft_id:
                    return draft

        if target.asset_name:
            lower_target = target.asset_name.lower()
            for draft in drafts:
                if not draft.asset_name:
                    continue

                lower_name = draft.asset_name.lower()
                if lower_target in lower_name or lower_name in lower_target:
                    return draft

        if target.asset_code:
            lower_code = target.asset_code.lower()
            for draft in drafts:
                if draft.asset_code and draft.asset_code.lower() == lower_code:
                    return draft

        if target.ordinal is not None:
            index = target.ordinal - 1
            if 0 <= index < len(drafts):
                return drafts[index]

        if target.reference_expression:
            ref = target.reference_expression.lower()

            if any(word in ref for word in ["前者", "第一", "第1", "first"]):
                return drafts[0]

            if any(word in ref for word in ["后者", "最后", "last"]):
                return drafts[-1]

            if any(word in ref for word in ["这笔", "当前"]):
                return drafts[-1]

            if any(word in ref for word in ["那笔"]):
                return drafts[0]

    return None


def _get_lookup_target(action: Action) -> ActionTarget:
    target = action.target.model_copy() if action.target else ActionTarget()

    if action.updates:
        if not target.asset_name and action.updates.get("asset_name"):
            target.asset_name = action.updates["asset_name"]

        if not target.asset_code and action.updates.get("asset_code"):
            target.asset_code = action.updates["asset_code"]

    return target


def apply_action(
    conn,
    *,
    session_id: str,
    drafts: List[TradeDraft],
    action: Action,
    message_id: str,
) -> Optional[str]:
    """
    返回 clarify_question。
    如果没有需要反问，则返回 None。
    """

    lookup_target = _get_lookup_target(action)

    if action.action_type == ActionType.CREATE:
        updates = dict(action.updates or {})

        if lookup_target.asset_name and not updates.get("asset_name"):
            updates["asset_name"] = lookup_target.asset_name

        if lookup_target.asset_code and not updates.get("asset_code"):
            updates["asset_code"] = lookup_target.asset_code

        existing = resolve_target(drafts, lookup_target)

        if existing:
            state_store.update_draft_fields(
                conn,
                draft_id=existing.draft_id,
                updates=updates,
                message_id=message_id,
                action_type=ActionType.UPDATE,
                reasoning=action.reasoning,
            )
        else:
            state_store.create_draft(
                conn,
                session_id=session_id,
                updates=updates,
                message_id=message_id,
            )

        return None

    if action.action_type == ActionType.UPDATE:
        target_draft = resolve_target(drafts, lookup_target)

        if not target_draft and len(drafts) == 1:
            target_draft = drafts[0]

        if not target_draft:
            clarify = "无法定位要更新的交易草稿，请补充标的或指代。"
            state_store.append_event(
                conn,
                session_id=session_id,
                draft_id=None,
                message_id=message_id,
                action_type=ActionType.CLARIFY,
                field=None,
                old_value=None,
                new_value=clarify,
                reasoning=action.reasoning,
            )
            return clarify

        if target_draft.status == "confirmed":
            state_store.append_event(
                conn,
                session_id=session_id,
                draft_id=target_draft.draft_id,
                message_id=message_id,
                action_type=ActionType.NOOP,
                field=None,
                old_value=None,
                new_value="draft already confirmed",
                reasoning="已确认交易默认不允许直接修改",
            )
            return None

        state_store.update_draft_fields(
            conn,
            draft_id=target_draft.draft_id,
            updates=action.updates,
            message_id=message_id,
            action_type=action.action_type,
            reasoning=action.reasoning,
        )

        return None

    if action.action_type in (
        ActionType.CONFIRM,
        ActionType.REJECT,
        ActionType.CANCEL,
    ):
        target_draft = resolve_target(drafts, lookup_target)

        if not target_draft and len(drafts) == 1:
            target_draft = drafts[0]

        if not target_draft:
            clarify = "无法定位要确认/取消的交易草稿，请补充标的或指代。"
            state_store.append_event(
                conn,
                session_id=session_id,
                draft_id=None,
                message_id=message_id,
                action_type=ActionType.CLARIFY,
                field=None,
                old_value=None,
                new_value=clarify,
                reasoning=action.reasoning,
            )
            return clarify

        status_map = {
            ActionType.CONFIRM: "confirmed",
            ActionType.REJECT: "rejected",
            ActionType.CANCEL: "cancelled",
        }

        state_store.set_draft_status(
            conn,
            draft_id=target_draft.draft_id,
            status=status_map[action.action_type],
            message_id=message_id,
            action_type=action.action_type,
            reasoning=action.reasoning,
        )

        return None

    if action.action_type == ActionType.CLARIFY:
        clarify = action.reasoning or "请补充信息。"
        state_store.append_event(
            conn,
            session_id=session_id,
            draft_id=None,
            message_id=message_id,
            action_type=ActionType.CLARIFY,
            field=None,
            old_value=None,
            new_value=clarify,
            reasoning=action.reasoning,
        )
        return clarify

    if action.action_type == ActionType.NOOP:
        state_store.append_event(
            conn,
            session_id=session_id,
            draft_id=None,
            message_id=message_id,
            action_type=ActionType.NOOP,
            field=None,
            old_value=None,
            new_value=None,
            reasoning=action.reasoning,
        )
        return None

    return None


def process_message(
    message: IncomingMessage,
    resolver: SessionResolver,
    extractor: ActionExtractor,
) -> ProcessResult:
    with get_db() as conn:
        session = resolver.resolve(conn, message)

        message_id = state_store.upsert_message(
            conn,
            message=message,
            session_id=session.session_id,
        )

        drafts = state_store.list_drafts(conn, session.session_id)
        history = state_store.list_recent_messages(
            conn,
            session_id=session.session_id,
            limit=20,
        )

        llm_result = extractor.extract(
            session=session,
            drafts=drafts,
            history=history,
            message=message,
        )

        clarify_question = llm_result.clarify_question

        for action in llm_result.actions:
            local_clarify = apply_action(
                conn,
                session_id=session.session_id,
                drafts=drafts,
                action=action,
                message_id=message_id,
            )

            if local_clarify and not clarify_question:
                clarify_question = local_clarify

            # 如果发生 CREATE，后续 action 需要看到最新 drafts
            drafts = state_store.list_drafts(conn, session.session_id)

        if llm_result.clarify_question:
            state_store.append_event(
                conn,
                session_id=session.session_id,
                draft_id=None,
                message_id=message_id,
                action_type=ActionType.CLARIFY,
                field=None,
                old_value=None,
                new_value=llm_result.clarify_question,
                reasoning="llm clarify",
            )

        state_store.touch_session(conn, session.session_id)

        session = state_store.get_session(conn, session.session_id)
        assert session is not None

        drafts = state_store.list_drafts(conn, session.session_id)

        return ProcessResult(
            session=session,
            drafts=drafts,
            actions=llm_result.actions,
            clarify_question=clarify_question,
            message_id=message_id,
        )
```

---

# 12. src/api.py

```python
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .db import get_db
from .llm import ActionExtractor, get_action_extractor
from .models import (
    DraftEvent,
    IncomingMessage,
    ProcessResult,
    SessionDetail,
    SessionResolveResult,
    TradeDraft,
)
from .service import process_message
from .session_resolver import DefaultSessionResolver, SessionResolver

router = APIRouter(prefix="/api")


def get_session_resolver() -> SessionResolver:
    """
    这里可以替换成自定义 SessionResolver。
    """
    return DefaultSessionResolver()


def get_extractor() -> ActionExtractor:
    return get_action_extractor()


@router.post("/messages", response_model=ProcessResult)
def api_process_message(
    payload: IncomingMessage,
    resolver: SessionResolver = Depends(get_session_resolver),
    extractor: ActionExtractor = Depends(get_extractor),
):
    """
    核心接口：接收一条新消息，执行增量状态更新。
    """
    return process_message(
        message=payload,
        resolver=resolver,
        extractor=extractor,
    )


@router.post("/session-resolver/resolve", response_model=SessionResolveResult)
def api_resolve_session(
    payload: IncomingMessage,
    resolver: SessionResolver = Depends(get_session_resolver),
):
    """
    SessionResolver 调试接口。

    前端仍然可以不传 session_id。
    这个接口用于查看某条消息会被分配到哪个 session。
    """
    with get_db() as conn:
        conversation_key = resolver.conversation_key(payload)

        existing = state_store.find_active_session(
            conn,
            conversation_key=conversation_key,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        session = resolver.resolve(conn, payload)

        return SessionResolveResult(
            session_id=session.session_id,
            conversation_key=conversation_key,
            created=existing is None,
            session=session,
        )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def api_get_session(session_id: str):
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(status_code=404, detail="session not found")

        drafts = state_store.list_drafts(conn, session_id)
        messages = state_store.list_recent_messages(
            conn,
            session_id=session_id,
            limit=100,
        )

        return SessionDetail(
            session=session,
            drafts=drafts,
            messages=messages,
        )


@router.get("/sessions/{session_id}/drafts", response_model=List[TradeDraft])
def api_get_session_drafts(session_id: str):
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(status_code=404, detail="session not found")

        return state_store.list_drafts(conn, session_id)


@router.get("/sessions/{session_id}/events", response_model=List[DraftEvent])
def api_get_session_events(session_id: str):
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(status_code=404, detail="session not found")

        return state_store.list_events(conn, session_id)
```

---

# 13. main.py

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import router
from src.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Trade Dialogue DST",
    description="多轮交易对话状态追踪与增量 NER 服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, tags=["dst"])


@app.get("/health")
def health():
    return {
        "status": "ok"
    }
```

---

# 14. README.md

```markdown
# Trade Dialogue DST

多轮交易对话状态追踪与增量 NER 服务。

## 功能

- 前端不传 session_id
- 后端自动解析 / 创建 / 复用 session
- SQLite 落盘
- 增量 Actions 更新 trade_draft
- 记录状态变更事件

## 启动

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## 示例

### 1. 第一条消息

```bash
curl -X POST http://127.0.0.1:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "trader_A",
    "receiver_id": "trader_B",
    "channel": "qq",
    "content": "24长发和25诚通有量吗？"
  }'
```

### 2. 更新前者量

```bash
curl -X POST http://127.0.0.1:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "trader_A",
    "receiver_id": "trader_B",
    "channel": "qq",
    "content": "前者量加到2000"
  }'
```

### 3. 更新后者价格

```bash
curl -X POST http://127.0.0.1:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "trader_B",
    "receiver_id": "trader_A",
    "channel": "qq",
    "content": "后者价格100.36"
  }'
```

### 4. 确认前者

```bash
curl -X POST http://127.0.0.1:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "trader_A",
    "receiver_id": "trader_B",
    "channel": "qq",
    "content": "前者确认"
  }'
```

## 查看 session

将返回中的 `session.session_id` 替换进去：

```bash
curl http://127.0.0.1:8000/api/sessions/{session_id}
```

## 数据库

默认 SQLite 文件：

```text
data/app.db
```

## 接入真实 Qwen

默认：

```text
LLM_PROVIDER=mock
```

如果要接入真实 Qwen：

1. 设置：

```bash
export LLM_PROVIDER=qwen
```

2. 在 `src/llm.py` 中实现：

```python
class QwenActionExtractor(ActionExtractor):
    def extract(...):
        prompt = build_prompt(...)
        # call Qwen API
        # parse JSON
        # return LLMActionsResponse
```

建议要求模型严格输出：

```json
{
  "actions": [],
  "clarify_question": null
}
```
```

---

# 15. 这套代码的运行逻辑

一次消息处理流程如下：

```text
POST /api/messages
        |
        v
SessionResolver.resolve()
        |
        v
找到或创建 session
        |
        v
消息落盘 messages
        |
        v
读取当前 session 的 trade_drafts
        |
        v
读取最近 history
        |
        v
ActionExtractor.extract()
        |
        v
得到 Actions
        |
        v
apply_action()
        |
        v
更新 trade_drafts
        |
        v
写入 draft_events
        |
        v
返回最新 session + drafts
```

---

# 16. 你后续接真实 Qwen 时，只需要改哪里？

核心只改一个地方：

```text
src/llm.py
```

你现在代码里已经预留了：

```python
class QwenActionExtractor(ActionExtractor):
    def extract(...):
        prompt = build_prompt(...)
        raise NotImplementedError
```

你只需要把它改成：

```python
response_text = call_qwen_api(prompt)
return LLMActionsResponse.model_validate_json(response_text)
```

其他部分不用大改。

---

# 17. 生产化建议

这份代码是**可运行的骨架**，如果你要上生产，建议继续补这几块：

1. **真实 Qwen 输出 JSON 的鲁棒解析**
   - 模型可能带 ```json
   - 可能输出解释文本
   - 需要做 JSON 清洗

2. **置信度控制**
   - `confidence < threshold` 时不要直接更新
   - 转为 `CLARIFY`

3. **字段级确认状态**
   - `proposed`
   - `confirmed`
   - `rejected`
   - `ambiguous`

4. **成单快照**
   - 当某个 `trade_draft.status == confirmed`
   - 生成一条 `final_trade_snapshot`
   - 推给下游 OMS / EMS

5. **反馈闭环**
   - 增加 `/api/feedback`
   - 关联 `session_id`、`draft_id`、`message_id`
   - 用于后续 prompt/few-shot/模型评估优化

6. **更复杂的 Session 切分**
   - 当前默认按聊天对象 + 超时时间
   - 后续可以加入显式开始/结束、交易日期、业务单号等规则

如果你愿意，我下一步可以继续帮你补一版：

1. **接入真实 Qwen API 的完整 `QwenActionExtractor`**
2. **带 JSON 修复、重试、结构化输出校验的版本**
3. **增加反馈接口 `/api/feedback` 的完整闭环版本**

