**system**:You are a helpful assistant about AI & LLM properties.


---
🙋**user**:
---
```
我有多件独立的NER工作要执行，但是是遵循相同的prompt。我是把它们写成一个llm—api-call，还是组成一个batch，还是组成一个并发taskgroup？
```

---
🤖**assistant**:
---

一般建议：**每件 NER 任务单独作为一个 LLM API call，然后用并发 task group / 并发池执行**。  
只有在特定场景下才考虑 **Batch API** 或 **把多条样本合并进一个 prompt**。

---

## 结论先说

如果你的任务是：

- 多个独立样本；
- 每个样本都遵循同一个 NER prompt；
- 每个样本之间不需要共享上下文；
- 你希望结果稳定、可重试、可解析；

那么推荐：

```text
多个独立 API call + 并发执行
```

也就是：

```text
sample_1 -> LLM call 1
sample_2 -> LLM call 2
sample_3 -> LLM call 3
...
```

而不是：

```text
sample_1 + sample_2 + sample_3 -> 一个 LLM call
```

---

# 三种方式对比

## 1. 写成一个 LLM API call

也就是把很多条待抽取文本塞进同一个 prompt，例如：

```text
请对下面多条文本做 NER：

text_1: ...
text_2: ...
text_3: ...

请返回 JSON。
```

### 优点

- 可能减少请求次数；
- 可能减少 prompt 中固定指令部分的重复开销；
- 对非常短的大量文本，可能看起来更省钱。

### 缺点

通常不推荐，因为问题很多：

#### 1. 输出容易错位

模型可能把 `text_1` 的实体放到 `text_2` 上。

#### 2. 容易漏样本

例如输入 50 条，输出只返回 47 条。

#### 3. 错误不隔离

一条样本导致输出格式坏掉，可能影响整批结果。

#### 4. 重试成本高

如果某一条失败，你往往需要重新跑整个大 prompt。

#### 5. 长上下文稳定性下降

即使模型支持很长上下文，也不代表它在长输入下仍能稳定完成大量独立子任务。

#### 6. 难以做质量监控

你很难判断是哪一条文本导致模型输出异常。

### 适用场景

只有在这些情况下才可以考虑合并成一个 call：

- 每条文本非常短；
- 批量大小很小，例如 3～10 条；
- 你要求模型严格返回 JSON，并能程序化校验；
- 你能接受偶尔漏条或错位；
- 你更关注成本而不是稳定性。

例如：

```text
一次处理 5 条短文本
```

可以考虑。

但如果是正式生产环境，通常还是更推荐独立调用。

---

## 2. 组成 Batch

这里要区分两个概念：

### Batch API

很多 LLM API 提供 batch 功能，比如你一次性提交很多请求：

```text
request_1
request_2
request_3
...
```

平台后台异步处理，稍后返回结果。

这和你把多条任务塞进一个 prompt 不是一回事。

Batch API 本质上仍然是：

```text
一个样本对应一个请求
```

只是平台帮你异步批量执行。

---

### Batch 的优点

- 适合大规模离线任务；
- 通常有价格折扣；
- 不占用实时并发；
- 适合夜间任务、数据标注、批量抽取；
- 对大量任务更友好。

### Batch 的缺点

- 延迟高；
- 不适合实时接口；
- 不适合用户等待响应的场景；
- 调试和重试机制依赖平台；
- 结果不是立即返回。

### 适用场景

如果你有：

```text
几万条、几十万条 NER 数据
```

并且不要求马上出结果，例如：

- 离线数据标注；
- 构建训练集；
- 历史数据回刷；
- 批量知识抽取；
- 后台定时任务；

那么可以用 Batch API。

---

## 3. 组成并发 TaskGroup

也就是为每个样本创建独立任务，然后并发执行：

```text
task_1 = call_llm(sample_1)
task_2 = call_llm(sample_2)
task_3 = call_llm(sample_3)

await asyncio.gather(task_1, task_2, task_3)
```

或者使用 Python 的 `asyncio.TaskGroup`。

### 优点

这是大多数实时或半实时场景下的最佳选择。

#### 1. 任务隔离

每个样本独立请求，一条失败不影响其他条。

#### 2. 容易重试

某一条失败，只需要重试那一条。

#### 3. 输出更稳定

每次只处理一条文本，模型任务更简单。

#### 4. 更容易结构化解析

每次返回一个样本的 JSON，schema 更简单。

#### 5. 容易限流

可以用 semaphore 控制并发数。

#### 6. 容易做缓存

相同文本可以缓存结果，避免重复调用。

#### 7. 容易追踪质量

每条样本都有独立 request、response、latency、error 信息。

---

### 缺点

- 需要自己处理并发、限流、重试；
- 请求次数更多；
- 可能更容易触发 rate limit；
- 如果没有做好控制，可能瞬时压力过大。

但这些通常都可以通过工程手段解决。

---

# 推荐默认方案

## 默认推荐：独立调用 + 并发 TaskGroup

适合：

- 在线服务；
- 用户触发任务；
- 需要较快返回；
- 需要稳定结构化输出；
- 需要失败重试；
- 需要追踪每条样本结果。

架构如下：

```text
输入样本列表
    |
    v
任务队列 / TaskGroup
    |
    v
并发控制器，例如 semaphore
    |
    v
每个样本一个 LLM API call
    |
    v
结果校验
    |
    v
失败重试
    |
    v
结果聚合
```

---

# 如何选择？

可以用下面的决策方式。

---

## 情况一：你需要实时结果

选择：

```text
并发 TaskGroup，每个样本一个 API call
```

例如：

```text
用户上传 20 条文本，希望几秒到几十秒内拿到 NER 结果
```

不要用一个超大 prompt。

---

## 情况二：你有大量离线数据

选择：

```text
Batch API
```

例如：

```text
10 万条历史文本，今晚跑完即可
```

如果 LLM 提供商支持 batch，并且有折扣，优先考虑 batch。

---

## 情况三：数据量不大，但非常短

可以考虑：

```text
小批量合并进一个 prompt
```

例如：

```text
一次处理 5 条短评论
```

但要非常谨慎，必须做输出校验。

---

## 情况四：你在做生产级 NER pipeline

优先选择：

```text
每个样本独立 API call + 并发执行 + 结构化输出 + 重试
```

这是最稳的。

---

# 为什么不建议一个 prompt 处理很多独立 NER 任务？

因为 NER 本质上是：

```text
输入一段文本 -> 输出该文本中的实体
```

这是一个典型的**样本级任务**。

如果多个样本之间没有依赖关系，模型并不需要看到其他样本。

把多个样本塞进一个 prompt，相当于人为增加任务复杂度：

```text
原本：
识别这句话里的实体

变成：
识别这 50 句话里的实体，并且不要混淆、不要漏、不要错序、还要输出合法 JSON
```

这对模型来说更难。

尤其是当你要求输出复杂 JSON 时，例如：

```json
[
  {
    "id": "text_1",
    "entities": [
      {
        "text": "张三",
        "type": "PERSON",
        "start": 0,
        "end": 2
      }
    ]
  }
]
```

合并多条样本时，模型更容易出现：

```text
id 对应错误
entities 丢失
start/end 错位
JSON 截断
某条样本被跳过
```

---

# 并发执行时要注意什么？

如果使用并发 TaskGroup，不建议无限制并发。

例如不要直接：

```python
await asyncio.gather(*all_tasks)
```

如果你有 10000 条数据，这样可能瞬间打爆 API。

应该加限流。

---

## 推荐模式：Semaphore + TaskGroup

核心思想：

```text
限制同时运行的请求数
```

例如同时最多 10 个请求。

伪代码：

```python
import asyncio
import httpx

semaphore = asyncio.Semaphore(10)

async def ner_one(text: str):
    async with semaphore:
        for attempt in range(3):
            try:
                result = await call_llm_for_ner(text)
                return parse_result(result)
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

async def main(texts: list[str]):
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(ner_one(text))
            for text in texts
        ]

    return [task.result() for task in tasks]
```

---

# 结构化输出建议

对于 NER，强烈建议让模型返回严格 JSON。

例如：

```json
{
  "entities": [
    {
      "text": "北京",
      "type": "LOCATION"
    },
    {
      "text": "张伟",
      "type": "PERSON"
    }
  ]
}
```

如果你需要 offset，也可以：

```json
{
  "entities": [
    {
      "text": "北京",
      "type": "LOCATION",
      "start": 0,
      "end": 2
    }
  ]
}
```

但要注意：LLM 对 `start`、`end` 这类字符级 offset 不一定非常可靠。  
如果你需要非常精确的 offset，最好结合规则、字符串匹配或后处理校验。

---

# Prompt 建议

既然所有样本使用相同 prompt，建议把 prompt 分成：

```text
system prompt: NER 规则、实体类型、输出格式
user prompt: 当前样本内容
```

例如：

```text
System:
你是一个命名实体识别系统。
请从用户输入中抽取实体。
只输出 JSON，不要解释。
实体类型包括：PERSON, ORGANIZATION, LOCATION, DATE, PRODUCT。
输出格式：
{
  "entities": [
    {
      "text": "...",
      "type": "..."
    }
  ]
}

User:
2024年3月，张伟在北京加入了星辰科技有限公司。
```

这样比把很多样本塞进一个 user prompt 更清晰。

---

# 如果你非常想合并多个样本，应该怎么做？

如果你因为成本或请求数限制，想合并多个样本，建议遵循以下原则。

---

## 1. 小批量合并

不要一次 100 条。

建议从：

```text
3～10 条
```

开始测试。

如果稳定，再谨慎增加。

---

## 2. 每条样本给稳定 ID

例如：

```json
[
  {
    "id": "doc_1",
    "text": "张伟在北京工作。"
  },
  {
    "id": "doc_2",
    "text": "李雷加入了阿里巴巴。"
  }
]
```

要求模型返回：

```json
[
  {
    "id": "doc_1",
    "entities": [...]
  },
  {
    "id": "doc_2",
    "entities": [...]
  }
]
```

---

## 3. 程序端必须校验

你要检查：

```text
返回数量是否等于输入数量？
每个 id 是否存在？
是否有重复 id？
JSON 是否合法？
entities 类型是否符合枚举？
```

如果校验失败，可以：

```text
降级为逐条调用
```

这是很实用的策略。

---

## 4. 失败时降级为单条调用

例如：

```text
先尝试 10 条一组；
如果某组输出异常；
这 10 条改成 10 个独立请求。
```

这样既可能省成本，又保证稳定性。

---

# 成本角度的细节

很多人想合并成一个 prompt，是为了节省重复指令的 token。

例如每条都重复：

```text
你是 NER 系统。
请抽取 PERSON、ORG、LOCATION。
请输出 JSON。
```

如果你有 10000 条，固定指令重复 10000 次，看起来浪费很多。

但实际要考虑：

```text
合并节省的 token
vs
输出错误导致的重试成本
```

如果合并后经常失败，反而更贵。

另外，很多场景下：

```text
输入 token 不是唯一成本
```

你还要考虑：

- 输出 token；
- 失败重试；
- 人工校验；
- 后处理复杂度；
- 线上故障风险。

所以对于生产系统，稳定性通常比省一点 prompt token 更重要。

---

# Batch 和并发 TaskGroup 的核心区别

这个非常容易混淆。

---

## 一个 prompt 里塞多条任务

这是：

```text
一个 LLM 请求
```

模型一次看到多个样本。

风险是模型混淆、漏掉、输出混乱。

---

## Batch API

这是：

```text
多个独立 LLM 请求打包提交
```

每个样本仍然是独立请求，只是平台异步处理。

适合离线。

---

## 并发 TaskGroup

这是：

```text
多个独立 LLM 请求并发执行
```

每个样本仍然是独立请求，适合实时或近实时。

---

# 推荐决策表

| 场景 | 推荐方式 |
|---|---|
| 实时接口 | 并发 TaskGroup，每条一个请求 |
| 用户等待结果 | 并发 TaskGroup |
| 少量样本 | 并发独立请求 |
| 中大规模离线标注 | Batch API |
| 非常短文本且成本敏感 | 可尝试小批量合并 prompt |
| 需要强稳定性 | 每条独立请求 |
| 需要失败隔离 | 每条独立请求 |
| 需要严格结构化输出 | 每条独立请求 |
| 任务之间完全独立 | 不要合并到一个 prompt |

---

# 我的最终建议

你的场景是：

```text
多件独立 NER 工作
相同 prompt
```

因此最推荐：

```text
每条文本一个独立 LLM API call
用并发 TaskGroup / 异步并发执行
加限流、重试、JSON schema 校验
```

如果你的数据量很大且不要求实时，再改成：

```text
Batch API
```

只有当你明确发现独立调用成本太高，并且样本很短、输出稳定时，才考虑：

```text
小批量合并进一个 prompt
```

---

可以简单记成：

```text
实时：并发独立调用
离线：Batch API
省成本：谨慎小批量合并
生产稳定：不要一个 prompt 塞太多独立任务
```


---
🙋**user**:
---
```
我原先的代码是这样的：
entities = []
# 按照 draft 和 action 逐一解析. drafts之间不作信息共享
for draft, action in zip(drafts, actions):
    this_entities = await extract_ner_entities(draft, action)
    entities.extend( this_entities )
其中 extract_ner_entities 对每个 draft & action 执行本地计算 和 call_llm_api 两个部分。我现在遇到的问题就是 当 draft 和 action 多，这样逐次call使得超时非常严重。
将各个call_llm_api部分独立出来，然后组成taskgroup异步执行，能解决问题吗？我该如何设计呢？
```

---
🤖**assistant**:
---

能，而且通常这是最直接的优化方向。

你现在的问题是：

```python
for draft, action in zip(drafts, actions):
    this_entities = await extract_ner_entities(draft, action)
    entities.extend(this_entities)
```

这是**串行执行**。

如果有 20 个 draft/action，每次 LLM API 平均 3 秒，那么总耗时大约是：

```text
20 * 3s = 60s
```

所以很容易触发超时。

如果改成并发执行，理想情况下总耗时会接近：

```text
max(单次请求耗时) + 少量调度开销
```

比如 20 个请求并发跑，每个 3 秒，总耗时可能变成：

```text
3s ~ 6s
```

所以：**把各个 call_llm_api 独立出来，然后组成 TaskGroup 异步执行，是可以显著缓解串行调用导致的超时问题的。**

但要注意：它解决的是“串行等待太慢”的问题，不一定解决以下问题：

1. 单个 LLM 请求本身超时；
2. LLM API 限流；
3. 并发过高导致服务端拒绝；
4. 外层 HTTP 网关整体超时；
5. `call_llm_api` 内部其实是同步阻塞代码；
6. 本地计算本身也很慢。

---

# 推荐设计思路

建议把 `extract_ner_entities` 拆成三层：

```text
1. prepare_request(draft, action)
   本地计算：构造 prompt、整理上下文、生成请求体

2. call_llm_api(request)
   远程调用：请求 LLM，只负责拿到原始响应

3. parse_response(response)
   本地计算：解析 JSON、抽取 entities、做后处理
```

也就是说，把原来的：

```python
this_entities = await extract_ner_entities(draft, action)
```

改成：

```python
request = prepare_request(draft, action)
response = await call_llm_api(request)
this_entities = parse_response(response)
```

然后只对 `call_llm_api` 这部分做并发。

---

# 最推荐的并发模式

## 模式一：每个 draft/action 一个任务 + Semaphore 限流 + TaskGroup

整体结构：

```text
drafts/actions
    ↓
prepare_request 本地计算
    ↓
asyncio.TaskGroup 并发执行
    ↓
Semaphore 控制并发数
    ↓
call_llm_api
    ↓
parse_response
    ↓
按原顺序收集 entities
```

---

# 示例代码

假设你现在有这些函数：

```python
def prepare_ner_request(draft, action):
    # 本地计算
    return {
        "prompt": "...",
        "draft": draft,
        "action": action,
    }

def parse_ner_response(response_text):
    # 解析 LLM 返回
    return [
        {"text": "...", "type": "..."}
    ]

async def call_llm_api_async(request_payload):
    # 真正调用 LLM API
    return response_text
```

那么可以这样写：

```python
import asyncio

# 并发数，不要一开始设太大
MAX_CONCURRENCY = 5

# 单个 LLM 请求超时时间
PER_REQUEST_TIMEOUT = 30

# 最大重试次数
MAX_ATTEMPTS = 3


semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


async def call_llm_api_with_retry(request_payload):
    """
    带限流、超时、重试的 LLM 调用。
    """
    async with semaphore:
        last_exception = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return await asyncio.wait_for(
                    call_llm_api_async(request_payload),
                    timeout=PER_REQUEST_TIMEOUT
                )

            except asyncio.TimeoutError as e:
                last_exception = e
                print(f"LLM timeout, attempt={attempt}")

            except Exception as e:
                last_exception = e
                print(f"LLM error, attempt={attempt}, error={e}")

            # 如果不是最后一次，则退避重试
            if attempt < MAX_ATTEMPTS:
                sleep_time = 2 ** attempt
                await asyncio.sleep(sleep_time)

        raise last_exception


async def extract_one(draft, action):
    """
    处理单个 draft/action。
    """
    # 1. 本地计算：准备请求
    request_payload = prepare_ner_request(draft, action)

    # 2. 远程调用：LLM
    response = await call_llm_api_with_retry(request_payload)

    # 3. 本地计算：解析结果
    entities = parse_ner_response(response)

    return entities


async def extract_all(drafts, actions):
    """
    并发处理所有 draft/action。
    """
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(extract_one(draft, action))
            for draft, action in zip(drafts, actions)
        ]

    entities = []
    for task in tasks:
        entities.extend(task.result())

    return entities
```

调用：

```python
entities = await extract_all(drafts, actions)
```

---

# 如果你需要保留每个结果对应哪个 draft

建议返回带索引的结果。

```python
async def extract_one_with_index(index, draft, action):
    request_payload = prepare_ner_request(draft, action)
    response = await call_llm_api_with_retry(request_payload)
    entities = parse_ner_response(response)
    return index, entities


async def extract_all(drafts, actions):
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(extract_one_with_index(i, draft, action))
            for i, (draft, action) in enumerate(zip(drafts, actions))
        ]

    results = [None] * len(drafts)

    for task in tasks:
        index, entities = task.result()
        results[index] = entities

    flat_entities = []
    for item in results:
        flat_entities.extend(item)

    return flat_entities
```

这样可以保证结果顺序和输入顺序一致。

---

# 如果你不允许一个失败导致整体失败

Python 的 `asyncio.TaskGroup` 有个特点：

> 如果其中一个任务抛出异常，TaskGroup 会取消其他任务，并抛出 ExceptionGroup。

如果你希望某一条失败不影响其他任务，可以在任务内部捕获异常。

```python
async def extract_one_safe(index, draft, action):
    try:
        request_payload = prepare_ner_request(draft, action)
        response = await call_llm_api_with_retry(request_payload)
        entities = parse_ner_response(response)
        return index, entities, None

    except Exception as e:
        return index, [], e


async def extract_all(drafts, actions):
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(extract_one_safe(i, draft, action))
            for i, (draft, action) in enumerate(zip(drafts, actions))
        ]

    results = [None] * len(drafts)
    errors = {}

    for task in tasks:
        index, entities, error = task.result()
        results[index] = entities

        if error is not None:
            errors[index] = error

    flat_entities = []
    for item in results:
        flat_entities.extend(item)

    if errors:
        print(f"失败数量: {len(errors)}")

    return flat_entities, errors
```

然后：

```python
entities, errors = await extract_all(drafts, actions)
```

---

# 如果你还在 Python 3.10 或更早版本

`asyncio.TaskGroup` 是 Python 3.11 引入的。

如果你不能用 `TaskGroup`，可以用 `asyncio.gather`。

```python
async def extract_all(drafts, actions):
    tasks = [
        extract_one_safe(i, draft, action)
        for i, (draft, action) in enumerate(zip(drafts, actions))
    ]

    results = await asyncio.gather(*tasks)

    ordered_entities = [None] * len(drafts)
    errors = {}

    for index, entities, error in results:
        ordered_entities[index] = entities

        if error is not None:
            errors[index] = error

    flat_entities = []
    for item in ordered_entities:
        flat_entities.extend(item)

    return flat_entities, errors
```

如果你希望某个任务失败时不让 `gather` 直接炸掉，记得在 `extract_one_safe` 里捕获异常，或者使用：

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
```

但通常我更推荐自己在任务内部捕获异常，返回统一结构。

---

# 你的 `call_llm_api` 是同步的吗？

这一点非常关键。

如果你现在的 `call_llm_api` 是同步的，例如：

```python
def call_llm_api(request_payload):
    response = requests.post(...)
    return response.json()
```

那么你不能直接把它放进异步并发里：

```python
await call_llm_api(...)
```

因为它不是 `async def`，而且 `requests` 会阻塞事件循环。

这种情况下有两个选择。

---

## 方案一：改成异步 HTTP 客户端

例如用 `httpx.AsyncClient`：

```python
import httpx

client = httpx.AsyncClient(timeout=30)

async def call_llm_api_async(request_payload):
    response = await client.post(
        "https://your-llm-api",
        json=request_payload
    )
    response.raise_for_status()
    return response.json()
```

这是最推荐的方式。

---

## 方案二：把同步调用放到线程池里

如果你暂时不能改底层 SDK，可以这样：

```python
import asyncio

def call_llm_api_sync(request_payload):
    # 同步调用
    return response


async def call_llm_api_async(request_payload):
    return await asyncio.to_thread(call_llm_api_sync, request_payload)
```

然后继续用前面的并发逻辑。

但是注意：

```python
asyncio.to_thread
```

也会受到线程池限制。

如果量很大，仍然要控制并发：

```python
semaphore = asyncio.Semaphore(5)

async def call_llm_api_with_retry(request_payload):
    async with semaphore:
        return await asyncio.to_thread(call_llm_api_sync, request_payload)
```

---

# 本地计算部分需要并发吗？

你的 `extract_ner_entities` 包含两部分：

```text
本地计算
+
call_llm_api
```

如果本地计算很轻，比如只是拼 prompt、构造 JSON，那么不需要特别处理。

直接在任务里同步执行即可：

```python
request_payload = prepare_ner_request(draft, action)
```

但如果本地计算很重，比如：

- 大量文本清洗；
- 复杂规则匹配；
- 向量计算；
- 长文本切分；
- CPU 密集处理；

那么它可能会阻塞事件循环。

这时可以把本地计算放到线程池：

```python
request_payload = await asyncio.to_thread(prepare_ner_request, draft, action)
```

例如：

```python
async def extract_one(index, draft, action):
    request_payload = await asyncio.to_thread(
        prepare_ner_request,
        draft,
        action
    )

    response = await call_llm_api_with_retry(request_payload)

    entities = await asyncio.to_thread(
        parse_ner_response,
        response
    )

    return index, entities
```

不过通常 NER 场景下，瓶颈主要是 LLM API 等待，而不是本地计算。

---

# 并发数应该设多少？

不要一开始就设很大。

建议从：

```python
MAX_CONCURRENCY = 3
```

或者：

```python
MAX_CONCURRENCY = 5
```

开始测试。

如果稳定，再逐步提高：

```text
5 -> 10 -> 20
```

但不要无脑开到 100。

因为 LLM API 通常有：

```text
QPS / RPM / TPM 限制
```

也就是：

- 每秒请求数；
- 每分钟请求数；
- 每分钟 token 数；
- 并发连接数；
- 账号配额。

如果并发太高，会出现：

```text
429 Too Many Requests
```

或者：

```text
大量超时
```

反而更慢。

---

# 推荐参数

可以先用这组保守参数：

```python
MAX_CONCURRENCY = 5
PER_REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 2
```

也就是：

```python
semaphore = asyncio.Semaphore(5)

MAX_ATTEMPTS = 3

sleep_time = 2 ** attempt
```

第一次失败后等：

```text
2s
```

第二次失败后等：

```text
4s
```

第三次失败后抛出异常。

---

# 超时要分两层

你需要区分两种超时。

---

## 1. 单个 LLM 请求超时

比如：

```python
PER_REQUEST_TIMEOUT = 30
```

意思是：

```text
一个 draft/action 的 LLM 调用最多等 30 秒
```

这个必须有。

---

## 2. 整体任务超时

如果你的外层接口有超时限制，比如网关只允许 30 秒，那么即使你并发执行，也可能超时。

例如你有 200 条任务，即使并发 10 条，仍然可能需要：

```text
20 批 * 3 秒 = 60 秒
```

这种情况下，单纯并发不够。

你需要考虑：

```text
后台任务化
```

也就是：

```text
用户提交任务
    ↓
系统返回 task_id
    ↓
后台异步执行
    ↓
用户稍后查询结果
```

例如：

```text
POST /ner/jobs
返回 job_id

GET /ner/jobs/{job_id}
返回状态和结果
```

如果这是 Web API，这点特别重要。

---

# 如果你仍然遇到外层超时

如果你的调用链是：

```text
前端 / 网关 / API Server / LLM
```

而网关有固定超时，比如：

```text
30s
```

那么当任务很多时，即使并发也可能超过 30 秒。

这时建议改成异步任务模式：

```text
1. 接收请求
2. 创建后台任务
3. 立刻返回 job_id
4. 后台并发执行所有 LLM 调用
5. 前端轮询或回调获取结果
```

不要在一个 HTTP 请求里硬等很久。

---

# 也可以分批并发

如果你有几百上千条任务，不建议一次性创建太多任务。

可以分批：

```python
async def extract_all_in_batches(drafts, actions, batch_size=20):
    entities = []

    for start in range(0, len(drafts), batch_size):
        end = start + batch_size

        batch_drafts = drafts[start:end]
        batch_actions = actions[start:end]

        batch_entities = await extract_all(batch_drafts, batch_actions)
        entities.extend(batch_entities)

    return entities
```

这样可以避免：

- 内存占用过高；
- 连接数过多；
- 瞬间打爆 API；
- 一次失败影响太多任务。

---

# 更完整的工程版本

一个比较实用的版本如下：

```python
import asyncio
import random

MAX_CONCURRENCY = 5
PER_REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3

semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


def prepare_ner_request(draft, action):
    return {
        "draft": draft,
        "action": action,
    }


def parse_ner_response(response):
    # 假设 response 里已经有 entities
    return response.get("entities", [])


async def call_llm_api_async(request_payload):
    # 这里替换成你的真实异步 LLM 调用
    ...


async def call_llm_api_with_retry(request_payload):
    async with semaphore:
        last_exception = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return await asyncio.wait_for(
                    call_llm_api_async(request_payload),
                    timeout=PER_REQUEST_TIMEOUT
                )

            except asyncio.TimeoutError as e:
                last_exception = e

            except Exception as e:
                last_exception = e

            if attempt < MAX_ATTEMPTS:
                sleep_time = (2 ** attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(sleep_time)

        raise last_exception


async def extract_one_safe(index, draft, action):
    try:
        request_payload = prepare_ner_request(draft, action)

        response = await call_llm_api_with_retry(request_payload)

        entities = parse_ner_response(response)

        return {
            "index": index,
            "entities": entities,
            "error": None
        }

    except Exception as e:
        return {
            "index": index,
            "entities": [],
            "error": e
        }


async def extract_all(drafts, actions):
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(extract_one_safe(i, draft, action))
            for i, (draft, action) in enumerate(zip(drafts, actions))
        ]

    results = [None] * len(drafts)
    errors = {}

    for task in tasks:
        result = task.result()
        index = result["index"]
        results[index] = result["entities"]

        if result["error"] is not None:
            errors[index] = result["error"]

    flat_entities = []
    for entities in results:
        flat_entities.extend(entities)

    return flat_entities, errors
```

调用：

```python
entities, errors = await extract_all(drafts, actions)
```

---

# 你应该如何改造现有代码？

你现在的代码：

```python
entities = []

for draft, action in zip(drafts, actions):
    this_entities = await extract_ner_entities(draft, action)
    entities.extend(this_entities)
```

可以先改成最小版本：

```python
tasks = [
    extract_ner_entities(draft, action)
    for draft, action in zip(drafts, actions)
]

results = await asyncio.gather(*tasks)

entities = []
for result in results:
    entities.extend(result)
```

如果 `extract_ner_entities` 内部已经是异步的，并且主要耗时在 `await call_llm_api`，这个改动就能明显提速。

但是生产环境建议加限流：

```python
semaphore = asyncio.Semaphore(5)

async def extract_with_limit(draft, action):
    async with semaphore:
        return await extract_ner_entities(draft, action)

tasks = [
    extract_with_limit(draft, action)
    for draft, action in zip(drafts, actions)
]

results = await asyncio.gather(*tasks)
```

如果你想更稳，再逐步加入：

```text
超时
重试
错误捕获
顺序索引
日志
```

---

# 最小改动版

如果你想尽量少改代码，可以这样：

```python
import asyncio

MAX_CONCURRENCY = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

async def extract_with_limit(draft, action):
    async with semaphore:
        try:
            return await asyncio.wait_for(
                extract_ner_entities(draft, action),
                timeout=30
            )
        except Exception as e:
            print(f"extract failed: {e}")
            return []

tasks = [
    extract_with_limit(draft, action)
    for draft, action in zip(drafts, actions)
]

results = await asyncio.gather(*tasks)

entities = []
for result in results:
    entities.extend(result)
```

这个版本适合快速验证。

但长期来看，仍然建议把 `extract_ner_entities` 拆成：

```python
prepare_request()
call_llm_api()
parse_response()
```

---

# 什么时候考虑 Batch？

如果你不是实时等结果，而是离线跑大量数据，比如：

```text
1000 条、10000 条、100000 条
```

并且可以接受：

```text
几分钟、几十分钟、几小时后返回结果
```

那么优先考虑 LLM API 提供商的 Batch API。

Batch 更适合：

- 离线标注；
- 数据回刷；
- 批量 NER；
- 构建训练数据；
- 非实时知识抽取。

如果是在线请求，还是并发独立调用更合适。

---

# 什么时候考虑把多个样本合并进一个 prompt？

只有在下面情况下才考虑：

- 每条文本很短；
- 批量很小，比如 3～10 条；
- 你非常在意请求次数；
- 你能严格校验输出；
- 你允许失败时降级成单条调用。

例如：

```text
一次请求处理 5 条短文本
```

但你的任务如果是：

```python
draft, action
```

而且每个都要独立解析，且结果不能混淆，那么我更建议：

```text
一个 draft/action 一个独立请求
```

不要合并。

---

# 最重要的几个注意点

## 1. 一定要限制并发数

不要这样：

```python
await asyncio.gather(*[call_api(...) for ...])
```

如果你有很多任务，会瞬间发出大量请求。

要这样：

```python
semaphore = asyncio.Semaphore(5)
```

---

## 2. 一定要有单个请求超时

否则某个 LLM 请求卡住，会把整个任务拖死。

```python
await asyncio.wait_for(call_api(...), timeout=30)
```

---

## 3. 一定要重试

LLM API 常见错误：

```text
timeout
connection reset
429
500
502
503
504
```

建议指数退避：

```python
sleep 2s
sleep 4s
sleep 8s
```

---

## 4. 保持结果顺序

用索引：

```python
index, entities
```

或者按任务列表顺序取结果。

---

## 5. 如果 `call_llm_api` 是同步的，必须处理

同步阻塞代码会破坏异步并发。

要么改成异步 HTTP 客户端，要么：

```python
await asyncio.to_thread(sync_call_llm_api, payload)
```

---

# 推荐最终结构

你的最终代码结构可以变成这样：

```python
async def extract_all_entities(drafts, actions):
    results = await run_concurrent_ner_tasks(drafts, actions)
    return flatten_entities(results)


async def run_concurrent_ner_tasks(drafts, actions):
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(
                process_one_ner_task(i, draft, action)
            )
            for i, (draft, action) in enumerate(zip(drafts, actions))
        ]

    return collect_results(tasks)


async def process_one_ner_task(index, draft, action):
    payload = prepare_ner_request(draft, action)
    response = await call_llm_api_with_limit_and_retry(payload)
    entities = parse_ner_response(response)
    return index, entities
```

---

# 简单结论

你的问题适合这样解决：

```text
是，把 call_llm_api 独立出来，用 asyncio.TaskGroup 并发执行。
```

推荐设计：

```text
每个 draft/action 一个任务
每个任务内部：
    prepare_request
    call_llm_api
    parse_response

外部：
    TaskGroup 并发
    Semaphore 限流
    wait_for 超时
    retry 重试
    index 保序
    error catch 隔离失败
```

如果现在是同步串行：

```python
for draft, action in zip(drafts, actions):
    await extract_ner_entities(draft, action)
```

优先改成：

```python
并发调用每个 draft/action 的 LLM 请求
```

这通常能显著减少总耗时。

但如果你的外层 HTTP 请求本身有严格超时，那么进一步要改成：

```text
后台任务 / 异步 job / Batch API
```

而不是让用户请求一直等待所有 LLM 调用完成。


---
🙋**user**:
---
```
对每个draft&action，本来都应该输出对应的entity_list。至少 本地计算部分 和 llm_api_call 部分要对应上：它们都应该是同一个draft&action的处理结果，只不过前者走的是本地计算，后者走的是llm_api_call。
我该如何设计这里的并行和异步？希望你能给我讲透，先别纠结并发数量这种小事。
```

---
🤖**assistant**:
---

要讲透这个问题，我们首先要剥离掉“并发数、重试、超时”这些工程细节，直击**异步与并行设计的本质**。

你现在的核心诉求是：**保证数据严格对应（不串线）**，即每个 `draft & action` 的“本地计算结果”和“LLM API 结果”必须完美绑定，最终输出正确的 `entity_list`。

为了实现这一点，我们需要从**数据流、执行模型、任务封装、结果收集**四个维度来彻底重构你的设计。

---

### 一、 核心设计思想：以“样本”为粒度的任务隔离

要保证不串线，最忌讳的设计是“流水线式”拆分（即：先并发跑完所有本地计算，把结果扔进队列，再并发跑所有 LLM 调用）。这种设计需要维护复杂的 ID 映射，极易出错。

**最优雅、最可靠的设计是：以 `(draft, action)` 为粒度，封装一个“原子任务（Atomic Task）”。**

在原子任务**内部**，严格串行执行：`本地计算 -> LLM调用 -> 结果解析`。
在原子任务**外部**，并发调度多个原子任务。

这样，数据的对应关系在任务创建的那一刻就被**闭包（Closure）** 或**参数**死死绑定了，绝对不可能串线。

---

### 二、 看透执行模型：本地计算 vs LLM 调用

在 Python 的 `asyncio` 模型中，你必须深刻理解“本地计算”和“LLM 调用”的本质区别，这是很多异步代码写成“假并发”的根源。

#### 1. LLM API 调用（网络 I/O 密集型）
- **本质**：发送请求后，CPU 就在干等网络响应。
- **异步表现**：使用 `await`。当执行到 `await call_llm()` 时，当前任务会**让出控制权（Yield）**，事件循环（Event Loop）会去执行其他任务。
- **结论**：完美契合 `asyncio`，是实现高并发的核心。

#### 2. 本地计算（CPU 密集型 或 纯内存操作）
- **本质**：比如复杂的正则匹配、长文本切分、JSON 组装。这需要 CPU 实打实地去算。
- **异步表现**：如果你在 `async def` 里面写了很重的同步本地计算，**它会霸占事件循环（Block the Event Loop）**。此时，其他所有的 `await` 都无法执行，你的“并发”会退化成“串行”。
- **结论**：如果本地计算很轻（几毫秒），直接同步写即可；如果本地计算很重（几十毫秒以上），必须把它**扔到线程池或进程池**中执行，不能阻塞主事件循环。

---

### 三、 架构设计：三层分离模型

基于上述分析，我们将代码设计为三层：

#### 第一层：原子任务层（Worker）
负责处理**单个** `draft & action` 的完整生命周期。保证数据绑定。

#### 第二层：调度层（Dispatcher）
负责创建所有原子任务，并交给事件循环并发执行。

#### 第三层：聚合层（Aggregator）
负责收集结果，并**严格保证输出顺序与输入顺序一致**。

---

### 四、 讲透代码实现

下面是工业级的设计模板，我们逐层剖析。

#### 1. 原子任务层：绑定数据，隔离状态

```python
import asyncio

# 假设这是你的本地计算函数（同步）
def local_compute(draft: str, action: str) -> dict:
    # 模拟复杂的本地计算：拼装 prompt、数据清洗等
    # 注意：这里不要使用任何全局变量来存储中间状态！
    payload = {"prompt": f"Draft: {draft}, Action: {action}"}
    return payload

# 假设这是你的 LLM 调用函数（异步）
async def call_llm_api(payload: dict) -> str:
    # 模拟网络 I/O 等待
    await asyncio.sleep(2) 
    return '{"entities": ["A", "B"]}'

# 假设这是你的解析函数（同步）
def parse_response(raw_response: str) -> list:
    return ["A", "B"]

# 【核心】原子任务：将单个 draft/action 的处理逻辑封装在一起
async def process_single_draft_action(draft: str, action: str) -> list:
    """
    处理单个样本。
    这里的变量全部是局部变量，天然线程/协程安全，绝对不会串线。
    """
    # 1. 本地计算
    # 如果 local_compute 非常耗时（CPU密集），请用：
    # payload = await asyncio.to_thread(local_compute, draft, action)
    # 如果只是轻量级字符串拼接，直接调用即可：
    payload = local_compute(draft, action) 
    
    # 2. LLM API 调用 (让出控制权，实现并发的关键点)
    raw_response = await call_llm_api(payload)
    
    # 3. 结果解析
    entity_list = parse_response(raw_response)
    
    # 4. 返回结果（此时结果已经与当前的 draft/action 牢牢绑定）
    return entity_list
```

**讲透点**：
在这个函数里，`draft`, `action`, `payload`, `raw_response` 都是**局部变量**。无论外部并发多少个这个函数，它们各自操作自己栈帧里的变量，**物理上杜绝了数据串线的可能**。

#### 2. 调度与聚合层：保序并发

```python
async def process_all_drafts_and_actions(drafts: list[str], actions: list[str]) -> list[list]:
    """
    并发调度所有任务，并严格保序收集结果。
    """
    # 1. 创建任务列表（此时任务还未真正开始执行，只是构建了协程对象）
    tasks = [
        process_single_draft_action(draft, action)
        for draft, action in zip(drafts, actions)
    ]
    
    # 2. 并发执行并收集结果
    # 【核心机制】：asyncio.gather 会严格按照 tasks 列表的顺序返回结果！
    # 即使 task_2 比 task_1 先完成，gather 返回的列表中，第二个元素依然是 task_2 的结果。
    # 这就完美解决了“对应上”的问题，不需要手动维护 index。
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 3. 结果后处理（处理可能的异常）
    final_entities = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            # 记录错误，但不中断整体流程，对应位置可以返回空列表或特定标记
            print(f"Task {i} failed with error: {res}")
            final_entities.append([]) 
        else:
            final_entities.append(res)
            
    return final_entities
```

**讲透点**：
很多人为了保序，会去搞一个全局字典 `results_dict[index] = res`，这在异步中是画蛇添足。
`asyncio.gather(*tasks)` 的底层实现保证了：**返回的结果列表顺序，永远与传入的 tasks 列表顺序严格一致**。这是 asyncio 提供的最强契约之一，直接利用它即可。

---

### 五、 深度剖析：如果“本地计算”很重怎么办？

这是实际工程中最容易踩坑的地方。

假设你的 `local_compute` 需要处理 10MB 的文本，做复杂的正则提取，耗时 500ms。
如果你直接像上面那样写：
```python
payload = local_compute(draft, action) # 阻塞 500ms
raw_response = await call_llm_api(payload)
```

**灾难会发生**：
当 Task 1 执行到 `local_compute` 时，整个事件循环被卡死 500ms。在这 500ms 内，Task 2、Task 3 的 `await call_llm_api` 根本无法被触发。你的并发退化成了“串行本地计算 + 并发 LLM 调用”，整体耗时依然很长。

**解决方案：将 CPU 密集型本地计算卸载到线程池。**

```python
async def process_single_draft_action(draft: str, action: str) -> list:
    # 使用 asyncio.to_thread 将同步的 CPU 密集函数扔到后台线程执行
    # 此时主事件循环不会被阻塞，可以去触发其他任务的 LLM 调用
    payload = await asyncio.to_thread(local_compute, draft, action)
    
    # 网络 I/O 依然在主事件循环中异步执行
    raw_response = await call_llm_api(payload)
    
    # 如果 parse_response 也很重，同样扔到线程池
    entity_list = await asyncio.to_thread(parse_response, raw_response)
    
    return entity_list
```

**讲透点**：
- `asyncio` 本身是**单线程**的并发模型，只擅长处理 I/O 等待。
- `asyncio.to_thread` (Python 3.9+) 或 `loop.run_in_executor` 会利用底层的 `ThreadPoolExecutor`。
- 这样设计后：**本地计算在多线程中真正并行（Parallel），LLM 调用在单线程中异步并发（Concurrent）**。这是 Python 异步编程的终极形态。

---

### 六、 总结：如何检验你的设计是否“讲透”了？

你可以用以下 4 个灵魂拷问来检验你的代码：

1. **状态隔离了吗？**
   - 检查：`process_single_draft_action` 内部有没有读写全局变量（如 `global_entities.append()`）？
   - 答案：必须有。所有中间变量必须是局部的，最后通过 `return` 返回。

2. **顺序保证了吗？**
   - 检查：收集结果时，有没有依赖任务完成的先后顺序？
   - 答案：不能依赖。必须使用 `asyncio.gather` 或 `TaskGroup` 的保序特性，按输入索引直接映射。

3. **事件循环阻塞了吗？**
   - 检查：在 `await` 之间的同步代码（本地计算），执行时间是否超过 10ms？
   - 答案：如果超过，必须用 `asyncio.to_thread` 包装，否则会把整个并发拖慢。

4. **异常隔离了吗？**
   - 检查：如果第 3 个 draft 的 LLM 调用报错了，会导致整个 `gather` 崩溃，让前 2 个成功的结果也丢失吗？
   - 答案：不能。必须在 `gather` 中设置 `return_exceptions=True`，或者在原子任务内部用 `try...except` 捕获并返回默认值。

按照这个架构去重构你的代码，你的“本地计算”和“LLM API”就会像齿轮一样完美咬合，既实现了极高的并发效率，又保证了数据 100% 不串线。


---
🙋**user**:
---
```
最后我的代码是这样：
parsed_result = await asyncio.to_thread(local_compute, message, draft, action)
try:
    trade_parties = await llm_api_call(draft.trade_parties)
except Exception:
    trade_parties = local_parse(draft.trade_parties)

return _construct_entities(draft, parsed_result, trade_parties, global_custs_info)

我发现，其实 local_compute 和 llm_api_call 没有依赖关系。这两个可以再并发吗？
```

---
🤖**assistant**:
---

**完全可以，而且这是一个非常高级且正确的优化思路！**

你现在的代码是**串行**的：
```python
# 耗时 T1
parsed_result = await asyncio.to_thread(local_compute, ...) 
# 耗时 T2
trade_parties = await llm_api_call(...) 
```
单个任务的总耗时是 **`T1 + T2`**。

如果把它们并发，单个任务的总耗时就会变成 **`max(T1, T2)`**。这在 LLM 应用中是巨大的性能提升，因为 LLM 调用（T2）通常很慢，而本地计算（T1）可能也需要几百毫秒。

我们将从**代码实现、架构升维、以及隐藏的坑**三个层面，把这种“任务内并发”彻底讲透。

---

### 一、 代码实现：如何优雅地在任务内并发？

在单个 `async def` 函数内部并发两个没有依赖关系的异步操作，最标准的做法是使用 `asyncio.create_task` 或 `asyncio.gather`。

为了保持代码清晰，特别是保留你原有的 `try...except` 降级逻辑，建议将 LLM 调用封装成一个独立的协程：

```python
import asyncio

# 1. 封装带降级逻辑的 LLM 调用
async def fetch_trade_parties_with_fallback(trade_parties_input):
    try:
        # 走 LLM API
        return await llm_api_call(trade_parties_input)
    except Exception as e:
        # 降级走本地解析
        # 注意：如果 local_parse 也是 CPU 密集型（耗时>10ms），请改为：
        # return await asyncio.to_thread(local_parse, trade_parties_input)
        return local_parse(trade_parties_input)

# 2. 在原子任务中实现“微观并发”
async def process_single_draft_action(message, draft, action, global_custs_info):
    
    # 【核心】：使用 create_task 立即将两个任务提交给事件循环
    # 此时它们已经开始并发执行了，不会互相阻塞
    
    # 任务 A：本地计算 (CPU 密集，放入线程池)
    task_local = asyncio.create_task(
        asyncio.to_thread(local_compute, message, draft, action)
    )
    
    # 任务 B：LLM 调用 + 降级逻辑 (I/O 密集，在主事件循环)
    task_llm = asyncio.create_task(
        fetch_trade_parties_with_fallback(draft.trade_parties)
    )
    
    # 【核心】：等待两个任务都完成，并严格保序接收结果
    parsed_result, trade_parties = await asyncio.gather(task_local, task_llm)
    
    # 3. 组装最终结果（此时 parsed_result 和 trade_parties 已经完美对应）
    return _construct_entities(draft, parsed_result, trade_parties, global_custs_info)
```

**讲透点：**
- `asyncio.create_task()` 的作用是**立即调度**。当你写下这两行代码时，`local_compute` 已经被扔进了后台线程，`llm_api_call` 也已经发出了网络请求。
- `await asyncio.gather(...)` 的作用是**同步等待点**。它会挂起当前协程，直到 A 和 B 都完成。即使 A 先完成，它也会等 B 完成后，再按 `(A, B)` 的顺序把结果解包给 `parsed_result` 和 `trade_parties`。**数据绝对不会串线。**

---

### 二、 架构升维：从“一维并发”到“二维并发”

你之前的设计是**一维并发（宏观并发 / Inter-task Concurrency）**：
- 多个 `(draft, action)` 之间并发。

现在的设计升级成了**二维并发（微观+宏观 / Intra-task + Inter-task Concurrency）**：
- **X轴（宏观）**：50 个 `(draft, action)` 在并发。
- **Y轴（微观）**：每个 `(draft, action)` 内部的 `local_compute` 和 `llm_api_call` 也在并发。

**这种设计的威力在于资源利用率的极致化：**
当 Task 1 的 `llm_api_call` 在等待网络响应时，它的事件循环控制权被让出；此时事件循环不仅去执行了 Task 2 的 `llm_api_call`，还顺便把 Task 1 的 `local_compute` 扔给了后台线程去算。**CPU（算本地逻辑）和 网络（等 LLM 响应）在同时满载运行。**

---

### 三、 隐藏的坑：必须警惕的“线程池雪崩”

这是很多高级开发者在引入 `asyncio.to_thread` 后最容易踩的致命坑。

#### 坑在哪里？
`asyncio.to_thread` 底层使用的是 Python 默认的 `ThreadPoolExecutor`。
在 Python 3.9+ 中，默认线程池的大小通常是 `min(32, os.cpu_count() + 4)`。假设你的机器是 8 核，默认线程池大小就是 **12**。

现在你有了“二维并发”：
- 假设外部有 **50 个** `(draft, action)` 在并发（宏观）。
- 每个任务内部都调用了 **1 次** `asyncio.to_thread`（微观）。
- 瞬间，事件循环会向线程池申请 **50 个线程**。

**后果**：
由于线程池只有 12 个线程，剩下的 38 个 `local_compute` 任务会**在线程池队列里排队等待**。
这会导致你的“微观并发”失效，`local_compute` 变成串行执行，整体耗时大幅增加，甚至可能因为排队超时而导致任务失败。

#### 如何解决？（两种方案）

**方案 A：扩大全局线程池（简单粗暴，推荐）**
在程序启动的最开始（如 `main` 函数或初始化阶段），替换掉默认的线程池：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 在程序启动时执行一次
# 将线程池扩大到足以支撑你的宏观并发数，比如 100
custom_executor = ThreadPoolExecutor(max_workers=100)
asyncio.get_running_loop().set_default_executor(custom_executor)

# 之后所有的 asyncio.to_thread 都会使用这个 100 大小的线程池
```

**方案 B：使用 Semaphore 限制 to_thread 的并发（更精细控制）**
如果你不想开太多线程（避免上下文切换开销），可以限制同时执行 `local_compute` 的数量：

```python
# 限制同时只有 10 个 local_compute 在后台线程跑
local_compute_semaphore = asyncio.Semaphore(10)

async def throttled_local_compute(message, draft, action):
    async with local_compute_semaphore:
        return await asyncio.to_thread(local_compute, message, draft, action)

# 在 process_single_draft_action 中：
task_local = asyncio.create_task(
    throttled_local_compute(message, draft, action)
)
```

---

### 四、 最终完美版代码结构

结合我们讲透的所有细节（二维并发、数据隔离、异常降级、线程池防雪崩），你的最终代码应该长这样：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ================= 初始化阶段 =================
# 1. 扩大默认线程池，防止 to_thread 排队雪崩
# 假设你的宏观并发数是 50，这里设为 60 留点余量
_executor = ThreadPoolExecutor(max_workers=60)
# 注意：这行代码必须在事件循环已经启动后执行（比如在 async main 里）

# 2. 宏观并发限流（控制同时处理多少个 draft）
MACRO_CONCURRENCY = 50
macro_semaphore = asyncio.Semaphore(MACRO_CONCURRENCY)


# ================= 任务定义阶段 =================

async def fetch_trade_parties_with_fallback(trade_parties_input):
    """微观任务 B：LLM 调用及降级"""
    try:
        return await llm_api_call(trade_parties_input)
    except Exception:
        # 如果 local_parse 也很慢，请改成 await asyncio.to_thread(local_parse, ...)
        return local_parse(trade_parties_input)

async def process_single_draft_action(message, draft, action, global_custs_info):
    """原子任务：处理单个 draft & action"""
    
    # 宏观限流：控制同时进入这个函数的任务数
    async with macro_semaphore:
        
        # 微观并发：同时启动本地计算和 LLM 调用
        task_local = asyncio.create_task(
            asyncio.to_thread(local_compute, message, draft, action)
        )
        task_llm = asyncio.create_task(
            fetch_trade_parties_with_fallback(draft.trade_parties)
        )
        
        # 等待两者完成，严格保序
        parsed_result, trade_parties = await asyncio.gather(task_local, task_llm)
        
        # 组装结果（局部变量，绝对不串线）
        return _construct_entities(draft, parsed_result, trade_parties, global_custs_info)


# ================= 调度聚合阶段 =================

async def process_all(message_list, drafts, actions, global_custs_info):
    """入口函数：调度所有任务"""
    
    # 确保自定义线程池被应用到当前事件循环
    loop = asyncio.get_running_loop()
    loop.set_default_executor(_executor)

    # 创建所有原子任务
    tasks = [
        process_single_draft_action(msg, draft, act, global_custs_info)
        for msg, draft, act in zip(message_list, drafts, actions)
    ]
    
    # 宏观并发执行并保序收集
    # return_exceptions=True 防止单个 draft 失败导致整个批次崩溃
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 后处理：过滤异常
    final_entities = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            print(f"Task {i} failed: {res}")
            final_entities.append([]) # 或者你的默认错误结构
        else:
            final_entities.append(res)
            
    return final_entities
```

### 总结

1. **可以再并发吗？** 可以。用 `asyncio.create_task` + `asyncio.gather` 实现任务内的微观并发。
2. **数据会串线吗？** 不会。只要坚持“局部变量 + 闭包返回”的原则，宏观和微观怎么并发都不会串线。
3. **最大的风险是什么？** `asyncio.to_thread` 导致的默认线程池耗尽。一定要在程序启动时通过 `set_default_executor` 扩大线程池。

按照这个架构，你的代码不仅逻辑严密、数据绝对安全，而且能把 CPU 和 网络 I/O 的性能压榨到极限。

