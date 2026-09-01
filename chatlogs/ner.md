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


---
🙋**user**:
---
```
好的。其一帮我补上JSON 修复、重试、结构化输出校验, 其二给我补上 /api/feedback. 要求feedback把记录落盘到 /data/feedback.db
```

---
🤖**assistant**:
---

下面给你补齐两块能力：

1. **LLM 输出 JSON 修复、重试、结构化输出校验**
2. **新增 `/api/feedback`，并将反馈单独落盘到 `data/feedback.db`**

你可以把下面的内容理解为：  
**在上一版代码基础上做增量补丁。**

---

# 一、目录结构更新

现在建议项目变成这样：

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
    ├── json_utils.py
    ├── parsing.py
    ├── feedback_store.py
    ├── service.py
    └── api.py
```

其中：

- `src/json_utils.py`：JSON 修复
- `src/parsing.py`：LLM 输出结构化校验
- `src/feedback_store.py`：feedback 单独 SQLite 存储
- `src/llm.py`：接入真实 Qwen、重试、修复、解析
- `data/app.db`：交易对话状态主库
- `data/feedback.db`：反馈库

---

# 二、requirements.txt

增加 `requests`：

```txt
fastapi
uvicorn[standard]
pydantic>=2
requests
```

---

# 三、src/config.py

这个文件需要替换成下面这个版本。

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 主业务数据库：session / message / trade_draft / draft_event
DB_PATH = DATA_DIR / "app.db"

# 反馈数据库：feedback
FEEDBACK_DB_PATH = DATA_DIR / "feedback.db"

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

# mock / qwen
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

# Qwen / OpenAI-compatible API
QWEN_API_URL = os.getenv(
    "QWEN_API_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


# 如果你的 Qwen 接口支持 response_format=json_object，可以打开
QWEN_USE_RESPONSE_FORMAT = _env_bool("QWEN_USE_RESPONSE_FORMAT", False)
```

---

# 四、src/models.py

这里在上一版基础上增加 Feedback 相关模型。  
你可以整体替换 `src/models.py`。

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


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
    LLM / ActionExtractor 输出。
    """
    actions: List[Action] = Field(default_factory=list)
    clarify_question: Optional[str] = None


class SlotState(BaseModel):
    """
    单个字段状态。
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


# ----------------------------
# Feedback
# ----------------------------

class FeedbackType(str, Enum):
    EXTRACTION_ERROR = "extraction_error"
    STATE_ERROR = "state_error"
    UI_CORRECTION = "ui_correction"
    COMMENT = "comment"


class FeedbackCreate(BaseModel):
    """
    创建反馈请求。
    """
    session_id: Optional[str] = None
    draft_id: Optional[str] = None
    message_id: Optional[str] = None
    event_id: Optional[str] = None

    feedback_type: FeedbackType = FeedbackType.EXTRACTION_ERROR

    # 如果反馈针对某个字段，例如 amount / price / asset_name
    field: Optional[str] = None

    # 期望值 / 实际值，可以是字符串、数字、对象
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None

    comment: Optional[str] = None
    status: str = "open"  # open / resolved / ignored

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: Optional[str]) -> str:
        value = (value or "open").lower()
        if value not in {"open", "resolved", "ignored"}:
            return "open"
        return value


class FeedbackRecord(FeedbackCreate):
    """
    落盘后的反馈记录。
    """
    feedback_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

---

# 五、src/json_utils.py

这个文件负责 **JSON 修复**。

```python
from __future__ import annotations

import json
import re
from typing import Any, List


class JsonRepairError(ValueError):
    pass


def strip_markdown_fences(text: str) -> str:
    """
    去掉 ```json ... ``` 这类 markdown 包裹。
    """
    if not text:
        return ""

    text = text.strip()

    # 去掉开头 ```json / ```JSON / ```
    text = re.sub(r"^```(?:json|JSON)?\s*", "", text)

    # 去掉结尾 ```
    text = re.sub(r"\s*```$", "", text)

    # 兜底：删除所有残留 ```
    text = text.replace("```json", "").replace("```JSON", "").replace("```", "")

    return text.strip()


def extract_outermost_json(text: str) -> str:
    """
    从一段混杂文本里，抽取最外层的 JSON 对象或数组。
    """
    if not text:
        return ""

    candidates = []

    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        end = text.rfind(end_char)

        if start != -1 and end != -1 and end > start:
            candidates.append(text[start:end + 1])

    if not candidates:
        return text

    # 返回最长的那个，通常最完整
    return max(candidates, key=len)


def remove_comments(text: str) -> str:
    """
    尽量去掉注释。
    注意：这是启发式修复，不能保证 100% 安全。
    """
    if not text:
        return ""

    # 块注释
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    # 行注释
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)

    return text


def normalize_python_literals(text: str) -> str:
    """
    将 Python 风格字面量转成 JSON。
    """
    if not text:
        return ""

    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)

    return text


def normalize_chinese_quotes(text: str) -> str:
    """
    将部分中文引号替换成 JSON 可识别的双引号。
    """
    if not text:
        return ""

    text = text.replace("“", '"')
    text = text.replace("”", '"')
    text = text.replace("‘", "'")
    text = text.replace("’", "'")

    return text


def quote_unquoted_keys(text: str) -> str:
    """
    尝试给未加引号的 key 加引号。

    例如：
    {name: "abc"} -> {"name": "abc"}
    """
    if not text:
        return ""

    return re.sub(
        r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:",
        r'\1"\2":',
        text,
    )


def remove_trailing_commas(text: str) -> str:
    """
    删除尾逗号。

    例如：
    {"a": 1,} -> {"a": 1}
    [1, 2,] -> [1, 2]
    """
    if not text:
        return ""

    return re.sub(r",\s*([}\]])", r"\1", text)


def replace_single_quotes(text: str) -> str:
    """
    最后兜底：把单引号替换成双引号。

    注意：
    这个策略比较暴力，只作为最后修复手段。
    """
    if not text:
        return ""

    return text.replace("'", '"')


def repair_json_text(text: str) -> str:
    """
    组合多种 JSON 修复策略。
    """
    if not text:
        return ""

    repaired = strip_markdown_fences(text)
    repaired = extract_outermost_json(repaired)
    repaired = remove_comments(repaired)
    repaired = normalize_chinese_quotes(repaired)
    repaired = normalize_python_literals(repaired)
    repaired = quote_unquoted_keys(repaired)
    repaired = remove_trailing_commas(repaired)

    return repaired.strip()


def _dedupe_candidates(candidates: List[str]) -> List[str]:
    seen = set()
    result = []

    for item in candidates:
        if not item:
            continue

        if item in seen:
            continue

        seen.add(item)
        result.append(item)

    return result


def robust_json_loads(text: Any) -> Any:
    """
    尽力把 LLM 输出解析成 JSON。

    支持：
    1. 标准 JSON
    2. markdown code fence
    3. 混杂文本中的 JSON 片段
    4. 尾逗号
    5. 未加引号的 key
    6. Python 字面量 True / False / None
    7. 中文引号
    8. 单引号兜底
    """
    if text is None:
        raise JsonRepairError("LLM output is empty")

    # 如果已经是 dict/list，直接返回
    if isinstance(text, (dict, list)):
        return text

    if not isinstance(text, str):
        text = str(text)

    original = text.strip()

    if not original:
        raise JsonRepairError("LLM output is empty")

    no_fences = strip_markdown_fences(original)
    extracted = extract_outermost_json(no_fences)
    repaired = repair_json_text(original)
    aggressive = replace_single_quotes(extracted or repaired)

    candidates = _dedupe_candidates(
        [
            original,
            no_fences,
            extracted,
            repaired,
            aggressive,
        ]
    )

    last_error: Exception | None = None

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception as exc:
            last_error = exc

    raise JsonRepairError(
        f"Cannot repair and parse LLM output as JSON. Last error: {last_error}"
    ) from last_error
```

---

# 六、src/parsing.py

这个文件负责：

1. 调 `json_utils` 修复 JSON
2. 用 Pydantic 做结构化校验
3. 清洗不合理的 Action

```python
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import ValidationError

from .json_utils import JsonRepairError, robust_json_loads
from .models import Action, ActionType, ActionTarget, LLMActionsResponse


class ActionParseError(ValueError):
    pass


ALLOWED_UPDATE_FIELDS = {
    "asset_name",
    "asset_code",
    "direction",
    "amount",
    "price",
}


def _wrap_payload(obj: Any) -> Dict[str, Any]:
    """
    尽量兼容模型返回格式。

    支持：
    1. [ {...}, {...} ]
    2. { "action_type": "UPDATE", ... }
    3. { "actions": [ ... ] }
    """
    if isinstance(obj, list):
        return {"actions": obj}

    if isinstance(obj, dict):
        if "actions" in obj:
            return obj

        if "action_type" in obj:
            return {"actions": [obj]}

        return obj

    raise ActionParseError(f"Unsupported LLM output type: {type(obj)}")


def _sanitize_target(target: Optional[ActionTarget]) -> Optional[ActionTarget]:
    if target is None:
        return None

    has_any_value = any(
        [
            target.draft_id,
            target.asset_name,
            target.asset_code,
            target.reference_expression,
            target.ordinal is not None,
        ]
    )

    if not has_any_value:
        return None

    return target


def _sanitize_action(action: Action) -> Optional[Action]:
    """
    对单个 Action 做清洗。
    """
    action.target = _sanitize_target(action.target)

    # CREATE 时，如果 updates 为空，但 target 里有资产名/代码，则补到 updates
    if action.action_type == ActionType.CREATE:
        updates = dict(action.updates or {})

        if action.target:
            if action.target.asset_name and not updates.get("asset_name"):
                updates["asset_name"] = action.target.asset_name

            if action.target.asset_code and not updates.get("asset_code"):
                updates["asset_code"] = action.target.asset_code

        action.updates = updates

    # UPDATE / CREATE 只允许白名单字段
    if action.updates:
        filtered_updates = {}

        for key, value in action.updates.items():
            if key not in ALLOWED_UPDATE_FIELDS:
                continue

            if value is None:
                continue

            filtered_updates[key] = value

        action.updates = filtered_updates

    # UPDATE 没有更新字段，则无意义
    if action.action_type == ActionType.UPDATE and not action.updates:
        return None

    # CREATE 如果既没有 updates，也没有 target 资产信息，则无意义
    if action.action_type == ActionType.CREATE:
        target_has_asset = bool(
            action.target
            and (
                action.target.asset_name
                or action.target.asset_code
            )
        )

        if not action.updates and not target_has_asset:
            return None

    return action


def parse_llm_actions(raw_output: Any) -> LLMActionsResponse:
    """
    将 LLM 原始输出解析并校验为 LLMActionsResponse。
    """
    try:
        data = robust_json_loads(raw_output)
    except JsonRepairError as exc:
        raise ActionParseError(f"JSON repair failed: {exc}") from exc

    payload = _wrap_payload(data)

    try:
        parsed = LLMActionsResponse.model_validate(payload)
    except ValidationError as exc:
        raise ActionParseError(f"Pydantic validation failed: {exc}") from exc

    sanitized_actions = []

    for action in parsed.actions:
        clean_action = _sanitize_action(action)
        if clean_action is not None:
            sanitized_actions.append(clean_action)

    parsed.actions = sanitized_actions

    return parsed
```

---

# 七、src/llm.py

这个文件建议整体替换。

它包含：

1. `MockActionExtractor`
2. `QwenActionExtractor`
3. Qwen API 调用
4. 重试
5. 修复式重试
6. 结构化输出校验

```python
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import requests

from . import config
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
from .parsing import ActionParseError, parse_llm_actions


logger = logging.getLogger(__name__)


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
# helpers for mock extractor
# ----------------------------

def _extract_asset_names(text: str) -> List[str]:
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

    if any(
        word in content
        for word in ["后者", "最后一笔", "最后的一笔", "第二笔", "第2笔"]
    ):
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
# Mock extractor
# ----------------------------

class MockActionExtractor(ActionExtractor):
    """
    本地规则 Mock，仅用于开发联调。
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
# Qwen API
# ----------------------------

def _post_qwen(payload: dict) -> str:
    if not config.QWEN_API_KEY:
        raise RuntimeError("QWEN_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {config.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            config.QWEN_API_URL,
            headers=headers,
            json=payload,
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"] or ""

    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code
            if exc.response is not None
            else "unknown"
        )
        body = exc.response.text if exc.response is not None else ""

        raise RuntimeError(
            f"Qwen API HTTP error: {status_code}, body: {body[:1000]}"
        ) from exc

    except Exception as exc:
        raise RuntimeError(f"Qwen API call failed: {exc}") from exc


def call_qwen_api(prompt: str) -> str:
    """
    调用 Qwen / OpenAI-compatible chat completion API。
    """
    base_payload = {
        "model": config.QWEN_MODEL,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise dialogue state tracking assistant. "
                    "You must output valid JSON only. "
                    "Do not output explanations. "
                    "Do not output markdown."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    if config.QWEN_USE_RESPONSE_FORMAT:
        payload = dict(base_payload)
        payload["response_format"] = {"type": "json_object"}

        try:
            return _post_qwen(payload)
        except RuntimeError as exc:
            # 如果服务端不支持 response_format，则降级重试一次
            if "response_format" in str(exc):
                fallback_payload = dict(base_payload)
                return _post_qwen(fallback_payload)

            raise
    else:
        return _post_qwen(base_payload)


# ----------------------------
# Qwen extractor
# ----------------------------

class QwenActionExtractor(ActionExtractor):
    """
    真实 Qwen 增量状态抽取器。

    特性：
    1. 自动重试
    2. JSON 修复
    3. Pydantic 结构化校验
    4. 解析失败时带错误信息再次请求模型修复
    5. 最终失败时降级为 NOOP + clarify
    """

    def extract(
        self,
        *,
        session: Session,
        drafts: List[TradeDraft],
        history: List[MessageRecord],
        message: IncomingMessage,
    ) -> LLMActionsResponse:
        base_prompt = build_prompt(
            session=session,
            drafts=drafts,
            history=history,
            message=message,
        )

        last_raw_output = ""
        last_error: Optional[Exception] = None

        for attempt in range(1, config.LLM_MAX_RETRIES + 1):
            current_prompt = (
                base_prompt
                if attempt == 1
                else build_repair_prompt(
                    base_prompt=base_prompt,
                    bad_output=last_raw_output,
                    error_message=str(last_error),
                )
            )

            try:
                raw_output = call_qwen_api(current_prompt)
                last_raw_output = raw_output

                parsed = parse_llm_actions(raw_output)

                logger.info(
                    "Qwen extraction succeeded, session=%s, attempt=%s, actions=%s",
                    session.session_id,
                    attempt,
                    len(parsed.actions),
                )

                return parsed

            except ActionParseError as exc:
                last_error = exc
                logger.warning(
                    "Qwen output parse failed, session=%s, attempt=%s, error=%s",
                    session.session_id,
                    attempt,
                    exc,
                )

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Qwen API call failed, session=%s, attempt=%s, error=%s",
                    session.session_id,
                    attempt,
                    exc,
                )

            if attempt < config.LLM_MAX_RETRIES:
                sleep_seconds = 0.5 * (2 ** (attempt - 1))
                time.sleep(sleep_seconds)

        logger.exception(
            "Qwen extraction failed after %s retries, session=%s",
            config.LLM_MAX_RETRIES,
            session.session_id,
        )

        # 降级：不直接 500，避免阻塞聊天流程
        return LLMActionsResponse(
            actions=[
                Action(
                    action_type=ActionType.NOOP,
                    reasoning=f"extraction failed after retries: {last_error}",
                )
            ],
            clarify_question="抱歉，系统暂时无法理解这条消息。请明确说明标的、字段和数值，例如：24长发，量改为2000。",
        )


# ----------------------------
# Prompt
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
7. 不要输出 markdown，不要输出 ```json。

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


def build_repair_prompt(
    *,
    base_prompt: str,
    bad_output: str,
    error_message: str,
) -> str:
    return f"""
你上一次输出不是合法 JSON，或不符合 Output Schema。

请你重新输出。要求：
1. 只输出最终合法 JSON。
2. 不要输出解释。
3. 不要输出 markdown。
4. 必须符合下面 Output Schema。

# Original Task
{base_prompt}

# Your Previous Bad Output
{bad_output}

# Parse Error
{error_message}

# Your Task Now
请重新输出符合 Output Schema 的合法 JSON。
""".strip()


def get_action_extractor() -> ActionExtractor:
    provider = config.LLM_PROVIDER.lower()

    if provider == "mock":
        return MockActionExtractor()

    if provider == "qwen":
        return QwenActionExtractor()

    raise ValueError(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER}")
```

---

# 八、src/feedback_store.py

这个文件专门负责 `data/feedback.db`。

```python
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, List, Optional

from .config import FEEDBACK_DB_PATH
from .models import FeedbackCreate, FeedbackRecord, FeedbackType
from .state_store import iso, new_id, parse_iso, utcnow


FEEDBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    session_id TEXT,
    draft_id TEXT,
    message_id TEXT,
    event_id TEXT,
    feedback_type TEXT NOT NULL DEFAULT 'extraction_error',
    field TEXT,
    expected_value TEXT,
    actual_value TEXT,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_session
ON feedback(session_id);

CREATE INDEX IF NOT EXISTS idx_feedback_draft
ON feedback(draft_id);

CREATE INDEX IF NOT EXISTS idx_feedback_message
ON feedback(message_id);

CREATE INDEX IF NOT EXISTS idx_feedback_status
ON feedback(status);
"""


def get_feedback_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(FEEDBACK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_feedback_db():
    conn = get_feedback_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_feedback_db() -> None:
    with get_feedback_db() as conn:
        conn.executescript(FEEDBACK_SCHEMA)


def _to_json_value(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _from_json_value(value: Optional[str]) -> Any:
    if value is None:
        return None

    try:
        return json.loads(value)
    except Exception:
        return value


def row_to_feedback(row) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=row["feedback_id"],
        session_id=row["session_id"],
        draft_id=row["draft_id"],
        message_id=row["message_id"],
        event_id=row["event_id"],
        feedback_type=FeedbackType(row["feedback_type"]),
        field=row["field"],
        expected_value=_from_json_value(row["expected_value"]),
        actual_value=_from_json_value(row["actual_value"]),
        comment=row["comment"],
        status=row["status"],
        created_at=parse_iso(row["created_at"]),
        updated_at=parse_iso(row["updated_at"]),
    )


def get_feedback(conn, feedback_id: str) -> Optional[FeedbackRecord]:
    row = conn.execute(
        "SELECT * FROM feedback WHERE feedback_id = ?",
        (feedback_id,),
    ).fetchone()

    if not row:
        return None

    return row_to_feedback(row)


def create_feedback(payload: FeedbackCreate) -> FeedbackRecord:
    feedback_id = new_id("fb")
    now = utcnow()

    with get_feedback_db() as conn:
        conn.execute(
            """
            INSERT INTO feedback (
                feedback_id,
                session_id,
                draft_id,
                message_id,
                event_id,
                feedback_type,
                field,
                expected_value,
                actual_value,
                comment,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                payload.session_id,
                payload.draft_id,
                payload.message_id,
                payload.event_id,
                payload.feedback_type.value,
                payload.field,
                _to_json_value(payload.expected_value),
                _to_json_value(payload.actual_value),
                payload.comment,
                payload.status,
                iso(now),
                iso(now),
            ),
        )

        record = get_feedback(conn, feedback_id)

        if record is None:
            raise RuntimeError("Failed to create feedback record")

        return record


def list_feedback(
    *,
    session_id: Optional[str] = None,
    draft_id: Optional[str] = None,
    message_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[FeedbackRecord]:
    clauses: List[str] = []
    params: List[Any] = []

    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)

    if draft_id:
        clauses.append("draft_id = ?")
        params.append(draft_id)

    if message_id:
        clauses.append("message_id = ?")
        params.append(message_id)

    if status:
        clauses.append("status = ?")
        params.append(status)

    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    limit = max(1, min(limit, 1000))
    params.append(limit)

    with get_feedback_db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM feedback
            {where_sql}
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [row_to_feedback(row) for row in rows]
```

---

# 九、src/api.py

这个文件建议整体替换。  
它在原有接口基础上新增 feedback 接口。

```python
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from . import feedback_store, state_store
from .config import SESSION_TIMEOUT_MINUTES
from .db import get_db
from .llm import ActionExtractor, get_action_extractor
from .models import (
    DraftEvent,
    FeedbackCreate,
    FeedbackRecord,
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        return state_store.list_drafts(conn, session_id)


@router.get("/sessions/{session_id}/events", response_model=List[DraftEvent])
def api_get_session_events(session_id: str):
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        return state_store.list_events(conn, session_id)


# ----------------------------
# Feedback
# ----------------------------

@router.post(
    "/feedback",
    response_model=FeedbackRecord,
    status_code=status.HTTP_201_CREATED,
)
def api_create_feedback(payload: FeedbackCreate):
    """
    创建一条反馈，落盘到 data/feedback.db。
    """
    return feedback_store.create_feedback(payload)


@router.get("/feedback", response_model=List[FeedbackRecord])
def api_list_feedback(
    session_id: Optional[str] = None,
    draft_id: Optional[str] = None,
    message_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
):
    """
    查询反馈列表。

    支持按：
    - session_id
    - draft_id
    - message_id
    - status_filter
    查询。
    """
    return feedback_store.list_feedback(
        session_id=session_id,
        draft_id=draft_id,
        message_id=message_id,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/sessions/{session_id}/feedback",
    response_model=List[FeedbackRecord],
)
def api_get_session_feedback(
    session_id: str,
    draft_id: Optional[str] = None,
    message_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 100,
):
    """
    查询某个 session 下的反馈。
    """
    return feedback_store.list_feedback(
        session_id=session_id,
        draft_id=draft_id,
        message_id=message_id,
        status=status_filter,
        limit=limit,
    )
```

---

# 十、main.py

这里需要在启动时初始化两个数据库。

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import router
from src.db import init_db
from src.feedback_store import init_feedback_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化主业务库
    init_db()

    # 初始化 feedback 库
    init_feedback_db()

    yield


app = FastAPI(
    title="Trade Dialogue DST",
    description="多轮交易对话状态追踪与增量 NER 服务",
    version="0.2.0",
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

# 十一、启动方式

## 1. 使用 Mock 模式

默认无需 Qwen API Key：

```bash
export LLM_PROVIDER=mock
uvicorn main:app --reload
```

---

## 2. 使用真实 Qwen 模式

```bash
export LLM_PROVIDER=qwen
export QWEN_API_KEY="你的key"
export QWEN_MODEL="qwen-plus"

# 如果你的接口支持 response_format=json_object，可以打开
export QWEN_USE_RESPONSE_FORMAT=true

uvicorn main:app --reload
```

如果你用的是自建网关或 DashScope compatible mode，也可以指定：

```bash
export QWEN_API_URL="https://your-gateway/v1/chat/completions"
```

---

# 十二、接口示例

## 1. 发送消息

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

---

## 2. 更新前者

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

---

## 3. 提交 Feedback

```bash
curl -X POST http://127.0.0.1:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_xxx",
    "draft_id": "draft_xxx",
    "message_id": "msg_xxx",
    "feedback_type": "extraction_error",
    "field": "amount",
    "expected_value": 2000,
    "actual_value": 1000,
    "comment": "用户说的是前者量加到2000，但系统没有更新成功"
  }'
```

返回类似：

```json
{
  "feedback_id": "fb_xxx",
  "session_id": "session_xxx",
  "draft_id": "draft_xxx",
  "message_id": "msg_xxx",
  "event_id": null,
  "feedback_type": "extraction_error",
  "field": "amount",
  "expected_value": 2000,
  "actual_value": 1000,
  "comment": "用户说的是前者量加到2000，但系统没有更新成功",
  "status": "open",
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:00:00Z"
}
```

---

## 4. 查询 Feedback

```bash
curl "http://127.0.0.1:8000/api/feedback?limit=20"
```

按 session 查询：

```bash
curl "http://127.0.0.1:8000/api/feedback?session_id=session_xxx"
```

按 draft 查询：

```bash
curl "http://127.0.0.1:8000/api/feedback?draft_id=draft_xxx"
```

---

## 5. 查询某个 session 的 feedback

```bash
curl "http://127.0.0.1:8000/api/sessions/session_xxx/feedback"
```

---

# 十三、这次补上的能力到底做了什么？

## 1. JSON 修复

在 `src/json_utils.py` 中处理：

- ```json 包裹
- 输出里混有解释文本
- 尾逗号
- 未加引号的 key
- 中文引号
- Python 风格 `True / False / None`
- 单引号 JSON 兜底
- 从混杂文本中提取最外层 JSON

---

## 2. 结构化输出校验

在 `src/parsing.py` 中处理：

- 用 `Pydantic` 校验 `LLMActionsResponse`
- 校验 `ActionType`
- 校验 `ActionTarget`
- 过滤非法字段
- 清洗无意义的 `UPDATE`
- 补全 `CREATE` 时 `target` 里的 `asset_name`

---

## 3. 重试机制

在 `src/llm.py` 的 `QwenActionExtractor` 中：

- 最多重试 `LLM_MAX_RETRIES`
- 默认 3 次
- 指数退避：
  - 第 1 次失败后 sleep 0.5s
  - 第 2 次失败后 sleep 1s
  - 第 3 次失败后结束

---

## 4. 修复式重试

如果不是合法 JSON：

系统会把：

```text
原始任务
上一次错误输出
解析错误原因
```

重新拼成修复 Prompt，再让模型输出一次合法 JSON。

---

## 5. 最终降级策略

如果 Qwen 多次失败，不会直接让整个接口 500，而是返回：

```json
{
  "actions": [
    {
      "action_type": "NOOP",
      "reasoning": "extraction failed after retries: ..."
    }
  ],
  "clarify_question": "抱歉，系统暂时无法理解这条消息。请明确说明标的、字段和数值，例如：24长发，量改为2000。"
}
```

这样聊天链路不会断，同时事件表里会留下 `NOOP` 和 `CLARIFY` 记录。

---

# 十四、后续你可以继续增强的地方

这套结构已经比较完整了。下一步最值得做的是：

1. **把 `/api/feedback` 的数据用于 few-shot 自动挑选**
   - 如果某个字段经常识别错
   - 可以把历史纠错样本作为 Qwen Prompt 的 few-shot

2. **增加字段级置信度阈值**
   - `confidence < 0.7` 不直接更新
   - 转为 `CLARIFY`

3. **增加成单快照表**
   - 当 `trade_draft.status == confirmed`
   - 生成 `trade_snapshot`
   - 推送下游系统

4. **增加 Feedback 状态更新接口**
   - `PATCH /api/feedback/{feedback_id}`
   - 把状态改成 `resolved` / `ignored`

如果你需要，我下一步可以继续帮你补：

1. **`PATCH /api/feedback/{feedback_id}`**
2. **基于 feedback.db 自动生成 few-shot 的服务**
3. **真实 Qwen 流式/非流式兼容版本**


---
🙋**user**:
---
```
帮我解读你给出的代码。要求：
给出一次消息处理流程, 特别标注涉及的model, 以及哪个.py文件的哪个函数
```

---
🤖**assistant**:
---

下面我按**一次消息处理流程**，从请求进入到响应返回，完整解读这份代码。

我会重点标注：

1. **当前处理到哪一步**
2. **涉及哪个 Pydantic model**
3. **发生在哪个 `.py` 文件**
4. **调用的是哪个函数**

---

# 一、整体流程总览

一次消息处理的主链路是：

```text
前端发送消息
    |
    v
FastAPI 路由接收请求
    |
    v
解析请求体为 IncomingMessage
    |
    v
进入主流程 service.process_message()
    |
    v
SessionResolver 解析/创建 session
    |
    v
消息落盘 messages
    |
    v
读取当前 session 的 trade_drafts
    |
    v
读取近期 messages 历史
    |
    v
ActionExtractor 生成 LLMActionsResponse
    |
    v
如果是 Qwen：
    调用 Qwen API -> JSON 修复 -> 结构化校验
    |
    v
逐个执行 Action
    |
    v
更新 trade_drafts
    |
    v
写入 draft_events
    |
    v
返回 ProcessResult
```

---

# 二、逐层详细流程

## 0. 服务启动阶段

服务启动时，FastAPI 会执行 `main.py`。

### 文件

`main.py`

### 函数

`lifespan(app)`

### 做了什么

启动时初始化两个 SQLite 数据库：

```python
init_db()
init_feedback_db()
```

### 涉及文件

| 文件 | 函数 | 作用 |
|---|---|---|
| `src/db.py` | `init_db()` | 初始化主业务数据库 `data/app.db` |
| `src/feedback_store.py` | `init_feedback_db()` | 初始化反馈数据库 `data/feedback.db` |

### 涉及数据表

主库 `data/app.db`：

```text
sessions
messages
trade_drafts
draft_events
```

反馈库 `data/feedback.db`：

```text
feedback
```

---

# 三、一次消息处理流程

假设前端发送：

```json
{
  "sender_id": "trader_A",
  "receiver_id": "trader_B",
  "channel": "qq",
  "content": "24长发和25诚通有量吗？"
}
```

注意这里：

> **前端没有传 `session_id`。**

---

## 1. FastAPI 接收请求

### 请求路径

```http
POST /api/messages
```

### 文件

`src/api.py`

### 函数

```python
api_process_message()
```

### 代码位置

```python
@router.post("/messages", response_model=ProcessResult)
def api_process_message(
    payload: IncomingMessage,
    resolver: SessionResolver = Depends(get_session_resolver),
    extractor: ActionExtractor = Depends(get_extractor),
):
    return process_message(
        message=payload,
        resolver=resolver,
        extractor=extractor,
    )
```

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `IncomingMessage` | FastAPI 将请求体校验为这个模型 |
| `ProcessResult` | 接口最终返回模型 |

### 涉及文件

| 文件 | 内容 |
|---|---|
| `src/api.py` | 路由入口 |
| `src/models.py` | 定义 `IncomingMessage` 和 `ProcessResult` |
| `src/session_resolver.py` | 提供 `SessionResolver` |
| `src/llm.py` | 提供 `ActionExtractor` |

---

## 2. 注入依赖

在进入 `api_process_message()` 时，FastAPI 会先解析两个依赖。

### 2.1 获取 SessionResolver

### 文件

`src/api.py`

### 函数

```python
get_session_resolver()
```

### 返回对象

```python
DefaultSessionResolver()
```

### 来自文件

`src/session_resolver.py`

### 类型

```python
SessionResolver
```

### 2.2 获取 ActionExtractor

### 文件

`src/api.py`

### 函数

```python
get_extractor()
```

### 实际调用

`src/llm.py`

### 函数

```python
get_action_extractor()
```

### 逻辑

```python
if LLM_PROVIDER == "mock":
    return MockActionExtractor()

if LLM_PROVIDER == "qwen":
    return QwenActionExtractor()
```

### 涉及文件

| 文件 | 函数 |
|---|---|
| `src/api.py` | `get_extractor()` |
| `src/llm.py` | `get_action_extractor()` |

### 可能返回对象

| 对象 | 类 |
|---|---|
| Mock 模式 | `MockActionExtractor` |
| Qwen 模式 | `QwenActionExtractor` |

---

## 3. 进入主流程

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 入参

| 参数 | 类型 | 说明 |
|---|---|---|
| `message` | `IncomingMessage` | 前端传来的原始消息 |
| `resolver` | `SessionResolver` | 会话解析器 |
| `extractor` | `ActionExtractor` | 增量动作抽取器 |

### 返回

| 类型 | 说明 |
|---|---|
| `ProcessResult` | 本次消息处理结果 |

### 涉及 Pydantic model

| Model | 文件 |
|---|---|
| `IncomingMessage` | `src/models.py` |
| `ProcessResult` | `src/models.py` |
| `Session` | `src/models.py` |
| `TradeDraft` | `src/models.py` |
| `Action` | `src/models.py` |

---

## 4. 打开数据库事务

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 关键代码

```python
with get_db() as conn:
    ...
```

### 调用文件

`src/db.py`

### 函数

```python
get_db()
```

### 作用

获取一个 SQLite 连接，进入事务上下文。

如果流程正常：

```python
conn.commit()
```

如果流程异常：

```python
conn.rollback()
```

### 涉及数据库

```text
data/app.db
```

---

## 5. SessionResolver 解析 session

这是整个流程中非常关键的一步。

因为前端不传 `session_id`，所以后端必须自己判断：

> 这条消息属于哪一次交易协商上下文？

---

### 5.1 调用 resolver.resolve()

### 文件

`src/service.py`

### 代码

```python
session = resolver.resolve(conn, message)
```

### 实际执行

`src/session_resolver.py`

### 类

```python
DefaultSessionResolver
```

### 函数

```python
resolve()
```

---

### 5.2 生成 conversation_key

`DefaultSessionResolver.resolve()` 内部首先调用：

```python
key = self.conversation_key(message)
```

### 文件

`src/session_resolver.py`

### 函数

```python
conversation_key()
```

### 规则

如果有 `group_id`：

```text
{channel}:group:{group_id}
```

如果是私聊：

```text
{channel}:private:{sorted(sender_id, receiver_id)}
```

如果没有 `receiver_id`：

```text
{channel}:private:{sender_id}
```

### 示例

```text
qq:group:8899
qq:private:trader_A:trader_B
```

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `IncomingMessage` | 提供 `sender_id`、`receiver_id`、`group_id`、`channel` |

---

### 5.3 查找活跃 session

### 文件

`src/session_resolver.py`

### 函数

```python
DefaultSessionResolver.resolve()
```

### 内部调用

`src/state_store.py`

### 函数

```python
find_active_session()
```

### 逻辑

根据：

```text
conversation_key
```

以及：

```text
SESSION_TIMEOUT_MINUTES
```

查找最近是否有活跃会话。

### 涉及数据表

```text
sessions
```

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `Session` | 查询到活跃会话时返回 |

---

### 5.4 如果没有活跃 session，则创建新 session

### 文件

`src/session_resolver.py`

### 函数

```python
DefaultSessionResolver.resolve()
```

### 内部调用

`src/state_store.py`

### 函数

```python
create_session()
```

### 逻辑

生成：

```text
session_id
```

写入：

```text
sessions
```

### 涉及函数

| 文件 | 函数 | 作用 |
|---|---|---|
| `src/state_store.py` | `new_id()` | 生成 `session_xxx` |
| `src/state_store.py` | `utcnow()` | 当前时间 |
| `src/state_store.py` | `iso()` | 时间转字符串 |
| `src/state_store.py` | `create_session()` | 插入 session |
| `src/state_store.py` | `get_session()` | 回查刚创建的 session |

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `Session` | 返回创建后的会话对象 |

---

## 6. 消息落盘

拿到 `session` 后，当前消息会被写入 `messages` 表。

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
message_id = state_store.upsert_message(
    conn,
    message=message,
    session_id=session.session_id,
)
```

### 实际执行

`src/state_store.py`

### 函数

```python
upsert_message()
```

### 逻辑

如果 `message.message_id` 为空：

```python
message_id = new_id("msg")
```

如果 `message.ts` 为空：

```python
ts = utcnow()
```

然后写入：

```text
messages
```

### 涉及数据表

```text
messages
```

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `IncomingMessage` | 原始消息输入 |
| `MessageRecord` | 数据库中消息记录对应的模型 |

### 涉及函数

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `upsert_message()` |
| `src/state_store.py` | `new_id()` |
| `src/state_store.py` | `utcnow()` |
| `src/state_store.py` | `iso()` |

---

## 7. 读取当前 session 的交易草稿

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
drafts = state_store.list_drafts(conn, session.session_id)
```

### 实际执行

`src/state_store.py`

### 函数

```python
list_drafts()
```

### 逻辑

从：

```text
trade_drafts
```

读取当前 `session_id` 下的所有交易草稿。

### 涉及数据表

```text
trade_drafts
```

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `TradeDraft` | 表示一笔交易草稿 |
| `SlotState` | 表示 `TradeDraft.slots` 中每个字段状态 |

### 涉及函数

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `list_drafts()` |
| `src/state_store.py` | `row_to_draft()` |

### 重点说明

`trade_drafts.slots_json` 会被解析成：

```python
Dict[str, SlotState]
```

例如：

```json
{
  "amount": {
    "value": 2000,
    "status": "proposed",
    "source_message_id": "msg_xxx"
  }
}
```

---

## 8. 读取近期历史消息

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
history = state_store.list_recent_messages(
    conn,
    session_id=session.session_id,
    limit=20,
)
```

### 实际执行

`src/state_store.py`

### 函数

```python
list_recent_messages()
```

### 逻辑

从 `messages` 表中读取当前 `session_id` 下最近的消息。

### 涉及数据表

```text
messages
```

### 涉及 Pydantic model

| Model | 作用 |
|---|---|
| `MessageRecord` | 历史消息记录 |

### 涉及函数

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `list_recent_messages()` |
| `src/state_store.py` | `row_to_message()` |

---

## 9. ActionExtractor 开始增量理解

现在系统已经拿到三块信息：

```text
1. 当前 session
2. 当前 drafts
3. 最近 history
4. 最新 message
```

接下来调用：

```python
llm_result = extractor.extract(...)
```

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 调用对象

```python
ActionExtractor
```

### 返回类型

| Model | 作用 |
|---|---|
| `LLMActionsResponse` | LLM 或 Mock 输出的动作结果 |

---

# 四、Mock 模式下的处理流程

如果：

```bash
LLM_PROVIDER=mock
```

则：

```python
extractor = MockActionExtractor()
```

---

## 10. MockActionExtractor.extract()

### 文件

`src/llm.py`

### 类

```python
MockActionExtractor
```

### 函数

```python
extract()
```

### 输入

| 参数 | Model |
|---|---|
| `session` | `Session` |
| `drafts` | `List[TradeDraft]` |
| `history` | `List[MessageRecord]` |
| `message` | `IncomingMessage` |

### 输出

| Model |
|---|
| `LLMActionsResponse` |

---

## 11. Mock 内部做了哪些判断？

### 11.1 抽取资产名

### 文件

`src/llm.py`

### 函数

```python
_extract_asset_names()
```

### 示例

输入：

```text
24长发和25诚通有量吗？
```

可能抽到：

```text
24长发
25诚通
```

### 11.2 判断是否已有该资产

### 文件

`src/llm.py`

### 函数

```python
_name_exists()
```

### 11.3 判断是否需要创建交易草稿

如果当前没有草稿，或者出现“另外、新、还有”等词，则生成：

```python
ActionType.CREATE
```

### 11.4 构建定位目标

### 文件

`src/llm.py`

### 函数

```python
_build_target()
```

### 会识别

```text
前者
后者
第一笔
第二笔
这笔
那笔
资产名
代码
```

### 输出模型

| Model | 作用 |
|---|---|
| `ActionTarget` | 表示模型对某笔草稿的定位线索 |

### 11.5 抽取数值字段

### 文件

`src/llm.py`

### 函数

| 函数 | 作用 |
|---|---|
| `_extract_amount()` | 抽取数量 |
| `_extract_price()` | 抽取价格 |

### 11.6 生成动作

可能生成：

```text
CREATE
UPDATE
CONFIRM
REJECT
CLARIFY
```

### 输出模型

| Model |
|---|
| `LLMActionsResponse` |

---

# 五、Qwen 模式下的处理流程

如果：

```bash
LLM_PROVIDER=qwen
```

则：

```python
extractor = QwenActionExtractor()
```

---

## 12. QwenActionExtractor.extract()

### 文件

`src/llm.py`

### 类

```python
QwenActionExtractor
```

### 函数

```python
extract()
```

### 输入

| 参数 | Model |
|---|---|
| `session` | `Session` |
| `drafts` | `List[TradeDraft]` |
| `history` | `List[MessageRecord]` |
| `message` | `IncomingMessage` |

### 输出

| Model |
|---|
| `LLMActionsResponse` |

---

## 13. 构建 Prompt

### 文件

`src/llm.py`

### 函数

```python
build_prompt()
```

### 输入

| 参数 | Model |
|---|---|
| `session` | `Session` |
| `drafts` | `List[TradeDraft]` |
| `history` | `List[MessageRecord]` |
| `message` | `IncomingMessage` |

### 输出

```text
prompt string
```

### Prompt 中包含的内容

```json
{
  "session": {
    "session_id": "...",
    "status": "..."
  },
  "current_drafts": [],
  "recent_history": [],
  "latest_message": {}
}
```

### 对应关系

| Prompt 字段 | 来源模型 |
|---|---|
| `session` | `Session` |
| `current_drafts` | `TradeDraft` |
| `recent_history` | `MessageRecord` |
| `latest_message` | `IncomingMessage` |

---

## 14. 调用 Qwen API

### 文件

`src/llm.py`

### 函数

```python
QwenActionExtractor.extract()
```

内部调用：

```python
call_qwen_api(current_prompt)
```

### 实际执行

`src/llm.py`

### 函数

```python
call_qwen_api()
```

### 内部继续调用

```python
_post_qwen()
```

### 涉及配置

来自：

`src/config.py`

| 配置 | 作用 |
|---|---|
| `QWEN_API_URL` | Qwen API 地址 |
| `QWEN_API_KEY` | API Key |
| `QWEN_MODEL` | 模型名 |
| `QWEN_TIMEOUT_SECONDS` | 超时时间 |
| `QWEN_USE_RESPONSE_FORMAT` | 是否使用 `response_format=json_object` |

### 返回

```text
LLM 原始字符串输出
```

---

## 15. JSON 修复

LLM 原始输出可能不是严格 JSON，例如：

```text
```json
{
  "actions": []
}
```
```

或者：

```text
好的，这是结果：
{"actions": []}
```

这时需要修复。

### 文件

`src/json_utils.py`

### 主函数

```python
robust_json_loads()
```

### 内部调用

| 函数 | 作用 |
|---|---|
| `strip_markdown_fences()` | 去掉 ```json |
| `extract_outermost_json()` | 从混杂文本中抽出 JSON |
| `remove_comments()` | 去除注释 |
| `normalize_chinese_quotes()` | 中文引号转普通引号 |
| `normalize_python_literals()` | `True/False/None` 转 `true/false/null` |
| `quote_unquoted_keys()` | 给无引号 key 加引号 |
| `remove_trailing_commas()` | 去掉尾逗号 |
| `replace_single_quotes()` | 单引号兜底转双引号 |

### 输出

```python
dict
```

---

## 16. 结构化校验

### 文件

`src/parsing.py`

### 函数

```python
parse_llm_actions()
```

### 内部调用

```python
robust_json_loads()
```

### 作用

把 LLM 原始输出解析成：

```python
LLMActionsResponse
```

### 涉及 Model

| Model | 作用 |
|---|---|
| `LLMActionsResponse` | 最终结构化动作结果 |
| `Action` | 单个动作 |
| `ActionTarget` | 动作目标 |
| `ActionType` | 动作类型枚举 |

---

## 17. 清洗 Action

### 文件

`src/parsing.py`

### 函数

```python
parse_llm_actions()
```

内部会调用：

```python
_sanitize_action()
_sanitize_target()
```

### 做的事情

#### 17.1 过滤空目标

如果 `ActionTarget` 没有任何有效信息，则置空。

#### 17.2 白名单字段过滤

只允许更新：

```text
asset_name
asset_code
direction
amount
price
```

#### 17.3 过滤无意义 UPDATE

如果：

```python
action_type == UPDATE
```

但是：

```python
updates == {}
```

则删除该动作。

#### 17.4 补全 CREATE

如果：

```python
action_type == CREATE
```

但是 `updates` 没有 `asset_name`，而 `target.asset_name` 有，则自动补上。

---

## 18. Qwen 重试机制

### 文件

`src/llm.py`

### 类

```python
QwenActionExtractor
```

### 函数

```python
extract()
```

### 逻辑

最多重试：

```python
config.LLM_MAX_RETRIES
```

默认 3 次。

### 每次失败后

如果不是最后一次，则指数退避：

```python
sleep_seconds = 0.5 * (2 ** (attempt - 1))
time.sleep(sleep_seconds)
```

### 如果失败原因是解析失败

下一次会调用：

```python
build_repair_prompt()
```

### 文件

`src/llm.py`

### 函数

```python
build_repair_prompt()
```

### 输入

| 参数 | 说明 |
|---|---|
| `base_prompt` | 原始任务 Prompt |
| `bad_output` | 模型上次错误输出 |
| `error_message` | 解析错误原因 |

### 作用

让模型重新输出合法 JSON。

---

## 19. Qwen 最终降级

如果重试全部失败：

### 文件

`src/llm.py`

### 类

```python
QwenActionExtractor
```

### 函数

```python
extract()
```

### 返回

```python
LLMActionsResponse(
    actions=[
        Action(
            action_type=ActionType.NOOP,
            reasoning="extraction failed after retries: ..."
        )
    ],
    clarify_question="抱歉，系统暂时无法理解这条消息..."
)
```

### 涉及 Model

| Model |
|---|
| `LLMActionsResponse` |
| `Action` |
| `ActionType` |

### 作用

避免接口直接 500，保证聊天链路不断。

---

# 六、回到主流程：执行 Actions

现在 `process_message()` 拿到了：

```python
llm_result: LLMActionsResponse
```

---

## 20. 初始化 clarify_question

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
clarify_question = llm_result.clarify_question
```

### 涉及 Model

| Model |
|---|
| `LLMActionsResponse` |

---

## 21. 遍历执行每个 Action

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
for action in llm_result.actions:
    local_clarify = apply_action(...)
```

### 调用函数

```python
apply_action()
```

### 涉及 Model

| Model | 作用 |
|---|---|
| `Action` | 当前要执行的动作 |
| `TradeDraft` | 当前 session 下的草稿列表 |
| `ActionTarget` | 动作目标 |

---

# 七、apply_action() 详细流程

### 文件

`src/service.py`

### 函数

```python
apply_action()
```

### 作用

根据一个 `Action`，实际更新数据库中的 `trade_draft`。

---

## 22. 构造定位目标

### 函数

```python
apply_action()
```

内部调用：

```python
_get_lookup_target(action)
```

### 文件

`src/service.py`

### 函数

```python
_get_lookup_target()
```

### 作用

从：

```python
action.target
```

和：

```python
action.updates
```

合并出一个用于查找草稿的 `ActionTarget`。

### 涉及 Model

| Model |
|---|
| `Action` |
| `ActionTarget` |

---

## 23. 解析目标草稿

### 函数

```python
resolve_target()
```

### 文件

`src/service.py`

### 输入

| 参数 | Model |
|---|---|
| `drafts` | `List[TradeDraft]` |
| `target` | `ActionTarget` |

### 输出

| 类型 |
|---|
| `Optional[TradeDraft]` |

### 匹配顺序

1. `target.draft_id`
2. `target.asset_name`
3. `target.asset_code`
4. `target.ordinal`
5. `target.reference_expression`

### 能处理的指代

```text
前者
后者
第一笔
第二笔
这笔
那笔
```

---

## 24. 如果 Action 是 CREATE

### 分支

```python
if action.action_type == ActionType.CREATE:
```

### 逻辑

如果目标草稿已经存在：

```python
state_store.update_draft_fields()
```

如果不存在：

```python
state_store.create_draft()
```

### 文件

`src/state_store.py`

### 函数

| 函数 | 作用 |
|---|---|
| `create_draft()` | 创建新草稿 |
| `update_draft_fields()` | 更新已有草稿字段 |

### 涉及数据表

```text
trade_drafts
draft_events
```

### 涉及 Model

| Model |
|---|
| `TradeDraft` |
| `SlotState` |
| `DraftEvent` |

---

## 25. 如果 Action 是 UPDATE

### 分支

```python
if action.action_type == ActionType.UPDATE:
```

### 逻辑

1. 查找目标草稿
2. 如果找不到，并且当前只有一笔草稿，则默认更新唯一草稿
3. 如果仍然找不到，则返回 clarify
4. 如果目标草稿已经确认，则不允许直接修改
5. 调用：

```python
state_store.update_draft_fields()
```

### 文件

`src/state_store.py`

### 函数

```python
update_draft_fields()
```

### 作用

更新字段，并写入事件。

### 涉及数据表

```text
trade_drafts
draft_events
```

### 涉及 Model

| Model | 作用 |
|---|---|
| `TradeDraft` | 被更新对象 |
| `SlotState` | 字段级状态 |
| `DraftEvent` | 状态变更事件 |

---

## 26. 如果 Action 是 CONFIRM / REJECT / CANCEL

### 分支

```python
if action.action_type in (
    ActionType.CONFIRM,
    ActionType.REJECT,
    ActionType.CANCEL,
):
```

### 逻辑

1. 查找目标草稿
2. 如果找不到，并且只有一笔草稿，则默认操作唯一草稿
3. 如果仍然找不到，则返回 clarify
4. 调用：

```python
state_store.set_draft_status()
```

### 文件

`src/state_store.py`

### 函数

```python
set_draft_status()
```

### 状态映射

| Action | Draft 状态 |
|---|---|
| `CONFIRM` | `confirmed` |
| `REJECT` | `rejected` |
| `CANCEL` | `cancelled` |

### 涉及数据表

```text
trade_drafts
draft_events
```

---

## 27. 如果 Action 是 CLARIFY

### 分支

```python
if action.action_type == ActionType.CLARIFY:
```

### 逻辑

写入事件：

```python
state_store.append_event()
```

然后返回需要反问的问题。

### 文件

`src/state_store.py`

### 函数

```python
append_event()
```

### 涉及数据表

```text
draft_events
```

---

## 28. 如果 Action 是 NOOP

### 分支

```python
if action.action_type == ActionType.NOOP:
```

### 逻辑

只写事件，不改变草稿。

### 文件

`src/state_store.py`

### 函数

```python
append_event()
```

---

# 八、执行完 Actions 后

回到：

`src/service.py`

函数：

```python
process_message()
```

---

## 29. 如果 LLM 返回了 clarify_question

### 代码

```python
if llm_result.clarify_question:
    state_store.append_event(...)
```

### 文件

`src/state_store.py`

### 函数

```python
append_event()
```

### 作用

把反问也记录到：

```text
draft_events
```

---

## 30. 刷新 session 活跃时间

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
state_store.touch_session(conn, session.session_id)
```

### 实际执行

`src/state_store.py`

### 函数

```python
touch_session()
```

### 作用

更新：

```text
sessions.updated_at
sessions.expired_at
```

### 涉及数据表

```text
sessions
```

---

## 31. 重新读取最新状态

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 代码

```python
session = state_store.get_session(conn, session.session_id)
drafts = state_store.list_drafts(conn, session.session_id)
```

### 实际执行

`src/state_store.py`

### 函数

| 函数 | 作用 |
|---|---|
| `get_session()` | 查询最新 session |
| `list_drafts()` | 查询最新 drafts |

### 涉及 Model

| Model |
|---|
| `Session` |
| `TradeDraft` |

---

## 32. 返回 ProcessResult

### 文件

`src/service.py`

### 函数

```python
process_message()
```

### 返回

```python
ProcessResult(
    session=session,
    drafts=drafts,
    actions=llm_result.actions,
    clarify_question=clarify_question,
    message_id=message_id,
)
```

### 涉及 Model

| Model | 作用 |
|---|---|
| `ProcessResult` | 最终接口返回 |
| `Session` | 当前会话 |
| `TradeDraft` | 当前草稿列表 |
| `Action` | 本次模型生成的动作 |

---

## 33. FastAPI 返回响应

### 文件

`src/api.py`

### 函数

```python
api_process_message()
```

### 返回模型

```python
ProcessResult
```

### 响应示例

```json
{
  "session": {
    "session_id": "session_xxx",
    "conversation_key": "qq:private:trader_A:trader_B",
    "channel": "qq",
    "status": "negotiating"
  },
  "drafts": [],
  "actions": [],
  "clarify_question": null,
  "message_id": "msg_xxx"
}
```

---

# 九、一次完整调用链速查表

下面是一次消息处理完整链路。

| 步骤 | 文件 | 函数 | 涉及 Model | 作用 |
|---|---|---|---|---|
| 1 | `src/api.py` | `api_process_message()` | `IncomingMessage`, `ProcessResult` | 接收请求 |
| 2 | `src/api.py` | `get_session_resolver()` | `SessionResolver` | 注入会话解析器 |
| 3 | `src/api.py` | `get_extractor()` | `ActionExtractor` | 注入动作抽取器 |
| 4 | `src/llm.py` | `get_action_extractor()` | `ActionExtractor` | 根据配置返回 Mock 或 Qwen |
| 5 | `src/service.py` | `process_message()` | `IncomingMessage`, `ProcessResult` | 主流程 |
| 6 | `src/db.py` | `get_db()` | 无 | 打开 SQLite 事务 |
| 7 | `src/session_resolver.py` | `DefaultSessionResolver.resolve()` | `IncomingMessage`, `Session` | 解析/创建 session |
| 8 | `src/session_resolver.py` | `conversation_key()` | `IncomingMessage` | 生成会话键 |
| 9 | `src/state_store.py` | `find_active_session()` | `Session` | 查找活跃 session |
| 10 | `src/state_store.py` | `create_session()` | `Session` | 创建新 session |
| 11 | `src/state_store.py` | `upsert_message()` | `IncomingMessage`, `MessageRecord` | 消息落盘 |
| 12 | `src/state_store.py` | `list_drafts()` | `TradeDraft`, `SlotState` | 读取当前草稿 |
| 13 | `src/state_store.py` | `list_recent_messages()` | `MessageRecord` | 读取历史消息 |
| 14 | `src/llm.py` | `ActionExtractor.extract()` | `LLMActionsResponse` | 生成增量动作 |
| 15 | `src/llm.py` | `MockActionExtractor.extract()` | `Action`, `ActionTarget`, `LLMActionsResponse` | Mock 规则抽取 |
| 16 | `src/llm.py` | `QwenActionExtractor.extract()` | `Action`, `LLMActionsResponse` | Qwen 抽取 |
| 17 | `src/llm.py` | `build_prompt()` | `Session`, `TradeDraft`, `MessageRecord`, `IncomingMessage` | 构造 Prompt |
| 18 | `src/llm.py` | `call_qwen_api()` | 无 | 调用 Qwen |
| 19 | `src/json_utils.py` | `robust_json_loads()` | 无 | JSON 修复和解析 |
| 20 | `src/parsing.py` | `parse_llm_actions()` | `LLMActionsResponse`, `Action`, `ActionTarget` | 结构化校验 |
| 21 | `src/service.py` | `apply_action()` | `Action`, `TradeDraft` | 执行动作 |
| 22 | `src/service.py` | `resolve_target()` | `TradeDraft`, `ActionTarget` | 定位目标草稿 |
| 23 | `src/state_store.py` | `create_draft()` | `TradeDraft`, `SlotState`, `DraftEvent` | 创建草稿 |
| 24 | `src/state_store.py` | `update_draft_fields()` | `TradeDraft`, `SlotState`, `DraftEvent` | 更新草稿字段 |
| 25 | `src/state_store.py` | `set_draft_status()` | `TradeDraft`, `DraftEvent` | 更新草稿状态 |
| 26 | `src/state_store.py` | `append_event()` | `DraftEvent` | 写事件 |
| 27 | `src/state_store.py` | `touch_session()` | `Session` | 刷新 session 活跃时间 |
| 28 | `src/service.py` | `process_message()` | `ProcessResult` | 返回最终结果 |

---

# 十、核心 Model 在流程中的位置

## 1. IncomingMessage

### 定义位置

`src/models.py`

### 作用

前端请求体。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/api.py` | `api_process_message()` |
| `src/service.py` | `process_message()` |
| `src/session_resolver.py` | `resolve()` |
| `src/state_store.py` | `upsert_message()` |
| `src/llm.py` | `extract()` |

---

## 2. Session

### 定义位置

`src/models.py`

### 作用

表示一次交易协商上下文。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/session_resolver.py` | `resolve()` |
| `src/state_store.py` | `create_session()` |
| `src/state_store.py` | `find_active_session()` |
| `src/service.py` | `process_message()` |
| `src/llm.py` | `build_prompt()` |

---

## 3. MessageRecord

### 定义位置

`src/models.py`

### 作用

表示已经落盘的消息。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `upsert_message()` |
| `src/state_store.py` | `list_recent_messages()` |
| `src/llm.py` | `extract()` |
| `src/llm.py` | `build_prompt()` |

---

## 4. TradeDraft

### 定义位置

`src/models.py`

### 作用

表示一笔交易草稿。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `list_drafts()` |
| `src/state_store.py` | `create_draft()` |
| `src/state_store.py` | `update_draft_fields()` |
| `src/service.py` | `apply_action()` |
| `src/service.py` | `resolve_target()` |
| `src/llm.py` | `build_prompt()` |

---

## 5. SlotState

### 定义位置

`src/models.py`

### 作用

表示交易草稿中某个字段的状态。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `row_to_draft()` |
| `src/state_store.py` | `create_draft()` |
| `src/state_store.py` | `update_draft_fields()` |

---

## 6. ActionTarget

### 定义位置

`src/models.py`

### 作用

表示模型如何定位某笔交易草稿。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/llm.py` | `_build_target()` |
| `src/parsing.py` | `_sanitize_target()` |
| `src/service.py` | `_get_lookup_target()` |
| `src/service.py` | `resolve_target()` |

---

## 7. Action

### 定义位置

`src/models.py`

### 作用

表示一次增量操作。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/llm.py` | `MockActionExtractor.extract()` |
| `src/llm.py` | `QwenActionExtractor.extract()` |
| `src/parsing.py` | `_sanitize_action()` |
| `src/service.py` | `apply_action()` |

---

## 8. LLMActionsResponse

### 定义位置

`src/models.py`

### 作用

表示模型最终输出的一组动作。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/llm.py` | `extract()` |
| `src/parsing.py` | `parse_llm_actions()` |
| `src/service.py` | `process_message()` |

---

## 9. DraftEvent

### 定义位置

`src/models.py`

### 作用

表示状态变化审计记录。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/state_store.py` | `append_event()` |
| `src/state_store.py` | `row_to_event()` |
| `src/api.py` | `api_get_session_events()` |

---

## 10. ProcessResult

### 定义位置

`src/models.py`

### 作用

接口最终返回。

### 出现在

| 文件 | 函数 |
|---|---|
| `src/api.py` | `api_process_message()` |
| `src/service.py` | `process_message()` |

---

# 十一、用一个具体例子走一遍

输入：

```json
{
  "sender_id": "trader_A",
  "receiver_id": "trader_B",
  "channel": "qq",
  "content": "24长发和25诚通有量吗？"
}
```

---

## 第一步：API 接收

`src/api.py`

```python
api_process_message()
```

解析为：

```python
IncomingMessage
```

---

## 第二步：进入主流程

`src/service.py`

```python
process_message()
```

---

## 第三步：解析 session

`src/session_resolver.py`

```python
DefaultSessionResolver.resolve()
```

生成：

```text
conversation_key = qq:private:trader_A:trader_B
```

---

## 第四步：查找/创建 session

`src/state_store.py`

```python
find_active_session()
create_session()
```

返回：

```python
Session
```

---

## 第五步：消息落盘

`src/state_store.py`

```python
upsert_message()
```

写入：

```text
messages
```

---

## 第六步：读取状态

`src/state_store.py`

```python
list_drafts()
list_recent_messages()
```

得到：

```python
drafts: List[TradeDraft]
history: List[MessageRecord]
```

---

## 第七步：模型抽取动作

如果是 Mock：

`src/llm.py`

```python
MockActionExtractor.extract()
```

如果是 Qwen：

`src/llm.py`

```python
QwenActionExtractor.extract()
```

输出：

```python
LLMActionsResponse
```

---

## 第八步：Qwen 模式下修复和校验

如果是 Qwen：

`src/json_utils.py`

```python
robust_json_loads()
```

`src/parsing.py`

```python
parse_llm_actions()
```

输出：

```python
LLMActionsResponse
```

---

## 第九步：执行动作

`src/service.py`

```python
apply_action()
```

可能调用：

`src/state_store.py`

```python
create_draft()
update_draft_fields()
set_draft_status()
append_event()
```

---

## 第十步：返回结果

`src/service.py`

```python
process_message()
```

返回：

```python
ProcessResult
```

---

# 十二、Feedback 流程是独立的

这次补上的 `/api/feedback` 不参与消息主流程。

它是一个独立链路。

---

## 1. 创建 Feedback

### 请求路径

```http
POST /api/feedback
```

### 文件

`src/api.py`

### 函数

```python
api_create_feedback()
```

### 请求模型

```python
FeedbackCreate
```

### 返回模型

```python
FeedbackRecord
```

---

## 2. 落盘到 feedback.db

### 文件

`src/feedback_store.py`

### 函数

```python
create_feedback()
```

### 数据库

```text
data/feedback.db
```

### 表

```text
feedback
```

---

## 3. 查询 Feedback

### 文件

`src/api.py`

### 函数

```python
api_list_feedback()
```

或者：

```python
api_get_session_feedback()
```

### 内部调用

`src/feedback_store.py`

```python
list_feedback()
```

---

# 十三、最核心的一句话总结

这套代码的核心思想是：

```text
FastAPI 接收 IncomingMessage
    -> SessionResolver 生成/复用 Session
    -> state_store 读取 Session 下的 TradeDraft 和 MessageRecord
    -> ActionExtractor 输出 LLMActionsResponse
    -> service.apply_action 根据 Action 更新 TradeDraft
    -> state_store 写入 DraftEvent
    -> 返回 ProcessResult
```

其中：

```text
Session 管上下文边界
TradeDraft 管交易实体
SlotState 管字段状态
Action 管增量变化
DraftEvent 管审计追踪
ProcessResult 管接口输出
FeedbackRecord 管人工纠错反馈
```


---
🙋**user**:
---
```
我仔细研读了你的代码，基本上能搞清楚在做什么了。那我现在需要的需求是:
把你的代码逻辑做成持续不断serve的服务, 持续执行如下:
0. 当目前session会话尚未结束时, 保持你目前的逻辑
1. 当目前session会话结束时(大概可以等价为一个新开下一个session，或者你在这里给我留好接口), 将该session下属的所有draft, 作以下处理:
   分析slots, 如果各个field对应的value都存在, 那么把所有proposed & confirmed状态都改成confirmed, 其他状态不动; 如果存在field欠缺, 那么将对应slot_status改成unknown.
2. 将所有这些draft发送给前端

总结一下, 其实就是在持续执行: 新开一个session时，要结算上一个session, 将其内部的所有draft的所有slots尘埃落定, proposed&confirmed都确认为confirmed, 欠缺的改成unknown, 其他不动.
然后执行api_get_session_drafts(last_session_id), 大概是这样吧?
```

---
🤖**assistant**:
---

你的理解**基本是对的**，但我建议把这件事抽象成一个明确的动作：

> **结算 / Settle Session**

也就是说，不是简单“新开一个 session 后，再调用 `api_get_session_drafts(last_session_id)`”。

更合理的设计是：

```text
当旧 session 结束时：
    1. 先结算旧 session 下所有 trade_draft
    2. 把 proposed / confirmed 的 slot 落定为 confirmed
    3. 把缺失字段的 slot 标记为 unknown
    4. 返回结算后的 drafts 给前端
    5. 再开启新 session
```

如果前端主动结束，也可以调用：

```http
POST /api/sessions/{session_id}/settle
```

如果是“超时后来了下一条消息，所以新开下一个 session”，则在 `SessionResolver` 里自动结算上一个 session。

---

# 一、先回答你的问题

你说：

> 总结一下，其实就是在持续执行：新开一个 session 时，要结算上一个 session，将其内部的所有 draft 的所有 slots 尘埃落定，proposed & confirmed 都确认为 confirmed，欠缺的改成 unknown，其他不动。然后执行 api_get_session_drafts(last_session_id)，大概是这样吧？

我的建议是：

## 1. “持续不断 serve 的服务”

FastAPI + Uvicorn 本身就是持续运行的服务。

你不需要额外写一个死循环来处理消息。

```bash
uvicorn main:app --reload
```

或者生产环境：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

它会持续接收请求。

---

## 2. “新开一个 session 时结算上一个 session”

这个逻辑建议放在：

```text
SessionResolver
```

里。

也就是：

```text
当前消息进来
    |
    v
根据会话规则判断是否还能复用当前 active session
    |
    +-- 如果还能复用：
    |       保持原逻辑
    |
    +-- 如果不能复用，需要新开 session：
            先找到上一个未结算 session
            settle 上一个 session
            创建新 session
            返回新 session + 已结算的旧 session drafts
```

---

## 3. “然后执行 api_get_session_drafts(last_session_id)”

可以，但不是最优。

因为 `GET /api/sessions/{session_id}/drafts` 只是查询，它不应该承担“结算”的职责。

更好的方式是：

```text
结算动作本身返回 drafts
```

即：

```http
POST /api/sessions/{session_id}/settle
```

返回：

```json
{
  "session": {},
  "drafts": []
}
```

或者在 `POST /api/messages` 的返回里直接带：

```json
{
  "session": {},
  "drafts": [],
  "actions": [],
  "message_id": "msg_xxx",
  "settled_session": {},
  "settled_drafts": []
}
```

这样前端不需要额外再请求一次。

---

# 二、这次要新增的核心概念

我们需要新增几个东西。

---

## 1. `SessionResolutionResult`

原来 `SessionResolver.resolve()` 只返回：

```python
Session
```

现在不够用了。

因为它可能同时发生两件事：

1. 创建了新 session；
2. 结算了旧 session。

所以建议返回：

```python
SessionResolutionResult
```

包含：

```python
session: Session
created: bool
settled_session: Optional[Session]
settled_drafts: List[TradeDraft]
```

---

## 2. `SessionSettleResult`

手动结算接口返回：

```python
SessionSettleResult
```

包含：

```python
session: Session
drafts: List[TradeDraft]
```

---

## 3. `settle_session()`

这是核心业务函数。

它做的事情是：

```text
找到某个 session 下所有 draft
    |
    v
检查每个 draft 的必需字段是否都有值
    |
    +-- 如果都有值：
    |       将所有 proposed / confirmed slot 改成 confirmed
    |
    +-- 如果有字段缺失：
    |       将缺失字段的 slot_status 改成 unknown
    |
    v
更新数据库
    |
    v
写入结算事件
    |
    v
将 session 标记为 settled
    |
    v
返回最新 drafts
```

---

# 三、代码修改

下面按文件给出。

---

# 四、修改 `src/models.py`

你需要新增几个模型，并且扩展 `ProcessResult`。

---

## 1. 替换原来的 `ProcessResult`

原来大概是：

```python
class ProcessResult(BaseModel):
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    clarify_question: Optional[str] = None
    message_id: str
```

替换成：

```python
class ProcessResult(BaseModel):
    """
    单次消息处理结果。
    """
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    clarify_question: Optional[str] = None
    message_id: str

    # 如果本次消息触发了新 session，并结算了上一个 session，
    # 这里会返回被结算的旧 session 以及旧 session 下的所有草稿。
    settled_session: Optional[Session] = None
    settled_drafts: List[TradeDraft] = Field(default_factory=list)
```

---

## 2. 新增 `SessionSettleResult`

可以放在 `SessionDetail` 附近：

```python
class SessionSettleResult(BaseModel):
    """
    Session 结算结果。
    """
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
```

---

## 3. 新增 `SessionResolutionResult`

```python
class SessionResolutionResult(BaseModel):
    """
    SessionResolver 的解析结果。

    如果当前消息仍然属于活跃 session，则只返回当前 session。
    如果当前消息触发了新 session，并且系统自动结算了上一个 session，
    则同时返回 settled_session 和 settled_drafts。
    """
    session: Session
    created: bool = False

    settled_session: Optional[Session] = None
    settled_drafts: List[TradeDraft] = Field(default_factory=list)
```

---

# 五、修改 `src/state_store.py`

这里新增结算逻辑。

你可以在 `src/state_store.py` 末尾追加下面代码。

---

## 1. 定义结算必需字段

```python
# 结算时需要检查的字段。
# 你可以根据业务改这里。
# 例如你只要求 asset_name / amount / price 必填，可以改成：
# REQUIRED_SETTLE_FIELDS = ("asset_name", "amount", "price")
REQUIRED_SETTLE_FIELDS = (
    "asset_name",
    "asset_code",
    "direction",
    "amount",
    "price",
)

# 如果你不想结算已被拒绝 / 取消的 draft，可以改成：
# SETTLE_SKIP_DRAFT_STATUSES = {"rejected", "cancelled"}
SETTLE_SKIP_DRAFT_STATUSES = set()
```

---

## 2. 查找最近一个未结算 session

```python
def find_latest_unsettled_session(
    conn,
    conversation_key: str,
) -> Optional[Session]:
    """
    查找当前会话键下最近一个尚未结算的 session。

    用于：
    1. 当前消息需要新开 session；
    2. 但上一个 session 还没有显式结算；
    3. 此时先结算上一个 session。
    """
    row = conn.execute(
        """
        SELECT *
        FROM sessions
        WHERE conversation_key = ?
          AND status NOT IN ('settled', 'closed')
        ORDER BY updated_at DESC, rowid DESC
        LIMIT 1
        """,
        (conversation_key,),
    ).fetchone()

    if not row:
        return None

    return row_to_session(row)
```

---

## 3. 判断字段是否缺失

```python
def _is_missing_value(value: Any) -> bool:
    """
    判断某个字段值是否缺失。

    当前规则：
    1. None 算缺失；
    2. 空字符串算缺失；
    3. 0 不算缺失；
    4. False 不算缺失。
    """
    if value is None:
        return True

    if isinstance(value, str) and not value.strip():
        return True

    return False
```

---

## 4. 结算单个 draft

```python
def settle_draft(
    conn,
    draft_id: str,
    message_id: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> Optional[TradeDraft]:
    """
    结算单个 trade_draft。

    规则：
    1. 检查 REQUIRED_SETTLE_FIELDS 是否都有值；
    2. 如果所有字段都有值：
       - 将所有 proposed / confirmed 状态的 slot 改成 confirmed；
       - 其他状态不动；
    3. 如果存在字段缺失：
       - 将缺失字段的 slot_status 改成 unknown；
       - 其他已有字段状态不动。
    """
    row = conn.execute(
        "SELECT * FROM trade_drafts WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()

    if not row:
        return None

    slots = json.loads(row["slots_json"] or "{}")
    now = utcnow()

    missing_fields = []

    for field in REQUIRED_SETTLE_FIELDS:
        value = row[field]
        if _is_missing_value(value):
            missing_fields.append(field)

    if missing_fields:
        # 存在字段缺失：
        # 只把缺失字段的 slot 标成 unknown。
        for field in missing_fields:
            slots[field] = SlotState(
                value=None,
                status="unknown",
                source_message_id=message_id,
                updated_at=now,
            ).model_dump(mode="json")

        settle_result = "incomplete"

    else:
        # 所有字段都有值：
        # 先确保每个必需字段都有 slot。
        for field in REQUIRED_SETTLE_FIELDS:
            if field not in slots:
                slots[field] = SlotState(
                    value=row[field],
                    status="confirmed",
                    source_message_id=message_id,
                    updated_at=now,
                ).model_dump(mode="json")

        # 将所有 proposed / confirmed 的 slot 改成 confirmed。
        # 其他状态，例如 rejected / ambiguous / unknown，不动。
        for slot in slots.values():
            if slot.get("status") in {"proposed", "confirmed"}:
                slot["status"] = "confirmed"
                slot["updated_at"] = now.isoformat()

        settle_result = "complete"

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

    append_event(
        conn,
        session_id=row["session_id"],
        draft_id=draft_id,
        message_id=message_id,
        action_type="SETTLE",
        field=None,
        old_value=None,
        new_value={
            "settle_result": settle_result,
            "missing_fields": missing_fields,
        },
        reasoning=reasoning,
    )

    return get_draft(conn, draft_id)
```

---

## 5. 结算整个 session

```python
def settle_session(
    conn,
    session_id: str,
    message_id: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> tuple[Session, List[TradeDraft]]:
    """
    结算整个 session。

    流程：
    1. 查找该 session 下所有 draft；
    2. 逐个 settle_draft；
    3. 将 session.status 标记为 settled；
    4. 写入 SETTLE 事件；
    5. 返回最新的 session 和 drafts。
    """
    session = get_session(conn, session_id)

    if session is None:
        raise ValueError(f"session not found: {session_id}")

    # 如果已经结算过，则幂等返回。
    if session.status in {"settled", "closed"}:
        return session, list_drafts(conn, session_id)

    drafts = list_drafts(conn, session_id)

    for draft in drafts:
        if draft.status in SETTLE_SKIP_DRAFT_STATUSES:
            continue

        settle_draft(
            conn,
            draft_id=draft.draft_id,
            message_id=message_id,
            reasoning=reasoning,
        )

    now = utcnow()

    conn.execute(
        """
        UPDATE sessions
        SET status = 'settled', updated_at = ?
        WHERE session_id = ?
        """,
        (
            iso(now),
            session_id,
        ),
    )

    append_event(
        conn,
        session_id=session_id,
        draft_id=None,
        message_id=message_id,
        action_type="SETTLE",
        field=None,
        old_value=session.status,
        new_value="settled",
        reasoning=reasoning,
    )

    settled_session = get_session(conn, session_id)
    assert settled_session is not None

    settled_drafts = list_drafts(conn, session_id)

    return settled_session, settled_drafts
```

---

# 六、替换 `src/session_resolver.py`

这个文件建议整体替换。

核心变化是：

```text
resolve() 不再只返回 Session，
而是返回 SessionResolutionResult。
```

新文件内容：

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .models import IncomingMessage, SessionResolutionResult


class SessionResolver(ABC):
    """
    SessionResolver 接口。

    职责：
    1. 判断当前消息属于哪个会话；
    2. 如果当前会话仍活跃，则复用；
    3. 如果需要新开一个会话，则先结算上一个未结算会话；
    4. 创建新的会话。
    """

    @abstractmethod
    def conversation_key(self, message: IncomingMessage) -> str:
        raise NotImplementedError

    @abstractmethod
    def resolve(
        self,
        conn,
        message: IncomingMessage,
    ) -> SessionResolutionResult:
        raise NotImplementedError


class DefaultSessionResolver(SessionResolver):
    """
    默认规则：

    1. 如果有 group_id，则按群会话切分；
    2. 如果是私聊，则按 sender_id + receiver_id 切分；
    3. 在 SESSION_TIMEOUT_MINUTES 内有活跃 session，则复用；
    4. 否则创建新 session；
    5. 创建新 session 前，如果存在上一个未结算 session，则先结算它。
    """

    def conversation_key(self, message: IncomingMessage) -> str:
        if message.group_id:
            return f"{message.channel}:group:{message.group_id}"

        if message.receiver_id:
            a, b = sorted([message.sender_id, message.receiver_id])
            return f"{message.channel}:private:{a}:{b}"

        return f"{message.channel}:private:{message.sender_id}"

    def resolve(
        self,
        conn,
        message: IncomingMessage,
    ) -> SessionResolutionResult:
        key = self.conversation_key(message)

        # 1. 优先复用活跃 session
        active_session = state_store.find_active_session(
            conn,
            conversation_key=key,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        if active_session:
            return SessionResolutionResult(
                session=active_session,
                created=False,
                settled_session=None,
                settled_drafts=[],
            )

        # 2. 如果没有活跃 session，准备新开一个 session。
        # 在开新 session 之前，先查找上一个未结算 session。
        settled_session = None
        settled_drafts = []

        previous_session = state_store.find_latest_unsettled_session(
            conn,
            conversation_key=key,
        )

        if previous_session:
            settled_session, settled_drafts = state_store.settle_session(
                conn,
                session_id=previous_session.session_id,
                message_id=message.message_id,
                reasoning="settle previous session before opening new session",
            )

        # 3. 创建新 session
        new_session = state_store.create_session(
            conn,
            conversation_key=key,
            channel=message.channel,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        return SessionResolutionResult(
            session=new_session,
            created=True,
            settled_session=settled_session,
            settled_drafts=settled_drafts,
        )
```

---

# 七、修改 `src/service.py`

你原来的 `service.py` 里面大部分逻辑可以不动。

主要修改 `process_message()`。

---

## 替换 `process_message()`

```python
def process_message(
    message: IncomingMessage,
    resolver: SessionResolver,
    extractor: ActionExtractor,
) -> ProcessResult:
    # 如果前端没有传 message_id，
    # 我们提前生成一个，方便结算事件关联到这条触发消息。
    if not message.message_id:
        message = message.model_copy(
            update={
                "message_id": state_store.new_id("msg")
            }
        )

    with get_db() as conn:
        # 1. 解析 session。
        # 如果这里触发了新 session，
        # resolver 会先结算上一个未结算 session。
        resolution = resolver.resolve(conn, message)

        session = resolution.session

        # 2. 当前消息落盘到新/当前 session 下。
        message_id = state_store.upsert_message(
            conn,
            message=message,
            session_id=session.session_id,
        )

        # 3. 读取当前 session 状态。
        drafts = state_store.list_drafts(conn, session.session_id)
        history = state_store.list_recent_messages(
            conn,
            session_id=session.session_id,
            limit=20,
        )

        # 4. 调用 LLM / Mock extractor，生成增量 Actions。
        llm_result = extractor.extract(
            session=session,
            drafts=drafts,
            history=history,
            message=message,
        )

        clarify_question = llm_result.clarify_question

        # 5. 逐个执行 Actions。
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

            # 如果发生 CREATE，后续 action 需要看到最新 drafts。
            drafts = state_store.list_drafts(conn, session.session_id)

        # 6. 如果 LLM 返回了 clarify_question，也写入事件。
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

        # 7. 刷新当前 session 活跃时间。
        state_store.touch_session(conn, session.session_id)

        # 8. 重新读取最新状态。
        session = state_store.get_session(conn, session.session_id)
        assert session is not None

        drafts = state_store.list_drafts(conn, session.session_id)

        return ProcessResult(
            session=session,
            drafts=drafts,
            actions=llm_result.actions,
            clarify_question=clarify_question,
            message_id=message_id,
            settled_session=resolution.settled_session,
            settled_drafts=resolution.settled_drafts,
        )
```

---

# 八、修改 `src/api.py`

这里主要做三件事：

1. 让 `/api/messages` 返回 `settled_session` 和 `settled_drafts`；
2. 新增手动结算接口；
3. 调整 `/session-resolver/resolve`。

---

## 1. 增加 import

在 `src/api.py` 顶部导入新增模型：

```python
from .models import (
    DraftEvent,
    FeedbackCreate,
    FeedbackRecord,
    IncomingMessage,
    ProcessResult,
    SessionDetail,
    SessionResolutionResult,
    SessionSettleResult,
    TradeDraft,
)
```

如果你原来已经有 `SessionResolveResult`，可以先保留，但下面会用新的 `SessionResolutionResult`。

---

## 2. 替换 `/session-resolver/resolve`

原来的接口可以改成：

```python
@router.post(
    "/session-resolver/resolve",
    response_model=SessionResolutionResult,
)
def api_resolve_session(
    payload: IncomingMessage,
    resolver: SessionResolver = Depends(get_session_resolver),
):
    """
    SessionResolver 调试接口。

    注意：
    这个接口会真实执行 resolver 逻辑。
    如果当前消息触发新 session，并且上一个 session 尚未结算，
    它也会结算上一个 session。
    """
    with get_db() as conn:
        return resolver.resolve(conn, payload)
```

---

## 3. 新增手动结算接口

```python
@router.post(
    "/sessions/{session_id}/settle",
    response_model=SessionSettleResult,
)
def api_settle_session(
    session_id: str,
    reason: Optional[str] = None,
):
    """
    手动结算一个 session。

    适用场景：
    1. 前端点击“结束会话”；
    2. 业务系统判断本次交易沟通结束；
    3. 后台任务发现 session 已过期；
    4. 需要把当前 session 下所有 draft 的 slots 落定。

    结算规则：
    1. 如果所有必需字段都有值：
       - 将所有 proposed / confirmed 状态的 slot 改成 confirmed；
       - 其他状态不动；
    2. 如果存在字段缺失：
       - 将缺失字段的 slot_status 改成 unknown；
       - 其他字段状态不动。
    """
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        settled_session, settled_drafts = state_store.settle_session(
            conn,
            session_id=session_id,
            message_id=None,
            reasoning=reason or "manual settle",
        )

        return SessionSettleResult(
            session=settled_session,
            drafts=settled_drafts,
        )
```

---

## 4. 原来的 `/api/sessions/{session_id}/drafts` 可以保留

你原来的：

```python
@router.get("/sessions/{session_id}/drafts", response_model=List[TradeDraft])
def api_get_session_drafts(session_id: str):
    ...
```

可以继续保留。

它可以用于：

```text
前端主动查询某个已结算 session 的 drafts
```

但不建议让它承担结算职责。

---

# 九、可选：增加后台超时结算任务

你现在有两种结算触发方式：

## 方式 1：新消息触发

如果旧 session 已经超时，但没有新消息进来，它不会立刻结算。

直到下一条消息到来，`SessionResolver` 发现需要新开 session，才会结算旧 session。

这符合你说的：

> 新开一个 session 时，结算上一个 session。

---

## 方式 2：后台定时扫描

如果你希望：

> 一旦 session 超时，即使没有新消息，也立刻结算。

那需要后台任务。

可以在 `main.py` 里加一个定时循环。

---

## 替换 `main.py`

```python
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src import state_store
from src.api import router
from src.db import get_db, init_db
from src.feedback_store import init_feedback_db


logger = logging.getLogger(__name__)


def _settle_expired_sessions_sync() -> None:
    """
    同步扫描已经过期但尚未结算的 session，并结算它们。
    """
    now = state_store.utcnow()

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT session_id
            FROM sessions
            WHERE status NOT IN ('settled', 'closed')
              AND expired_at IS NOT NULL
              AND expired_at <= ?
            """,
            (now.isoformat(),),
        ).fetchall()

        for row in rows:
            session_id = row["session_id"]

            try:
                state_store.settle_session(
                    conn,
                    session_id=session_id,
                    message_id=None,
                    reasoning="session expired",
                )

                logger.info(
                    "Settled expired session: %s",
                    session_id,
                )

            except Exception:
                logger.exception(
                    "Failed to settle expired session: %s",
                    session_id,
                )


async def settle_expired_sessions_loop() -> None:
    """
    后台循环：
    每隔一段时间检查一次过期 session。
    """
    while True:
        await asyncio.sleep(30)

        try:
            await asyncio.to_thread(_settle_expired_sessions_sync)
        except Exception:
            logger.exception("settle_expired_sessions_loop failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化主业务库
    init_db()

    # 初始化 feedback 库
    init_feedback_db()

    # 启动后台过期结算任务
    background_task = asyncio.create_task(
        settle_expired_sessions_loop()
    )

    yield

    # 关闭后台任务
    background_task.cancel()

    try:
        await background_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Trade Dialogue DST",
    description="多轮交易对话状态追踪与增量 NER 服务",
    version="0.3.0",
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

# 十、最终接口形态

完成上述修改后，你的服务有这些能力。

---

## 1. 持续接收消息

```http
POST /api/messages
```

如果当前 session 还没结束：

```json
{
  "session": {
    "session_id": "session_current"
  },
  "drafts": [],
  "actions": [],
  "message_id": "msg_xxx",
  "settled_session": null,
  "settled_drafts": []
}
```

如果这条消息触发了新 session，并结算了旧 session：

```json
{
  "session": {
    "session_id": "session_new"
  },
  "drafts": [],
  "actions": [],
  "message_id": "msg_xxx",
  "settled_session": {
    "session_id": "session_old",
    "status": "settled"
  },
  "settled_drafts": [
    {
      "draft_id": "draft_1",
      "session_id": "session_old",
      "asset_name": "24长发",
      "amount": 2000,
      "price": 100.85,
      "slots": {
        "asset_name": {
          "value": "24长发",
          "status": "confirmed"
        },
        "amount": {
          "value": 2000,
          "status": "confirmed"
        },
        "price": {
          "value": 100.85,
          "status": "confirmed"
        },
        "asset_code": {
          "value": null,
          "status": "unknown"
        },
        "direction": {
          "value": null,
          "status": "unknown"
        }
      }
    }
  ]
}
```

---

## 2. 手动结束 / 结算某个 session

```http
POST /api/sessions/{session_id}/settle?reason=user_close
```

返回：

```json
{
  "session": {
    "session_id": "session_old",
    "status": "settled"
  },
  "drafts": [
    {
      "draft_id": "draft_1",
      "slots": {
        "asset_name": {
          "value": "24长发",
          "status": "confirmed"
        },
        "amount": {
          "value": 2000,
          "status": "confirmed"
        },
        "price": {
          "value": 100.85,
          "status": "confirmed"
        },
        "asset_code": {
          "value": null,
          "status": "unknown"
        },
        "direction": {
          "value": null,
          "status": "unknown"
        }
      }
    }
  ]
}
```

---

## 3. 查询某个 session 的 drafts

```http
GET /api/sessions/{session_id}/drafts
```

这个接口现在更适合做“查询”。

---

# 十一、你这个需求的最终执行链路

现在整个系统会变成这样：

```text
消息持续进入
    |
    v
FastAPI /api/messages
    |
    v
SessionResolver.resolve()
    |
    +-- 当前 session 仍活跃
    |       |
    |       v
    |   保持原有增量更新逻辑
    |
    +-- 当前 session 已结束 / 超时 / 需要新开
            |
            v
        查找上一个未结算 session
            |
            v
        settle_session(last_session_id)
            |
            v
        遍历 last_session 下所有 draft
            |
            v
        检查 slots / fields
            |
            +-- 所有字段都有值
            |       |
            |       v
            |   proposed / confirmed -> confirmed
            |
            +-- 存在字段缺失
                    |
                    v
                missing field slot_status -> unknown
            |
            v
        返回 settled_session + settled_drafts
            |
            v
        创建新 session
            |
            v
        继续处理当前新消息
```

---

# 十二、关于你说的“然后执行 api_get_session_drafts(last_session_id)”

我的建议是：

## 如果只是前端想拉取结果

可以：

```http
GET /api/sessions/{last_session_id}/drafts
```

但前提是：

```text
last_session_id 已经被结算过
```

否则你拿到的仍然是未落定的状态。

---

## 更好的方式

让结算接口直接返回结果：

```http
POST /api/sessions/{last_session_id}/settle
```

或者：

```http
POST /api/messages
```

返回里直接带：

```json
"settled_drafts": []
```

这样前端不需要再额外调用一次。

---

# 十三、你还需要特别注意一个业务问题

你现在说的是：

> 如果各个 field 对应的 value 都存在，那么把所有 proposed & confirmed 状态都改成 confirmed，其他状态不动。

这里有一个细节：

## `draft.status` 和 `slot.status` 不是一回事

例如一个 draft 可能：

```json
{
  "status": "rejected",
  "slots": {
    "price": {
      "value": 100.8,
      "status": "proposed"
    }
  }
}
```

如果你按字面逻辑结算，`price` 这个 `proposed` slot 也会变成 `confirmed`。

这可能不符合业务直觉。

所以我在代码里留了：

```python
SETTLE_SKIP_DRAFT_STATUSES = set()
```

如果你希望：

```text
已拒绝 / 已取消的 draft 不参与结算
```

可以改成：

```python
SETTLE_SKIP_DRAFT_STATUSES = {"rejected", "cancelled"}
```

如果你坚持：

```text
所有 draft 都结算
```

就保持：

```python
SETTLE_SKIP_DRAFT_STATUSES = set()
```

---

# 十四、总结

你的理解可以修正成下面这句话：

```text
服务持续运行。
每当需要新开一个 session 时，先结算上一个未结算 session。
结算时，将旧 session 下所有 draft 的 slots 落定：
    完整字段的 proposed / confirmed 变成 confirmed；
    缺失字段变成 unknown；
    其他状态保持不变。
结算完成后，把旧 session 和旧 drafts 返回给前端。
```

代码层面核心是：

```text
state_store.settle_session()
state_store.settle_draft()
DefaultSessionResolver.resolve()
POST /api/sessions/{session_id}/settle
ProcessResult.settled_session / settled_drafts
```

这样你的服务就从：

```text
持续增量理解消息
```

升级成了：

```text
持续增量理解消息 + 会话结束自动结算
```


---
🙋**user**:
---
```
我觉得你说的有道理，不能完全依靠新开session才触发对上一个未结算session的结算，否则当天的最后一个session永远无法得到结算了。
重新帮我考虑，该如何设计session的状态，以及对session的结算时机。我反正觉得当新开一个session时必然应该伴随着对上一个未结算session的结算，结算后session的状态应该编程closed或cancelled。
也应该有轮询：以某个频率扫描是否有状态为expired的session，如果有，结算它。
反正session的结算是纯粹的cpu work，不涉及LLM api。
```

---
🤖**assistant**:
---

你的观察非常准确：**只靠"新开 session 触发结算"会有盲区**——当天最后一个会话永远等不到下一条消息，也就永远不会被结算。

我重新设计一套**显式的 session 状态机 + 多重结算触发机制**。核心思想是：

1. **结算是纯 CPU 工作**，不依赖 LLM，可以随时安全执行；
2. **结算时机多路触发**：新消息、轮询、手动，三路兜底；
3. **结算后进入终态**，不再参与后续状态转移。

---

# 一、Session 状态机设计

## 1.1 状态定义

我建议引入 4 个状态，其中 2 个是终态：

| 状态 | 含义 | 是否终态 |
|---|---|---|
| `active` | 会话进行中，正在接收消息、更新草稿 | 否 |
| `expired` | 已超时，但尚未结算（短暂中间态） | 否 |
| `closed` | 已结算关闭（正常结束，无论字段是否齐全） | **是** |
| `cancelled` | 已取消（用户主动取消整个会话） | **是** |

## 1.2 状态转移图

```
                    ┌─────────────────┐
        create ──►  │     active      │
                    └────────┬────────┘
                             │
              timeout 检测    │    用户主动取消
                             ▼
                    ┌─────────────────┐         ┌──────────────┐
                    │     expired     │         │  cancelled   │
                    └────────┬────────┘         └──────────────┘
                             │                        ▲
                             │ settle                 │
                             ▼                        │
                    ┌─────────────────┐               │
                    │     closed      │───────────────┘
                    └─────────────────┘   （仅用户取消时走这条）
```

## 1.3 为什么引入 `expired` 中间态？

如果没有 `expired`，直接从 `active` 跳到 `closed`，会有两个问题：

1. **无法区分"刚超时"和"刚创建"**：轮询任务不知道该结算谁；
2. **无法做"超时但未结算"的审计**：出问题时不知道哪些会话是超时导致的。

引入 `expired` 后：

```text
active  ──超时检测──►  expired  ──结算──►  closed
```

每一步都有明确语义，轮询任务只需要扫 `expired`，逻辑非常干净。

## 1.4 结算后状态判定

你提到"结算后状态应该变成 `closed` 或 `cancelled`"。我建议这样区分：

| 触发方式 | 结算后状态 |
|---|---|
| 新消息开新 session 触发 | `closed` |
| 轮询超时触发 | `closed` |
| 手动调用结算接口 | `closed` |
| **用户主动取消**（说"不要了"、"取消"） | `cancelled` |

字段是否齐全**不影响** `closed` / `cancelled`，而是用 `is_complete` 字段标记：

```text
closed + is_complete=true   → 完整成单
closed + is_complete=false  → 不完整结束（有 unknown 字段）
cancelled                   → 用户主动放弃
```

这样语义更清晰：**`cancelled` 表示"用户不想要了"，`closed` 表示"会话生命周期自然结束"**。

---

# 二、结算时机：三路触发

## 2.1 触发点全景

| 触发点 | 时机 | 触发方式 | close_reason |
|---|---|---|---|
| **T1. 新消息触发** | 新消息需要开新 session 时 | `SessionResolver.resolve()` | `new_session` |
| **T2. 轮询触发** | 后台定时扫描 | `maintenance_loop` | `timeout_poll` |
| **T3. 手动触发** | 前端点击"结束会话" | `POST /sessions/{id}/settle` | `manual` |
| **T4. 用户取消** | 用户明确说"取消" | `POST /sessions/{id}/cancel` | `user_cancel` |

## 2.2 为什么需要三路？

```text
T1（新消息）：解决"会话切换"场景
T2（轮询）：  解决"当天最后一个会话"场景 ← 你提到的盲区
T3（手动）：  解决"用户显式结束"场景
T4（取消）：  解决"用户放弃"场景
```

四路兜底，确保**每个会话最终都会进入终态**。

---

# 三、数据库变更

## 3.1 `sessions` 表新增字段

在 `src/db.py` 的 `SCHEMA` 中，把 `sessions` 表改成：

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    conversation_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    close_reason TEXT,
    is_complete INTEGER,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expired_at TEXT,
    settled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_conversation
ON sessions(conversation_key, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_sessions_status
ON sessions(status, updated_at);
```

新增字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `close_reason` | TEXT | 结算原因：`new_session` / `timeout_poll` / `manual` / `user_cancel` |
| `is_complete` | INTEGER | 结算时字段是否齐全（0/1） |
| `settled_at` | TEXT | 结算时间 |

## 3.2 状态默认值改为 `active`

原来默认是 `negotiating`，现在统一改成 `active`。

---

# 四、`src/models.py` 修改

## 4.1 新增状态常量

```python
class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CloseReason(str, Enum):
    NEW_SESSION = "new_session"
    TIMEOUT_POLL = "timeout_poll"
    MANUAL = "manual"
    USER_CANCEL = "user_cancel"
```

## 4.2 更新 `Session` 模型

```python
class Session(BaseModel):
    """
    一次交易协商上下文。
    """
    session_id: str
    conversation_key: str
    channel: str
    status: str = SessionStatus.ACTIVE
    close_reason: Optional[str] = None
    is_complete: Optional[bool] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
```

---

# 五、`src/state_store.py` 新增核心函数

## 5.1 状态常量

```python
# Session 状态
SESSION_ACTIVE = "active"
SESSION_EXPIRED = "expired"
SESSION_CLOSED = "closed"
SESSION_CANCELLED = "cancelled"

# 结算原因
CLOSE_REASON_NEW_SESSION = "new_session"
CLOSE_REASON_TIMEOUT_POLL = "timeout_poll"
CLOSE_REASON_MANUAL = "manual"
CLOSE_REASON_USER_CANCEL = "user_cancel"

# 终态集合
TERMINAL_STATUSES = {SESSION_CLOSED, SESSION_CANCELLED}
```

## 5.2 更新 `row_to_session`

```python
def row_to_session(row) -> Session:
    return Session(
        session_id=row["session_id"],
        conversation_key=row["conversation_key"],
        channel=row["channel"],
        status=row["status"],
        close_reason=row["close_reason"],
        is_complete=bool(row["is_complete"]) if row["is_complete"] is not None else None,
        started_at=parse_iso(row["started_at"]),
        updated_at=parse_iso(row["updated_at"]),
        expired_at=parse_iso(row["expired_at"]),
        settled_at=parse_iso(row["settled_at"]),
    )
```

## 5.3 更新 `create_session`

```python
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
            SESSION_ACTIVE,  # ← 改成 active
            iso(now),
            iso(now),
            iso(expired_at),
        ),
    )

    session = get_session(conn, session_id)
    assert session is not None
    return session
```

## 5.4 更新 `find_active_session`

```python
def find_active_session(
    conn,
    conversation_key: str,
    timeout_minutes: int,
) -> Optional[Session]:
    """
    查找当前会话键下仍然活跃的 session。
    只返回 status='active' 且未超时的。
    """
    threshold = utcnow() - timedelta(minutes=timeout_minutes)

    row = conn.execute(
        """
        SELECT *
        FROM sessions
        WHERE conversation_key = ?
          AND status = ?
          AND updated_at >= ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (conversation_key, SESSION_ACTIVE, threshold.isoformat()),
    ).fetchone()

    if not row:
        return None

    return row_to_session(row)
```

## 5.5 新增：标记过期 session

```python
def mark_expired_sessions(
    conn,
    timeout_minutes: int,
    conversation_key: Optional[str] = None,
) -> int:
    """
    将超时的 active session 标记为 expired。

    参数：
        conversation_key: 如果指定，只处理该会话；否则处理所有会话。

    返回：
        受影响的行数。
    """
    threshold = utcnow() - timedelta(minutes=timeout_minutes)
    now = utcnow()

    if conversation_key:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET status = ?, updated_at = ?
            WHERE status = ?
              AND conversation_key = ?
              AND updated_at < ?
            """,
            (SESSION_EXPIRED, iso(now), SESSION_ACTIVE, conversation_key, threshold.isoformat()),
        )
    else:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET status = ?, updated_at = ?
            WHERE status = ?
              AND updated_at < ?
            """,
            (SESSION_EXPIRED, iso(now), SESSION_ACTIVE, threshold.isoformat()),
        )

    return cursor.rowcount
```

## 5.6 新增：查找待结算的 expired session

```python
def find_expired_sessions(
    conn,
    conversation_key: Optional[str] = None,
    limit: int = 100,
) -> List[Session]:
    """
    查找所有状态为 expired 的 session。
    """
    if conversation_key:
        rows = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE status = ?
              AND conversation_key = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (SESSION_EXPIRED, conversation_key, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE status = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (SESSION_EXPIRED, limit),
        ).fetchall()

    return [row_to_session(row) for row in rows]
```

## 5.7 更新 `settle_session`：支持终态判定

```python
def settle_session(
    conn,
    session_id: str,
    message_id: Optional[str] = None,
    reasoning: Optional[str] = None,
    close_reason: str = CLOSE_REASON_MANUAL,
) -> tuple[Session, List[TradeDraft]]:
    """
    结算整个 session。

    流程：
    1. 查找该 session 下所有 draft；
    2. 逐个 settle_draft；
    3. 根据 close_reason 决定终态：
       - user_cancel → cancelled
       - 其他 → closed
    4. 计算 is_complete（所有 draft 的所有必需字段是否齐全）；
    5. 写入结算事件；
    6. 返回最新的 session 和 drafts。
    """
    session = get_session(conn, session_id)

    if session is None:
        raise ValueError(f"session not found: {session_id}")

    # 幂等：已经是终态，直接返回
    if session.status in TERMINAL_STATUSES:
        return session, list_drafts(conn, session_id)

    drafts = list_drafts(conn, session_id)

    # 结算每个 draft，并统计是否完整
    all_complete = True

    for draft in drafts:
        if draft.status in SETTLE_SKIP_DRAFT_STATUSES:
            continue

        settled_draft = settle_draft(
            conn,
            draft_id=draft.draft_id,
            message_id=message_id,
            reasoning=reasoning,
        )

        # 检查是否有 unknown 字段
        if settled_draft:
            has_unknown = any(
                slot.status == "unknown"
                for slot in settled_draft.slots.values()
            )
            if has_unknown:
                all_complete = False

    # 决定终态
    if close_reason == CLOSE_REASON_USER_CANCEL:
        final_status = SESSION_CANCELLED
    else:
        final_status = SESSION_CLOSED

    now = utcnow()

    conn.execute(
        """
        UPDATE sessions
        SET status = ?,
            close_reason = ?,
            is_complete = ?,
            settled_at = ?,
            updated_at = ?
        WHERE session_id = ?
        """,
        (
            final_status,
            close_reason,
            1 if all_complete else 0,
            iso(now),
            iso(now),
            session_id,
        ),
    )

    append_event(
        conn,
        session_id=session_id,
        draft_id=None,
        message_id=message_id,
        action_type="SETTLE",
        field=None,
        old_value=session.status,
        new_value={
            "status": final_status,
            "close_reason": close_reason,
            "is_complete": all_complete,
        },
        reasoning=reasoning,
    )

    settled_session = get_session(conn, session_id)
    assert settled_session is not None

    settled_drafts = list_drafts(conn, session_id)

    return settled_session, settled_drafts
```

## 5.8 新增：批量结算所有 expired session

```python
def settle_all_expired_sessions(
    conn,
    close_reason: str = CLOSE_REASON_TIMEOUT_POLL,
    reasoning: Optional[str] = None,
) -> List[tuple[Session, List[TradeDraft]]]:
    """
    批量结算所有状态为 expired 的 session。

    用于轮询任务。
    """
    expired_sessions = find_expired_sessions(conn)
    results = []

    for session in expired_sessions:
        try:
            settled_session, settled_drafts = settle_session(
                conn,
                session_id=session.session_id,
                close_reason=close_reason,
                reasoning=reasoning or "session expired",
            )
            results.append((settled_session, settled_drafts))
        except Exception:
            # 单个 session 结算失败不影响其他
            continue

    return results
```

## 5.9 新增：按会话键结算

```python
def settle_expired_sessions_for_conversation(
    conn,
    conversation_key: str,
    close_reason: str = CLOSE_REASON_NEW_SESSION,
    reasoning: Optional[str] = None,
) -> List[tuple[Session, List[TradeDraft]]]:
    """
    结算某个会话键下所有状态为 expired 的 session。

    用于 SessionResolver 开新 session 前。
    """
    expired_sessions = find_expired_sessions(
        conn,
        conversation_key=conversation_key,
    )
    results = []

    for session in expired_sessions:
        settled_session, settled_drafts = settle_session(
            conn,
            session_id=session.session_id,
            close_reason=close_reason,
            reasoning=reasoning or "settle before opening new session",
        )
        results.append((settled_session, settled_drafts))

    return results
```

## 5.10 移除或替换 `find_latest_unsettled_session`

原来的 `find_latest_unsettled_session` 可以删掉，因为现在逻辑变成：

```text
1. 先 mark_expired_sessions（把超时的 active 标成 expired）
2. 再 settle_expired_sessions_for_conversation（结算所有 expired）
```

不再需要"查找未结算"这个模糊概念。

---

# 六、`src/session_resolver.py` 修改

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .models import IncomingMessage, SessionResolutionResult


class SessionResolver(ABC):
    """
    SessionResolver 接口。

    职责：
    1. 判断当前消息属于哪个会话；
    2. 如果当前会话仍活跃，则复用；
    3. 如果需要新开一个会话：
       a. 先把超时的 active 标记为 expired；
       b. 结算所有 expired 的 session；
       c. 创建新 session。
    """

    @abstractmethod
    def conversation_key(self, message: IncomingMessage) -> str:
        raise NotImplementedError

    @abstractmethod
    def resolve(
        self,
        conn,
        message: IncomingMessage,
    ) -> SessionResolutionResult:
        raise NotImplementedError


class DefaultSessionResolver(SessionResolver):
    """
    默认规则：

    1. 如果有 group_id，则按群会话切分；
    2. 如果是私聊，则按 sender_id + receiver_id 切分；
    3. 在 SESSION_TIMEOUT_MINUTES 内有活跃 session，则复用；
    4. 否则：
       a. 把超时的 active 标记为 expired；
       b. 结算所有 expired 的 session；
       c. 创建新 session。
    """

    def conversation_key(self, message: IncomingMessage) -> str:
        if message.group_id:
            return f"{message.channel}:group:{message.group_id}"

        if message.receiver_id:
            a, b = sorted([message.sender_id, message.receiver_id])
            return f"{message.channel}:private:{a}:{b}"

        return f"{message.channel}:private:{message.sender_id}"

    def resolve(
        self,
        conn,
        message: IncomingMessage,
    ) -> SessionResolutionResult:
        key = self.conversation_key(message)

        # ────────────────────────────────────────────
        # Step 1: 把当前会话下超时的 active 标记为 expired
        # ────────────────────────────────────────────
        state_store.mark_expired_sessions(
            conn,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
            conversation_key=key,
        )

        # ────────────────────────────────────────────
        # Step 2: 查找仍然活跃的 session
        # ────────────────────────────────────────────
        active_session = state_store.find_active_session(
            conn,
            conversation_key=key,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        if active_session:
            return SessionResolutionResult(
                session=active_session,
                created=False,
                settled_session=None,
                settled_drafts=[],
            )

        # ────────────────────────────────────────────
        # Step 3: 结算所有 expired 的 session
        # ────────────────────────────────────────────
        settled_results = state_store.settle_expired_sessions_for_conversation(
            conn,
            conversation_key=key,
            close_reason=state_store.CLOSE_REASON_NEW_SESSION,
            reasoning="settle before opening new session",
        )

        # 取最近一个结算结果返回给前端
        settled_session = None
        settled_drafts = []

        if settled_results:
            settled_session, settled_drafts = settled_results[0]

        # ────────────────────────────────────────────
        # Step 4: 创建新 session
        # ────────────────────────────────────────────
        new_session = state_store.create_session(
            conn,
            conversation_key=key,
            channel=message.channel,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        return SessionResolutionResult(
            session=new_session,
            created=True,
            settled_session=settled_session,
            settled_drafts=settled_drafts,
        )
```

---

# 七、后台轮询任务

## 7.1 新增 `src/maintenance.py`

```python
"""
后台维护任务：
1. 标记过期 session
2. 结算 expired session

这是纯 CPU 工作，不涉及 LLM API。
"""

import logging
from typing import Optional

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .db import get_db


logger = logging.getLogger(__name__)


def run_maintenance_sync(
    conversation_key: Optional[str] = None,
) -> dict:
    """
    执行一次维护任务（同步版本）。

    流程：
    1. 把超时的 active session 标记为 expired；
    2. 结算所有 expired 的 session。

    返回：
        {
            "marked_expired": int,
            "settled": int,
        }
    """
    with get_db() as conn:
        # Step 1: 标记过期
        marked = state_store.mark_expired_sessions(
            conn,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
            conversation_key=conversation_key,
        )

        # Step 2: 结算
        results = state_store.settle_all_expired_sessions(
            conn,
            close_reason=state_store.CLOSE_REASON_TIMEOUT_POLL,
            reasoning="session expired (poll)",
        )

        settled = len(results)

        if marked > 0 or settled > 0:
            logger.info(
                "Maintenance: marked %d expired, settled %d sessions",
                marked,
                settled,
            )

        return {
            "marked_expired": marked,
            "settled": settled,
        }


async def run_maintenance_async(
    conversation_key: Optional[str] = None,
) -> dict:
    """
    执行一次维护任务（异步版本）。
    """
    import asyncio
    return await asyncio.to_thread(
        run_maintenance_sync,
        conversation_key,
    )
```

## 7.2 更新 `main.py`：加入轮询循环

```python
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import router
from src.db import init_db
from src.feedback_store import init_feedback_db
from src.maintenance import run_maintenance_sync


logger = logging.getLogger(__name__)

# 轮询间隔（秒）
MAINTENANCE_INTERVAL_SECONDS = 30


async def maintenance_loop() -> None:
    """
    后台轮询任务：
    每隔 MAINTENANCE_INTERVAL_SECONDS 秒执行一次维护。
    """
    while True:
        try:
            result = await asyncio.to_thread(run_maintenance_sync)

            if result["marked_expired"] > 0 or result["settled"] > 0:
                logger.info(
                    "Maintenance loop: marked=%d, settled=%d",
                    result["marked_expired"],
                    result["settled"],
                )

        except Exception:
            logger.exception("Maintenance loop failed")

        await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    init_db()
    init_feedback_db()

    # 启动后台维护任务
    maintenance_task = asyncio.create_task(maintenance_loop())

    logger.info(
        "Maintenance loop started (interval=%ds)",
        MAINTENANCE_INTERVAL_SECONDS,
    )

    yield

    # 关闭后台任务
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Trade Dialogue DST",
    description="多轮交易对话状态追踪与增量 NER 服务",
    version="0.4.0",
    lifespan=lifespan,
)

app.include_router(router, tags=["dst"])


@app.get("/health")
def health():
    return {"status": "ok"}
```

---

# 八、API 新增接口

## 8.1 手动结算（已有，更新 `close_reason`）

```python
@router.post(
    "/sessions/{session_id}/settle",
    response_model=SessionSettleResult,
)
def api_settle_session(
    session_id: str,
    reason: Optional[str] = None,
):
    """
    手动结算一个 session。
    """
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        settled_session, settled_drafts = state_store.settle_session(
            conn,
            session_id=session_id,
            close_reason=state_store.CLOSE_REASON_MANUAL,
            reasoning=reason or "manual settle",
        )

        return SessionSettleResult(
            session=settled_session,
            drafts=settled_drafts,
        )
```

## 8.2 新增：用户取消

```python
@router.post(
    "/sessions/{session_id}/cancel",
    response_model=SessionSettleResult,
)
def api_cancel_session(
    session_id: str,
    reason: Optional[str] = None,
):
    """
    用户主动取消一个 session。

    与 /settle 的区别：
    - /settle 结算后状态为 closed
    - /cancel 结算后状态为 cancelled
    """
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        settled_session, settled_drafts = state_store.settle_session(
            conn,
            session_id=session_id,
            close_reason=state_store.CLOSE_REASON_USER_CANCEL,
            reasoning=reason or "user cancel",
        )

        return SessionSettleResult(
            session=settled_session,
            drafts=settled_drafts,
        )
```

## 8.3 新增：手动触发维护（调试用）

```python
@router.post("/maintenance/run")
def api_run_maintenance():
    """
    手动触发一次维护任务（调试用）。

    生产环境由后台轮询自动执行。
    """
    from .maintenance import run_maintenance_sync

    result = run_maintenance_sync()

    return {
        "status": "ok",
        "marked_expired": result["marked_expired"],
        "settled": result["settled"],
    }
```

---

# 九、完整状态转移表

| 当前状态 | 触发事件 | 目标状态 | 触发函数 |
|---|---|---|---|
| - | 创建 | `active` | `create_session()` |
| `active` | 超时 | `expired` | `mark_expired_sessions()` |
| `expired` | 结算 | `closed` | `settle_session(close_reason=...)` |
| `expired` | 用户取消 | `cancelled` | `settle_session(close_reason=user_cancel)` |
| `active` | 用户取消 | `cancelled` | `settle_session(close_reason=user_cancel)` |
| `closed` | 任何 | `closed`（终态） | - |
| `cancelled` | 任何 | `cancelled`（终态） | - |

---

# 十、结算时机总结

```
┌─────────────────────────────────────────────────────────────┐
│                    结算触发全景                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  T1. 新消息触发（SessionResolver）                          │
│      ├─ 条件：新消息需要开新 session                        │
│      ├─ 动作：先结算当前会话下所有 expired                  │
│      └─ close_reason: new_session                           │
│                                                             │
│  T2. 轮询触发（maintenance_loop）                           │
│      ├─ 条件：每 30 秒扫描一次                              │
│      ├─ 动作：标记过期 → 结算所有 expired                   │
│      └─ close_reason: timeout_poll                          │
│                                                             │
│  T3. 手动触发（/settle）                                    │
│      ├─ 条件：前端点击"结束会话"                            │
│      ├─ 动作：结算指定 session                              │
│      └─ close_reason: manual                                │
│                                                             │
│  T4. 用户取消（/cancel）                                    │
│      ├─ 条件：用户明确说"不要了"                            │
│      ├─ 动作：结算指定 session，状态为 cancelled            │
│      └─ close_reason: user_cancel                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

# 十一、回答你的核心问题

> 我反正觉得当新开一个session时必然应该伴随着对上一个未结算session的结算，结算后session的状态应该变成closed或cancelled。

✅ **完全正确**。代码中 `SessionResolver.resolve()` 现在会：

1. 先 `mark_expired_sessions()` 把超时的 `active` 标成 `expired`；
2. 再 `settle_expired_sessions_for_conversation()` 结算所有 `expired`；
3. 最后 `create_session()` 开新的。

结算后状态：

- 正常结算 → `closed`
- 用户取消 → `cancelled`

> 也应该有轮询：以某个频率扫描是否有状态为expired的session，如果有，结算它。

✅ **完全正确**。`maintenance_loop` 每 30 秒：

1. `mark_expired_sessions()`：把超时的 `active` 标成 `expired`；
2. `settle_all_expired_sessions()`：结算所有 `expired`。

这样**当天最后一个 session 也会在一定时间后被轮询任务结算**，不会永远悬着。

> 反正session的结算是纯粹的cpu work，不涉及LLM api。

✅ **完全正确**。整个结算链路：

```text
mark_expired_sessions()     → 纯 SQL UPDATE
settle_draft()              → 纯 Python 字段检查 + SQL UPDATE
settle_session()            → 纯 Python 循环 + SQL UPDATE
```

**没有任何 LLM 调用**，速度快、成本低、可以随时安全执行。

---

# 十二、最终架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI 服务                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ /api/messages│    │ /settle      │    │ /cancel      │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              SessionResolver.resolve()               │   │
│  │  1. mark_expired_sessions()                         │   │
│  │  2. find_active_session()                           │   │
│  │  3. settle_expired_sessions_for_conversation()      │   │
│  │  4. create_session()                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           maintenance_loop (后台轮询)                │   │
│  │  每 30 秒：                                          │   │
│  │  1. mark_expired_sessions()                         │   │
│  │  2. settle_all_expired_sessions()                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              state_store (纯 CPU)                    │   │
│  │  - settle_draft()                                   │   │
│  │  - settle_session()                                 │   │
│  │  - mark_expired_sessions()                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  SQLite (data/)                      │   │
│  │  - app.db: sessions / messages / drafts / events    │   │
│  │  - feedback.db: feedback                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

这套设计确保了：

1. **每个 session 最终都会进入终态**（四路触发兜底）；
2. **结算是纯 CPU 工作**，可以随时安全执行；
3. **状态机清晰**，`active → expired → closed/cancelled`；
4. **审计完整**，`close_reason` + `is_complete` + `settled_at` 记录一切。


---
🙋**user**:
---
```
is_complete字段放在session去判断？我怎么觉得有点不对呢？单个session内部，可以有所有slots都confirmed的tradedraft，也可以有部分slots未能confirmed的tradedraft才对吧？
这个is_complete判断应该放在tradedraft内部才对啊。
请将结算会话 settle session 部分的改动重新描述，基于你前面给出的第一版代码。
```

---
🤖**assistant**:
---

你说得对。`is_complete` 放在 session 级别确实不合理。

一个 session 内部可能同时存在：

```text
draft_1: 所有字段齐全 → is_complete = true
draft_2: 缺少 asset_code → is_complete = false
draft_3: 缺少 price → is_complete = false
```

所以 `is_complete` 应该放在 **每个 `trade_draft` 内部**，而不是 session 上。

下面我基于第一版代码，重新描述结算部分的完整改动。

---

# 一、改动文件清单

| 文件 | 改动内容 |
|---|---|
| `src/models.py` | 新增状态枚举，修改 `Session`、`TradeDraft` 模型 |
| `src/db.py` | 修改 `sessions` 和 `trade_drafts` 表结构 |
| `src/state_store.py` | 新增结算核心函数 |
| `src/session_resolver.py` | 修改 `resolve()` 逻辑 |
| `src/api.py` | 新增 `/settle`、`/cancel` 接口 |
| `src/maintenance.py` | **新增文件**，后台轮询 |
| `main.py` | 启动后台轮询任务 |

---

# 二、`src/models.py` 修改

## 2.1 新增状态枚举

在文件顶部 `from enum import Enum` 之后，新增：

```python
class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CloseReason(str, Enum):
    NEW_SESSION = "new_session"
    TIMEOUT_POLL = "timeout_poll"
    MANUAL = "manual"
    USER_CANCEL = "user_cancel"
```

## 2.2 修改 `Session` 模型

替换原来的 `Session`：

```python
class Session(BaseModel):
    """
    一次交易协商上下文。

    状态机：
        active → expired → closed
        active → cancelled
        expired → cancelled
    """
    session_id: str
    conversation_key: str
    channel: str
    status: str = "active"
    close_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
```

注意：**`Session` 上没有 `is_complete`**。

## 2.3 修改 `TradeDraft` 模型

替换原来的 `TradeDraft`，新增 `is_complete` 字段：

```python
class TradeDraft(BaseModel):
    """
    一笔交易草稿。

    结算后：
    - is_complete=true  → 所有必需字段都有值
    - is_complete=false → 存在字段缺失
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
    is_complete: Optional[bool] = None  # ← 新增：结算时判断
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

## 2.4 修改 `ProcessResult`

新增 `settled_session` 和 `settled_drafts`：

```python
class ProcessResult(BaseModel):
    """
    单次消息处理结果。
    """
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    clarify_question: Optional[str] = None
    message_id: str

    # 如果本次消息触发了新 session，并结算了上一个 session，
    # 这里会返回被结算的旧 session 以及旧 session 下的所有草稿。
    settled_session: Optional[Session] = None
    settled_drafts: List[TradeDraft] = Field(default_factory=list)
```

## 2.5 新增 `SessionSettleResult`

```python
class SessionSettleResult(BaseModel):
    """
    Session 结算结果。
    """
    session: Session
    drafts: List[TradeDraft] = Field(default_factory=list)
```

## 2.6 新增 `SessionResolutionResult`

```python
class SessionResolutionResult(BaseModel):
    """
    SessionResolver 的解析结果。

    如果当前消息仍然属于活跃 session，则只返回当前 session。
    如果当前消息触发了新 session，并且系统自动结算了上一个 session，
    则同时返回 settled_session 和 settled_drafts。
    """
    session: Session
    created: bool = False

    settled_session: Optional[Session] = None
    settled_drafts: List[TradeDraft] = Field(default_factory=list)
```

---

# 三、`src/db.py` 修改

## 3.1 修改 `sessions` 表

替换 `SCHEMA` 中的 `sessions` 表：

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    conversation_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    close_reason TEXT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expired_at TEXT,
    settled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_conversation
ON sessions(conversation_key, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_sessions_status
ON sessions(status, updated_at);
```

## 3.2 修改 `trade_drafts` 表

替换 `SCHEMA` 中的 `trade_drafts` 表，新增 `is_complete` 字段：

```sql
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
    is_complete INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_trade_drafts_session
ON trade_drafts(session_id);
```

---

# 四、`src/state_store.py` 修改

这是改动最大的文件。以下所有函数都是**新增**或**替换**的。

## 4.1 新增常量

在文件顶部新增：

```python
# Session 状态
SESSION_ACTIVE = "active"
SESSION_EXPIRED = "expired"
SESSION_CLOSED = "closed"
SESSION_CANCELLED = "cancelled"

# 结算原因
CLOSE_REASON_NEW_SESSION = "new_session"
CLOSE_REASON_TIMEOUT_POLL = "timeout_poll"
CLOSE_REASON_MANUAL = "manual"
CLOSE_REASON_USER_CANCEL = "user_cancel"

# 终态集合
TERMINAL_STATUSES = {SESSION_CLOSED, SESSION_CANCELLED}

# 结算时需要检查的必需字段
# 你可以根据业务调整
REQUIRED_SETTLE_FIELDS = (
    "asset_name",
    "asset_code",
    "direction",
    "amount",
    "price",
)

# 如果你不想结算已被拒绝 / 取消的 draft，可以改成：
# SETTLE_SKIP_DRAFT_STATUSES = {"rejected", "cancelled"}
SETTLE_SKIP_DRAFT_STATUSES = set()
```

## 4.2 修改 `row_to_session`

```python
def row_to_session(row) -> Session:
    return Session(
        session_id=row["session_id"],
        conversation_key=row["conversation_key"],
        channel=row["channel"],
        status=row["status"],
        close_reason=row["close_reason"],
        started_at=parse_iso(row["started_at"]),
        updated_at=parse_iso(row["updated_at"]),
        expired_at=parse_iso(row["expired_at"]),
        settled_at=parse_iso(row["settled_at"]),
    )
```

## 4.3 修改 `row_to_draft`

```python
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
        is_complete=bool(row["is_complete"]) if row["is_complete"] is not None else None,
        created_at=parse_iso(row["created_at"]),
        updated_at=parse_iso(row["updated_at"]),
    )
```

## 4.4 修改 `create_session`

```python
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
            SESSION_ACTIVE,
            iso(now),
            iso(now),
            iso(expired_at),
        ),
    )

    session = get_session(conn, session_id)
    assert session is not None
    return session
```

## 4.5 修改 `find_active_session`

```python
def find_active_session(
    conn,
    conversation_key: str,
    timeout_minutes: int,
) -> Optional[Session]:
    """
    查找当前会话键下仍然活跃的 session。
    只返回 status='active' 且未超时的。
    """
    threshold = utcnow() - timedelta(minutes=timeout_minutes)

    row = conn.execute(
        """
        SELECT *
        FROM sessions
        WHERE conversation_key = ?
          AND status = ?
          AND updated_at >= ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (conversation_key, SESSION_ACTIVE, threshold.isoformat()),
    ).fetchone()

    if not row:
        return None

    return row_to_session(row)
```

## 4.6 新增：`mark_expired_sessions`

```python
def mark_expired_sessions(
    conn,
    timeout_minutes: int,
    conversation_key: Optional[str] = None,
) -> int:
    """
    将超时的 active session 标记为 expired。

    参数：
        conversation_key: 如果指定，只处理该会话；否则处理所有会话。

    返回：
        受影响的行数。
    """
    threshold = utcnow() - timedelta(minutes=timeout_minutes)
    now = utcnow()

    if conversation_key:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET status = ?, updated_at = ?
            WHERE status = ?
              AND conversation_key = ?
              AND updated_at < ?
            """,
            (
                SESSION_EXPIRED,
                iso(now),
                SESSION_ACTIVE,
                conversation_key,
                threshold.isoformat(),
            ),
        )
    else:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET status = ?, updated_at = ?
            WHERE status = ?
              AND updated_at < ?
            """,
            (
                SESSION_EXPIRED,
                iso(now),
                SESSION_ACTIVE,
                threshold.isoformat(),
            ),
        )

    return cursor.rowcount
```

## 4.7 新增：`find_expired_sessions`

```python
def find_expired_sessions(
    conn,
    conversation_key: Optional[str] = None,
    limit: int = 100,
) -> List[Session]:
    """
    查找所有状态为 expired 的 session。
    """
    if conversation_key:
        rows = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE status = ?
              AND conversation_key = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (SESSION_EXPIRED, conversation_key, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE status = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (SESSION_EXPIRED, limit),
        ).fetchall()

    return [row_to_session(row) for row in rows]
```

## 4.8 新增：`_is_missing_value`

```python
def _is_missing_value(value: Any) -> bool:
    """
    判断某个字段值是否缺失。

    规则：
    1. None 算缺失；
    2. 空字符串算缺失；
    3. 0 不算缺失；
    4. False 不算缺失。
    """
    if value is None:
        return True

    if isinstance(value, str) and not value.strip():
        return True

    return False
```

## 4.9 新增：`settle_draft`（核心）

```python
def settle_draft(
    conn,
    draft_id: str,
    message_id: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> Optional[TradeDraft]:
    """
    结算单个 trade_draft。

    规则：
    1. 检查 REQUIRED_SETTLE_FIELDS 是否都有值；
    2. 如果所有字段都有值：
       - is_complete = true
       - 将所有 proposed / confirmed 状态的 slot 改成 confirmed；
       - 其他状态不动；
    3. 如果存在字段缺失：
       - is_complete = false
       - 将缺失字段的 slot_status 改成 unknown；
       - 其他已有字段状态不动。
    """
    row = conn.execute(
        "SELECT * FROM trade_drafts WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()

    if not row:
        return None

    slots = json.loads(row["slots_json"] or "{}")
    now = utcnow()

    # ────────────────────────────────────────────
    # Step 1: 检查哪些字段缺失
    # ────────────────────────────────────────────
    missing_fields = []

    for field in REQUIRED_SETTLE_FIELDS:
        value = row[field]
        if _is_missing_value(value):
            missing_fields.append(field)

    # ────────────────────────────────────────────
    # Step 2: 根据是否缺失，决定 is_complete
    # ────────────────────────────────────────────
    is_complete = len(missing_fields) == 0

    if missing_fields:
        # 存在字段缺失：
        # 只把缺失字段的 slot 标成 unknown。
        for field in missing_fields:
            slots[field] = SlotState(
                value=None,
                status="unknown",
                source_message_id=message_id,
                updated_at=now,
            ).model_dump(mode="json")

    else:
        # 所有字段都有值：
        # 先确保每个必需字段都有 slot。
        for field in REQUIRED_SETTLE_FIELDS:
            if field not in slots:
                slots[field] = SlotState(
                    value=row[field],
                    status="confirmed",
                    source_message_id=message_id,
                    updated_at=now,
                ).model_dump(mode="json")

        # 将所有 proposed / confirmed 的 slot 改成 confirmed。
        # 其他状态，例如 rejected / ambiguous / unknown，不动。
        for slot in slots.values():
            if slot.get("status") in {"proposed", "confirmed"}:
                slot["status"] = "confirmed"
                slot["updated_at"] = now.isoformat()

    # ────────────────────────────────────────────
    # Step 3: 写回数据库
    # ────────────────────────────────────────────
    conn.execute(
        """
        UPDATE trade_drafts
        SET slots_json = ?,
            is_complete = ?,
            updated_at = ?
        WHERE draft_id = ?
        """,
        (
            json.dumps(slots, ensure_ascii=False),
            1 if is_complete else 0,
            iso(now),
            draft_id,
        ),
    )

    # ────────────────────────────────────────────
    # Step 4: 写入结算事件
    # ────────────────────────────────────────────
    append_event(
        conn,
        session_id=row["session_id"],
        draft_id=draft_id,
        message_id=message_id,
        action_type="SETTLE",
        field=None,
        old_value=None,
        new_value={
            "is_complete": is_complete,
            "missing_fields": missing_fields,
        },
        reasoning=reasoning,
    )

    return get_draft(conn, draft_id)
```

## 4.10 新增：`settle_session`（核心）

```python
def settle_session(
    conn,
    session_id: str,
    message_id: Optional[str] = None,
    reasoning: Optional[str] = None,
    close_reason: str = CLOSE_REASON_MANUAL,
) -> tuple[Session, List[TradeDraft]]:
    """
    结算整个 session。

    流程：
    1. 查找该 session 下所有 draft；
    2. 逐个 settle_draft（每个 draft 独立判断 is_complete）；
    3. 根据 close_reason 决定终态：
       - user_cancel → cancelled
       - 其他 → closed
    4. 写入结算事件；
    5. 返回最新的 session 和 drafts。

    注意：
    - is_complete 在每个 draft 上独立判断，不在 session 上；
    - session 只记录 close_reason 和 settled_at。
    """
    session = get_session(conn, session_id)

    if session is None:
        raise ValueError(f"session not found: {session_id}")

    # 幂等：已经是终态，直接返回
    if session.status in TERMINAL_STATUSES:
        return session, list_drafts(conn, session_id)

    drafts = list_drafts(conn, session_id)

    # ────────────────────────────────────────────
    # Step 1: 逐个结算每个 draft
    # ────────────────────────────────────────────
    for draft in drafts:
        if draft.status in SETTLE_SKIP_DRAFT_STATUSES:
            continue

        settle_draft(
            conn,
            draft_id=draft.draft_id,
            message_id=message_id,
            reasoning=reasoning,
        )

    # ────────────────────────────────────────────
    # Step 2: 决定终态
    # ────────────────────────────────────────────
    if close_reason == CLOSE_REASON_USER_CANCEL:
        final_status = SESSION_CANCELLED
    else:
        final_status = SESSION_CLOSED

    now = utcnow()

    # ────────────────────────────────────────────
    # Step 3: 更新 session 状态
    # ────────────────────────────────────────────
    conn.execute(
        """
        UPDATE sessions
        SET status = ?,
            close_reason = ?,
            settled_at = ?,
            updated_at = ?
        WHERE session_id = ?
        """,
        (
            final_status,
            close_reason,
            iso(now),
            iso(now),
            session_id,
        ),
    )

    # ────────────────────────────────────────────
    # Step 4: 写入结算事件
    # ────────────────────────────────────────────
    append_event(
        conn,
        session_id=session_id,
        draft_id=None,
        message_id=message_id,
        action_type="SETTLE",
        field=None,
        old_value=session.status,
        new_value={
            "status": final_status,
            "close_reason": close_reason,
        },
        reasoning=reasoning,
    )

    # ────────────────────────────────────────────
    # Step 5: 返回最新状态
    # ────────────────────────────────────────────
    settled_session = get_session(conn, session_id)
    assert settled_session is not None

    settled_drafts = list_drafts(conn, session_id)

    return settled_session, settled_drafts
```

## 4.11 新增：`settle_all_expired_sessions`

```python
def settle_all_expired_sessions(
    conn,
    close_reason: str = CLOSE_REASON_TIMEOUT_POLL,
    reasoning: Optional[str] = None,
) -> List[tuple[Session, List[TradeDraft]]]:
    """
    批量结算所有状态为 expired 的 session。

    用于轮询任务。
    """
    expired_sessions = find_expired_sessions(conn)
    results = []

    for session in expired_sessions:
        try:
            settled_session, settled_drafts = settle_session(
                conn,
                session_id=session.session_id,
                close_reason=close_reason,
                reasoning=reasoning or "session expired (poll)",
            )
            results.append((settled_session, settled_drafts))
        except Exception:
            # 单个 session 结算失败不影响其他
            continue

    return results
```

## 4.12 新增：`settle_expired_sessions_for_conversation`

```python
def settle_expired_sessions_for_conversation(
    conn,
    conversation_key: str,
    close_reason: str = CLOSE_REASON_NEW_SESSION,
    reasoning: Optional[str] = None,
) -> List[tuple[Session, List[TradeDraft]]]:
    """
    结算某个会话键下所有状态为 expired 的 session。

    用于 SessionResolver 开新 session 前。
    """
    expired_sessions = find_expired_sessions(
        conn,
        conversation_key=conversation_key,
    )
    results = []

    for session in expired_sessions:
        settled_session, settled_drafts = settle_session(
            conn,
            session_id=session.session_id,
            close_reason=close_reason,
            reasoning=reasoning or "settle before opening new session",
        )
        results.append((settled_session, settled_drafts))

    return results
```

---

# 五、`src/session_resolver.py` 修改

整体替换：

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .models import IncomingMessage, SessionResolutionResult


class SessionResolver(ABC):
    """
    SessionResolver 接口。

    职责：
    1. 判断当前消息属于哪个会话；
    2. 如果当前会话仍活跃，则复用；
    3. 如果需要新开一个会话：
       a. 先把超时的 active 标记为 expired；
       b. 结算所有 expired 的 session；
       c. 创建新 session。
    """

    @abstractmethod
    def conversation_key(self, message: IncomingMessage) -> str:
        raise NotImplementedError

    @abstractmethod
    def resolve(
        self,
        conn,
        message: IncomingMessage,
    ) -> SessionResolutionResult:
        raise NotImplementedError


class DefaultSessionResolver(SessionResolver):
    """
    默认规则：

    1. 如果有 group_id，则按群会话切分；
    2. 如果是私聊，则按 sender_id + receiver_id 切分；
    3. 在 SESSION_TIMEOUT_MINUTES 内有活跃 session，则复用；
    4. 否则：
       a. 把超时的 active 标记为 expired；
       b. 结算所有 expired 的 session；
       c. 创建新 session。
    """

    def conversation_key(self, message: IncomingMessage) -> str:
        if message.group_id:
            return f"{message.channel}:group:{message.group_id}"

        if message.receiver_id:
            a, b = sorted([message.sender_id, message.receiver_id])
            return f"{message.channel}:private:{a}:{b}"

        return f"{message.channel}:private:{message.sender_id}"

    def resolve(
        self,
        conn,
        message: IncomingMessage,
    ) -> SessionResolutionResult:
        key = self.conversation_key(message)

        # ────────────────────────────────────────────
        # Step 1: 把当前会话下超时的 active 标记为 expired
        # ────────────────────────────────────────────
        state_store.mark_expired_sessions(
            conn,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
            conversation_key=key,
        )

        # ────────────────────────────────────────────
        # Step 2: 查找仍然活跃的 session
        # ────────────────────────────────────────────
        active_session = state_store.find_active_session(
            conn,
            conversation_key=key,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        if active_session:
            return SessionResolutionResult(
                session=active_session,
                created=False,
                settled_session=None,
                settled_drafts=[],
            )

        # ────────────────────────────────────────────
        # Step 3: 结算所有 expired 的 session
        # ────────────────────────────────────────────
        settled_results = state_store.settle_expired_sessions_for_conversation(
            conn,
            conversation_key=key,
            close_reason=state_store.CLOSE_REASON_NEW_SESSION,
            reasoning="settle before opening new session",
        )

        # 取最近一个结算结果返回给前端
        settled_session = None
        settled_drafts = []

        if settled_results:
            settled_session, settled_drafts = settled_results[0]

        # ────────────────────────────────────────────
        # Step 4: 创建新 session
        # ────────────────────────────────────────────
        new_session = state_store.create_session(
            conn,
            conversation_key=key,
            channel=message.channel,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
        )

        return SessionResolutionResult(
            session=new_session,
            created=True,
            settled_session=settled_session,
            settled_drafts=settled_drafts,
        )
```

---

# 六、`src/api.py` 新增接口

在原有接口基础上，新增以下接口：

## 6.1 手动结算

```python
@router.post(
    "/sessions/{session_id}/settle",
    response_model=SessionSettleResult,
)
def api_settle_session(
    session_id: str,
    reason: Optional[str] = None,
):
    """
    手动结算一个 session。

    结算后状态为 closed。
    """
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        settled_session, settled_drafts = state_store.settle_session(
            conn,
            session_id=session_id,
            close_reason=state_store.CLOSE_REASON_MANUAL,
            reasoning=reason or "manual settle",
        )

        return SessionSettleResult(
            session=settled_session,
            drafts=settled_drafts,
        )
```

## 6.2 用户取消

```python
@router.post(
    "/sessions/{session_id}/cancel",
    response_model=SessionSettleResult,
)
def api_cancel_session(
    session_id: str,
    reason: Optional[str] = None,
):
    """
    用户主动取消一个 session。

    与 /settle 的区别：
    - /settle 结算后状态为 closed
    - /cancel 结算后状态为 cancelled
    """
    with get_db() as conn:
        session = state_store.get_session(conn, session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="session not found",
            )

        settled_session, settled_drafts = state_store.settle_session(
            conn,
            session_id=session_id,
            close_reason=state_store.CLOSE_REASON_USER_CANCEL,
            reasoning=reason or "user cancel",
        )

        return SessionSettleResult(
            session=settled_session,
            drafts=settled_drafts,
        )
```

## 6.3 手动触发维护（调试用）

```python
@router.post("/maintenance/run")
def api_run_maintenance():
    """
    手动触发一次维护任务（调试用）。

    生产环境由后台轮询自动执行。
    """
    from .maintenance import run_maintenance_sync

    result = run_maintenance_sync()

    return {
        "status": "ok",
        "marked_expired": result["marked_expired"],
        "settled": result["settled"],
    }
```

---

# 七、新增 `src/maintenance.py`

```python
"""
后台维护任务：
1. 标记过期 session
2. 结算 expired session

这是纯 CPU 工作，不涉及 LLM API。
"""

import logging
from typing import Optional

from . import state_store
from .config import SESSION_TIMEOUT_MINUTES
from .db import get_db


logger = logging.getLogger(__name__)


def run_maintenance_sync(
    conversation_key: Optional[str] = None,
) -> dict:
    """
    执行一次维护任务（同步版本）。

    流程：
    1. 把超时的 active session 标记为 expired；
    2. 结算所有 expired 的 session。

    返回：
        {
            "marked_expired": int,
            "settled": int,
        }
    """
    with get_db() as conn:
        # Step 1: 标记过期
        marked = state_store.mark_expired_sessions(
            conn,
            timeout_minutes=SESSION_TIMEOUT_MINUTES,
            conversation_key=conversation_key,
        )

        # Step 2: 结算
        results = state_store.settle_all_expired_sessions(
            conn,
            close_reason=state_store.CLOSE_REASON_TIMEOUT_POLL,
            reasoning="session expired (poll)",
        )

        settled = len(results)

        if marked > 0 or settled > 0:
            logger.info(
                "Maintenance: marked %d expired, settled %d sessions",
                marked,
                settled,
            )

        return {
            "marked_expired": marked,
            "settled": settled,
        }
```

---

# 八、修改 `main.py`

```python
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api import router
from src.db import init_db
from src.feedback_store import init_feedback_db
from src.maintenance import run_maintenance_sync


logger = logging.getLogger(__name__)

# 轮询间隔（秒）
MAINTENANCE_INTERVAL_SECONDS = 30


async def maintenance_loop() -> None:
    """
    后台轮询任务：
    每隔 MAINTENANCE_INTERVAL_SECONDS 秒执行一次维护。
    """
    while True:
        try:
            result = await asyncio.to_thread(run_maintenance_sync)

            if result["marked_expired"] > 0 or result["settled"] > 0:
                logger.info(
                    "Maintenance loop: marked=%d, settled=%d",
                    result["marked_expired"],
                    result["settled"],
                )

        except Exception:
            logger.exception("Maintenance loop failed")

        await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    init_db()
    init_feedback_db()

    # 启动后台维护任务
    maintenance_task = asyncio.create_task(maintenance_loop())

    logger.info(
        "Maintenance loop started (interval=%ds)",
        MAINTENANCE_INTERVAL_SECONDS,
    )

    yield

    # 关闭后台任务
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Trade Dialogue DST",
    description="多轮交易对话状态追踪与增量 NER 服务",
    version="0.4.0",
    lifespan=lifespan,
)

app.include_router(router, tags=["dst"])


@app.get("/health")
def health():
    return {"status": "ok"}
```

---

# 九、结算逻辑总结

## 9.1 状态机

```
                    ┌─────────────────┐
        create ──►  │     active      │
                    └────────┬────────┘
                             │
              timeout 检测    │    用户主动取消
                             ▼
                    ┌─────────────────┐         ┌──────────────┐
                    │     expired     │         │  cancelled   │
                    └────────┬────────┘         └──────────────┘
                             │                        ▲
                             │ settle                 │
                             ▼                        │
                    ┌─────────────────┐               │
                    │     closed      │───────────────┘
                    └─────────────────┘   （仅用户取消时走这条）
```

## 9.2 结算触发时机

| 触发点 | 时机 | 触发方式 | close_reason |
|---|---|---|---|
| **T1. 新消息触发** | 新消息需要开新 session 时 | `SessionResolver.resolve()` | `new_session` |
| **T2. 轮询触发** | 后台定时扫描 | `maintenance_loop` | `timeout_poll` |
| **T3. 手动触发** | 前端点击"结束会话" | `POST /sessions/{id}/settle` | `manual` |
| **T4. 用户取消** | 用户明确说"取消" | `POST /sessions/{id}/cancel` | `user_cancel` |

## 9.3 `is_complete` 判断位置

```text
Session 上：
    - status: active / expired / closed / cancelled
    - close_reason: new_session / timeout_poll / manual / user_cancel
    - settled_at: 结算时间
    - 没有 is_complete

TradeDraft 上：
    - is_complete: true / false
    - 结算时独立判断每个 draft
```

## 9.4 结算规则

```text
对每个 trade_draft：

1. 检查 REQUIRED_SETTLE_FIELDS 是否都有值

2. 如果所有字段都有值：
   - is_complete = true
   - 将所有 proposed / confirmed 状态的 slot 改成 confirmed
   - 其他状态不动

3. 如果存在字段缺失：
   - is_complete = false
   - 将缺失字段的 slot_status 改成 unknown
   - 其他已有字段状态不动

4. 写回数据库
5. 写入 SETTLE 事件
```

## 9.5 结算后返回示例

```json
{
  "session": {
    "session_id": "session_old",
    "status": "closed",
    "close_reason": "timeout_poll",
    "settled_at": "2026-06-22T10:30:00Z"
  },
  "drafts": [
    {
      "draft_id": "draft_1",
      "asset_name": "24长发",
      "amount": 2000,
      "price": 100.85,
      "is_complete": true,
      "slots": {
        "asset_name": {
          "value": "24长发",
          "status": "confirmed"
        },
        "amount": {
          "value": 2000,
          "status": "confirmed"
        },
        "price": {
          "value": 100.85,
          "status": "confirmed"
        }
      }
    },
    {
      "draft_id": "draft_2",
      "asset_name": "25诚通",
      "amount": 1000,
      "price": null,
      "is_complete": false,
      "slots": {
        "asset_name": {
          "value": "25诚通",
          "status": "confirmed"
        },
        "amount": {
          "value": 1000,
          "status": "confirmed"
        },
        "price": {
          "value": null,
          "status": "unknown"
        }
      }
    }
  ]
}
```

---

# 十、关键设计决策总结

| 决策 | 理由 |
|---|---|
| `is_complete` 放在 `TradeDraft` 上 | 一个 session 内可能有多个 draft，每个 draft 完整性独立 |
| `Session` 只记录 `close_reason` 和 `settled_at` | Session 是协商上下文，不关心具体字段完整性 |
| 引入 `expired` 中间态 | 区分"刚超时"和"刚创建"，轮询任务只扫 `expired` |
| 结算是纯 CPU 工作 | 不涉及 LLM，可以随时安全执行 |
| 四路触发兜底 | 确保每个 session 最终都会进入终态 |
| 幂等设计 | 已经是终态的 session 再次结算直接返回，不重复处理 |

