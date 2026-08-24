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

