**system**:You are a helpful assistant specializing on Python programming & LLM deployment


---
🙋**user**:
---
```
帮我写一个后端Python脚本服务, 预计将使用docker部署. 它的主要工作是:接收关于债券交易的聊天信息相关的消息结构体input, 调取某地址的LLM服务,让大模型完成相关实体抽取,最后按照配置config中的输出模板config.output_schema输出output结构体。
具体信息如下:
请求路径: /api/v1/llm/extract-transaction
请求方法: POST
Content-Type: application/json
请求参数:
字段名|类型|是否必填|描述
input|Object|是|QT平台原始消息结构体
Input.timestamp|String|是|取字段ts后标准化 yyyy/MM/DD HH:mm:ss
input.content|String|是|取字段 content
input.fromCorpName|String|是|取字段 fromCorpName
input.fromName|String|是|取字段 fromName
input.fromOpenID|String|否|取字段 fromOpenID
input.fromQQ|String|是|取字段 fromQQ
input.msgUniqueID|String|是|取字段 msgUniqueID
input.toCorpName|String|是|取字段 toCorpName
input.toGroupName|String|否|取字段 toGroupName
input.toGroupOpenID|String|否|取字段 toGroupOpenID
input.toName|String|是|取字段 toName
input.toOpenID|String|否|取字段 toOpenID
input.toQQ|String|是|取字段 toQQ
input.toQQGroup|String|否|取字段 toQQGroup
request_id|String|否|客户端生成的请求唯一标识,用于链路追踪。
config|Object|否|LLM 推理配置项
config.model_version|String|否|指定模型版本
config.temperature|Float|否|采样温度,范围 O~1
config.output_schema|String|否|输出模板版本.默认v1_standard
v1_standard示例如下:
{
"timestamp":"2026/2/10 10:26:06",   //标准化时间格式(YYYY/MM/DD HH:mm:Ss)
"quote_type":"群聊",                //群聊or私聊
"intent":"",                        //交易意图
"sales_qq":"0123456789",            //销售QQ
"sales_qq":"赵钱",                  //销售名称
"cust_org_name":"xx证券",           //客户所属机构
cust_qq_group":"9876543210",        //客户QQ群号
"cust_group_open_id":"12345",       //客户QQ群id
"cust_group_name":"交易聊天室",      //客户QQ群名
"cust_qq":"0987654321",             //客户QQ or QT账号
"cust_name":"张三",                 //客户联系人
"price_type":"净价",                //价格类型
"cust_trade_price":"0.07",          //收益率
"cust_trade_amount":"1000W",       //客户交易量
"cust_trade_direction":"bid",       //客户交易方向:bid-买入,ofr-卖出
"stock_code":"0000000.IB",         //债券代码
"stock_name":"IB中债0000",         //债券名称
"clear_speed":"T+0",               //清算速度
"trader_name":"孙李",              //对口交易员名称
"remark":"QT聊天室测试",            //备注
"initiator":"我方",                 //报价发起方
}

输出参数:
字段名|类型|描述
code|Integer|业务状态码(200表示成功)
message|String|状态描述
data|Object|业务数据主题
data.task_id|String|服务端生成的任务唯一ID,反馈接口需使用此ID
data.entities|Array of Entity Object|按照config.output_schema输出的结构化实体的列表
data.meta|Object|LLM推理元数据(用于计费和监控)
data.meta.model|String|实际使用的模型版本
data.meta.tokens_used|Integer|消耗的token总数
data.meta.latency_ms|Integer|推理耗时(毫秒)

要求: 生成"后端接收、格式化、编写Prompt、发送LLM服务接口、接收LLM实体抽取结果、格式化输出"这一套流程的框架代码即可, 中间业务相关的具体逻辑不需要写。
```

---
🤖**assistant**:
---

这是一个基于 **FastAPI** 构建的后端服务框架，专为 Docker 部署设计。它包含了完整的请求校验、Prompt 构建、LLM 调用、结果解析及响应封装流程。

### 1. 项目结构

```text
bond-llm-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # 入口文件，定义 API 路由
│   ├── config.py            # 配置管理 (环境变量)
│   ├── models.py            # Pydantic 数据模型 (请求/响应)
│   └── services/
│       ├── __init__.py
│       ├── llm_client.py    # LLM 服务调用逻辑
│       └── prompt_builder.py # Prompt 构建逻辑
├── requirements.txt         # 依赖包
├── Dockerfile               # 容器构建文件
└── .env.example             # 环境变量示例
```

### 2. 代码实现

#### `requirements.txt`
```text
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
httpx==0.26.0
python-dotenv==1.0.0
```

#### `app/config.py`
```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 服务配置
    APP_NAME: str = "Bond LLM Extraction Service"
    DEBUG: bool = False
    
    # LLM 服务配置
    LLM_API_URL: str = "http://llm-internal-service/v1/chat/completions"
    LLM_API_KEY: str = "sk-secret-key"
    LLM_TIMEOUT: int = 30  # 秒
    
    # 默认配置
    DEFAULT_MODEL_VERSION: str = "qwen-max"
    DEFAULT_OUTPUT_SCHEMA: str = "v1_standard"

    class Config:
        env_file = ".env"

settings = Settings()
```

#### `app/models.py`
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# --- 请求模型 ---

class InputMessage(BaseModel):
    timestamp: str = Field(..., description="标准化时间 yyyy/MM/DD HH:mm:ss")
    content: str = Field(..., description="聊天内容")
    fromCorpName: str = Field(..., description="发送方机构")
    fromName: str = Field(..., description="发送方姓名")
    fromOpenID: Optional[str] = Field(None, description="发送方 OpenID")
    fromQQ: str = Field(..., description="发送方 QQ")
    msgUniqueID: str = Field(..., description="消息唯一 ID")
    toCorpName: str = Field(..., description="接收方机构")
    toGroupName: Optional[str] = Field(None, description="接收群名")
    toGroupOpenID: Optional[str] = Field(None, description="接收群 OpenID")
    toName: str = Field(..., description="接收方姓名")
    toOpenID: Optional[str] = Field(None, description="接收方 OpenID")
    toQQ: str = Field(..., description="接收方 QQ")
    toQQGroup: Optional[str] = Field(None, description="接收方 QQ 群号")

class LLMConfig(BaseModel):
    model_version: Optional[str] = Field(None, description="模型版本")
    temperature: Optional[float] = Field(None, ge=0, le=1, description="采样温度")
    output_schema: Optional[str] = Field("v1_standard", description="输出模板版本")

class ExtractionRequest(BaseModel):
    input: InputMessage
    request_id: Optional[str] = Field(None, description="链路追踪 ID")
    config: Optional[LLMConfig] = Field(default_factory=LLMConfig)

# --- 响应模型 ---

class EntityData(BaseModel):
    """
    对应 config.output_schema v1_standard 的结构
    注意：根据实际业务需求，此处字段应严格对应 LLM 输出的 JSON Key
    """
    timestamp: Optional[str] = None
    quote_type: Optional[str] = None
    intent: Optional[str] = None
    sales_qq: Optional[str] = None
    sales_name: Optional[str] = None  # 修正示例中的重复字段
    cust_org_name: Optional[str] = None
    cust_qq_group: Optional[str] = None
    cust_group_open_id: Optional[str] = None
    cust_group_name: Optional[str] = None
    cust_qq: Optional[str] = None
    cust_name: Optional[str] = None
    price_type: Optional[str] = None
    cust_trade_price: Optional[str] = None
    cust_trade_amount: Optional[str] = None
    cust_trade_direction: Optional[str] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    clear_speed: Optional[str] = None
    trader_name: Optional[str] = None
    remark: Optional[str] = None
    initiator: Optional[str] = None

class MetaData(BaseModel):
    model: str
    tokens_used: int
    latency_ms: int

class ResponseData(BaseModel):
    task_id: str
    entities: List[Dict[str, Any]] # 使用 Dict 以兼容不同 schema 版本，或严格使用 List[EntityData]
    meta: MetaData

class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[ResponseData] = None
```

#### `app/services/prompt_builder.py`
```python
from app.models import ExtractionRequest

def build_prompt(request: ExtractionRequest) -> str:
    """
    构建发送给 LLM 的 Prompt。
    此处为框架逻辑，具体的 Prompt 模板需要根据业务效果调优。
    """
    input_data = request.input
    schema_version = request.config.output_schema if request.config else "v1_standard"
    
    # 基础指令
    system_instruction = f"""
    你是一个债券交易助手。请从下方的聊天信息中提取交易实体。
    请严格按照 {schema_version} 模板输出 JSON 格式，不要包含任何 Markdown 标记。
    """
    
    # 构造上下文
    context = f"""
    消息时间：{input_data.timestamp}
    发送人：{input_data.fromName} ({input_data.fromCorpName}) - QQ:{input_data.fromQQ}
    接收人：{input_data.toName} ({input_data.toCorpName}) - QQ:{input_data.toQQ}
    聊天内容：
    {input_data.content}
    """
    
    return f"{system_instruction}\n\n{context}"
```

#### `app/services/llm_client.py`
```python
import httpx
import time
import json
from app.config import settings
from app.models import LLMConfig

class LLMClient:
    def __init__(self):
        self.base_url = settings.LLM_API_URL
        self.api_key = settings.LLM_API_KEY
        self.timeout = settings.LLM_TIMEOUT

    async def extract_entities(self, prompt: str, config: LLMConfig) -> dict:
        """
        调用 LLM 服务进行实体抽取。
        返回：{"result": parsed_json, "meta": {"model": "", "tokens": 0}}
        """
        start_time = time.time()
        
        # 准备 LLM 请求体 (假设是 OpenAI 兼容格式)
        payload = {
            "model": config.model_version or settings.DEFAULT_MODEL_VERSION,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant for bond trading entity extraction."},
                {"role": "user", "content": prompt}
            ],
            "temperature": config.temperature if config.temperature is not None else 0.1,
            "response_format": {"type": "json_object"} # 强制 JSON 输出
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.base_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                resp_json = response.json()
                
                # 解析 LLM 返回
                # 注意：不同 LLM 提供商返回结构不同，此处需适配
                content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                usage = resp_json.get("usage", {})
                model_used = resp_json.get("model", "unknown")
                
                entities = json.loads(content)
                
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                
                return {
                    "entities": entities if isinstance(entities, list) else [entities],
                    "meta": {
                        "model": model_used,
                        "tokens_used": usage.get("total_tokens", 0),
                        "latency_ms": latency_ms
                    }
                }
                
            except httpx.HTTPError as e:
                raise Exception(f"LLM Service Error: {str(e)}")
            except json.JSONDecodeError as e:
                raise Exception(f"LLM Response Parse Error: {str(e)}")

llm_client = LLMClient()
```

#### `app/main.py`
```python
import uuid
import logging
from fastapi import FastAPI, HTTPException
from app.config import settings
from app.models import ExtractionRequest, ApiResponse, ResponseData, MetaData
from app.services.prompt_builder import build_prompt
from app.services.llm_client import llm_client

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

@app.post("/api/v1/llm/extract-transaction", response_model=ApiResponse)
async def extract_transaction(request: ExtractionRequest):
    task_id = str(uuid.uuid4())
    logger.info(f"Task {task_id} started. RequestID: {request.request_id}")
    
    try:
        # 1. 构建 Prompt
        prompt = build_prompt(request)
        
        # 2. 调用 LLM 服务
        llm_result = await llm_client.extract_entities(prompt, request.config or LLMConfig())
        
        # 3. 封装响应
        response_data = ResponseData(
            task_id=task_id,
            entities=llm_result["entities"],
            meta=MetaData(**llm_result["meta"])
        )
        
        logger.info(f"Task {task_id} completed successfully.")
        
        return ApiResponse(
            code=200,
            message="success",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        # 业务异常也返回 200 但 code 字段标识错误，或者返回 HTTP 500
        # 这里按照通用 API 规范，HTTP 状态码 500，但 Body 中保持结构
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### `Dockerfile`
```dockerfile
# 使用 Python 3.11  slim 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量 (防止 Python 生成 pyc 文件，缓冲日志)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY ./app ./app

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### `.env.example`
```bash
LLM_API_URL=http://your-llm-service:8080/v1/chat/completions
LLM_API_KEY=your-secret-key
DEFAULT_MODEL_VERSION=qwen-max
```

### 3. 使用说明

1.  **准备环境**: 确保已安装 Docker 和 Docker Compose。
2.  **配置**: 复制 `.env.example` 为 `.env` 并填写真实的 LLM 服务地址和 Key。
3.  **构建镜像**:
    ```bash
    docker build -t bond-llm-extractor:latest .
    ```
4.  **运行容器**:
    ```bash
    docker run -d -p 8000:8000 --env-file .env bond-llm-extractor:latest
    ```
5.  **测试接口**:
    ```bash
    curl -X POST "http://localhost:8000/api/v1/llm/extract-transaction" \
      -H "Content-Type: application/json" \
      -d '{
        "input": {
          "timestamp": "2026/02/10 10:26:06",
          "content": "出 24 国债 01, 净价 99.5, 量 1000 万，T+0",
          "fromCorpName": "XX 证券",
          "fromName": "赵钱",
          "fromQQ": "0123456789",
          "msgUniqueID": "msg_123",
          "toCorpName": "YY 基金",
          "toName": "孙李",
          "toQQ": "0987654321"
        },
        "config": {
          "output_schema": "v1_standard"
        }
      }'
    ```

### 4. 关键点说明

1.  **异步处理**: 使用 `httpx` 和 `FastAPI` 的 `async/await` 特性，确保在等待 LLM 响应时不阻塞其他请求，提高并发能力。
2.  **数据校验**: 使用 `Pydantic` 严格定义输入输出结构，确保传入 LLM 的数据格式正确，且返回给前端的数据符合接口文档。
3.  **扩展性**:
    *   `prompt_builder.py` 独立出来，方便后续针对不同 `output_schema` 版本编写不同的 Prompt 模板。
    *   `llm_client.py` 封装了 HTTP 细节，如果后续更换 LLM 提供商（如从 OpenAI 协议换成私有协议），只需修改此文件。
4.  **监控元数据**: `meta` 字段中记录了 `tokens_used` 和 `latency_ms`，这对于后续的成本核算和性能监控至关重要。
5.  **容错**: 增加了 `try-except` 块捕获 LLM 调用异常，并记录日志，防止服务因单次 LLM 超时导致崩溃。


---
🙋**user**:
---
```
你在LLMClient中payload.messages中给role system写了{"role": "system", "content": "You are a helpful assistant for bond trading entity extraction."},同时又在prompt_builder中写了system_instruction加在了{"role": "user", "content": prompt}的prompt里。这是怎么回事？为什么在不同地方写了两条system prompt
```

---
🤖**assistant**:
---

你说得非常对！这是一个**设计上的不一致**，是我的疏忽。让我解释一下原因并给出修正方案。

## 问题分析

| 位置 | 内容 | Role | 问题 |
|------|------|------|------|
| `llm_client.py` | "You are a helpful assistant..." | `system` | 通用系统指令 |
| `prompt_builder.py` | "你是一个债券交易助手..." | `user` (嵌入在 prompt 中) | 业务系统指令 |

**这会导致：**
1. **指令冲突**：两条 system 指令可能互相干扰
2. **优先级混乱**：不同模型对多条 system 指令的处理方式不同
3. **维护困难**：系统指令分散在两个地方

## 修正方案

### 方案一：统一使用 `system` role（推荐）

将完整的系统指令放在 `messages` 的 `system` 字段中，`prompt_builder` 只负责构建用户输入内容。

#### 修正后的 `prompt_builder.py`
```python
from app.models import ExtractionRequest

def build_system_prompt(schema_version: str) -> str:
    """
    构建系统指令 - 只放在 system role 中
    """
    return f"""
你是一个债券交易助手。请从聊天信息中提取交易实体。
请严格按照 {schema_version} 模板输出 JSON 格式，不要包含任何 Markdown 标记。
如果某些字段无法从聊天内容中识别，请返回 null 或空字符串。
确保输出是有效的 JSON，可以直接被解析。
"""

def build_user_prompt(request: ExtractionRequest) -> str:
    """
    构建用户输入内容 - 只包含业务数据
    """
    input_data = request.input
    
    context = f"""
消息时间：{input_data.timestamp}
发送人：{input_data.fromName} ({input_data.fromCorpName}) - QQ:{input_data.fromQQ}
接收人：{input_data.toName} ({input_data.toCorpName}) - QQ:{input_data.toQQ}
聊天内容：
{input_data.content}
"""
    return context

def build_messages(request: ExtractionRequest) -> list:
    """
    构建完整的 messages 列表
    """
    schema_version = request.config.output_schema if request.config else "v1_standard"
    
    return [
        {"role": "system", "content": build_system_prompt(schema_version)},
        {"role": "user", "content": build_user_prompt(request)}
    ]
```

#### 修正后的 `llm_client.py`
```python
async def extract_entities(self, messages: list, config: LLMConfig) -> dict:
    """
    调用 LLM 服务进行实体抽取。
    参数 messages 已经包含 system 和 user 角色
    """
    start_time = time.time()
    
    payload = {
        "model": config.model_version or settings.DEFAULT_MODEL_VERSION,
        "messages": messages,  # 直接使用构建好的 messages
        "temperature": config.temperature if config.temperature is not None else 0.1,
        "response_format": {"type": "json_object"}
    }
    
    # ... 其余代码不变
```

#### 修正后的 `main.py`
```python
@app.post("/api/v1/llm/extract-transaction", response_model=ApiResponse)
async def extract_transaction(request: ExtractionRequest):
    task_id = str(uuid.uuid4())
    logger.info(f"Task {task_id} started. RequestID: {request.request_id}")
    
    try:
        # 1. 构建完整的 messages (包含 system 和 user)
        from app.services.prompt_builder import build_messages
        messages = build_messages(request)
        
        # 2. 调用 LLM 服务
        llm_result = await llm_client.extract_entities(messages, request.config or LLMConfig())
        
        # ... 其余代码不变
```

### 方案二：为什么有时会看到两种方式混用？

| 场景 | 原因 | 建议 |
|------|------|------|
| 旧版 API 不支持 system role | 如早期 GPT-3 API | 把 system 指令放在 user prompt 开头 |
| 某些模型忽略 system role | 部分开源模型 | 需要测试具体模型行为 |
| 动态切换系统指令 | 需要运行时调整 | 放在 user prompt 更灵活 |

### 架构对比图

```
❌ 错误设计（当前代码）
┌─────────────────────────────────────────┐
│  llm_client.py                          │
│  messages = [{"role": "system", ...}]   │  ← system 指令 1
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  prompt_builder.py                      │
│  prompt = "system_instruction + data"   │  ← system 指令 2 (在 user 里)
└─────────────────────────────────────────┘

✅ 正确设计（修正后）
┌─────────────────────────────────────────┐
│  prompt_builder.py                      │
│  build_messages()                       │
│    ├─ {"role": "system", ...}          │  ← 唯一的 system 指令
│    └─ {"role": "user", ...}            │  ← 只有业务数据
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  llm_client.py                          │
│  直接使用 messages，不再修改            │
└─────────────────────────────────────────┘
```

## 总结

| 原则 | 说明 |
|------|------|
| **单一职责** | `prompt_builder` 负责构建完整消息，`llm_client` 负责发送请求 |
| **统一管理** | 所有 system 指令集中在一个地方维护 |
| **符合规范** | 遵循 OpenAI 等多数 LLM API 的标准格式 |

感谢你的细心发现！这确实是代码审查中应该抓住的典型问题。修正后的代码会更清晰、更易维护。


---
🙋**user**:
---
```
问题1: 你在app/config.py中写的Settings, 又写了LLM_API_URL/LLM_API_KEY等，然后又写了Config: env_file='.env'。那我到底是在哪里配置API_URL和API_KEY呢？然后你Settings内部的DEFAULT_OUTPUT_SCHEMA也没用上啊
问题2: 实际上我没看到默认模板v1_standard的具体配置，你反而是根据v1_standard写死了EntityData。但我的本意是v1_standard只是output_schema未提供时的模板而已，EntityData的结构应该与output_schema相同，也就是output_schema未提供时，EntityData才应该与v1_standard相同。我觉得这里有点问题
```

---
🤖**assistant**:
---

你提的两个问题非常关键！让我逐一修正。

## 问题 1: 配置优先级与实际使用

### 配置优先级说明

```
环境变量 (OS) > .env 文件 > 代码默认值
```

**正确配置方式**：

| 位置 | 用途 | 示例 |
|------|------|------|
| `app/config.py` | 定义配置项 + 默认值 | 开发/测试默认值 |
| `.env` 文件 | 生产环境实际配置 | Docker 部署时使用 |
| 系统环境变量 | 最高优先级 | K8s/云平台注入 |

### 修正后的 `app/config.py`

```python
import os
from pydantic_settings import BaseSettings
from typing import Dict, List

class Settings(BaseSettings):
    # ==================== 服务配置 ====================
    APP_NAME: str = "Bond LLM Extraction Service"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ==================== LLM 服务配置 ====================
    LLM_API_URL: str = "http://llm-internal-service:8080/v1/chat/completions"
    LLM_API_KEY: str = "sk-default-key-change-me"
    LLM_TIMEOUT: int = 30
    
    # ==================== 默认推理配置 ====================
    DEFAULT_MODEL_VERSION: str = "qwen-max"
    DEFAULT_TEMPERATURE: float = 0.1
    DEFAULT_OUTPUT_SCHEMA: str = "v1_standard"  # ✅ 这里定义，下面会使用
    
    # ==================== Schema 模板配置 ====================
    # 定义不同 output_schema 版本对应的字段说明（用于 Prompt 构建）
    OUTPUT_SCHEMA_TEMPLATES: Dict[str, List[str]] = {
        "v1_standard": [
            "timestamp", "quote_type", "intent", "sales_qq", "sales_name",
            "cust_org_name", "cust_qq_group", "cust_group_open_id", "cust_group_name",
            "cust_qq", "cust_name", "price_type", "cust_trade_price",
            "cust_trade_amount", "cust_trade_direction", "stock_code",
            "stock_name", "clear_speed", "trader_name", "remark", "initiator"
        ],
        # 未来可扩展 v2_enhanced 等版本
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False  # 环境变量不区分大小写

settings = Settings()

# ✅ 验证 DEFAULT_OUTPUT_SCHEMA 是否在模板中
if settings.DEFAULT_OUTPUT_SCHEMA not in settings.OUTPUT_SCHEMA_TEMPLATES:
    raise ValueError(
        f"DEFAULT_OUTPUT_SCHEMA '{settings.DEFAULT_OUTPUT_SCHEMA}' not found in templates. "
        f"Available: {list(settings.OUTPUT_SCHEMA_TEMPLATES.keys())}"
    )
```

### 修正后的 `.env` 文件（生产环境配置）

```bash
# .env
APP_NAME=Bond LLM Extraction Service
DEBUG=false

# LLM 服务配置（Docker 网络中使用服务名）
LLM_API_URL=http://llm-service:8080/v1/chat/completions
LLM_API_KEY=sk-prod-secret-key-xxxxx
LLM_TIMEOUT=60

# 默认推理配置
DEFAULT_MODEL_VERSION=qwen-max
DEFAULT_TEMPERATURE=0.1
DEFAULT_OUTPUT_SCHEMA=v1_standard
```

### 使用示例

```python
from app.config import settings

# 代码中直接使用（会自动从 .env 或环境变量读取）
print(settings.LLM_API_URL)           # 从 .env 读取
print(settings.DEFAULT_OUTPUT_SCHEMA) # 从 .env 读取，默认 "v1_standard"
print(settings.OUTPUT_SCHEMA_TEMPLATES["v1_standard"]) # 获取字段列表
```

---

## 问题 2: EntityData 动态适配 output_schema

你的理解完全正确！`EntityData` 不应该写死为 `v1_standard`，而应该根据 `config.output_schema` 动态适配。

### 修正方案：使用 `Dict[str, Any]` + Schema 元数据

#### 修正后的 `app/models.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# ==================== 请求模型 ====================

class InputMessage(BaseModel):
    timestamp: str = Field(..., description="标准化时间 yyyy/MM/DD HH:mm:ss")
    content: str = Field(..., description="聊天内容")
    fromCorpName: str = Field(..., description="发送方机构")
    fromName: str = Field(..., description="发送方姓名")
    fromOpenID: Optional[str] = Field(None, description="发送方 OpenID")
    fromQQ: str = Field(..., description="发送方 QQ")
    msgUniqueID: str = Field(..., description="消息唯一 ID")
    toCorpName: str = Field(..., description="接收方机构")
    toGroupName: Optional[str] = Field(None, description="接收群名")
    toGroupOpenID: Optional[str] = Field(None, description="接收群 OpenID")
    toName: str = Field(..., description="接收方姓名")
    toOpenID: Optional[str] = Field(None, description="接收方 OpenID")
    toQQ: str = Field(..., description="接收方 QQ")
    toQQGroup: Optional[str] = Field(None, description="接收方 QQ 群号")

class LLMConfig(BaseModel):
    model_version: Optional[str] = Field(None, description="模型版本")
    temperature: Optional[float] = Field(None, ge=0, le=1, description="采样温度")
    output_schema: Optional[str] = Field(None, description="输出模板版本")
    
    def get_effective_schema(self, default_schema: str) -> str:
        """获取实际生效的 output_schema"""
        return self.output_schema if self.output_schema else default_schema

class ExtractionRequest(BaseModel):
    input: InputMessage
    request_id: Optional[str] = Field(None, description="链路追踪 ID")
    config: Optional[LLMConfig] = Field(default_factory=LLMConfig)

# ==================== 响应模型 ====================

class EntityData(BaseModel):
    """
    动态实体数据 - 使用 Dict 适配不同 output_schema 版本
    具体字段由 config.output_schema 决定
    """
    class Config:
        extra = "allow"  # ✅ 允许额外字段，适配不同 schema 版本

class MetaData(BaseModel):
    model: str
    tokens_used: int
    latency_ms: int
    output_schema: str  # ✅ 记录实际使用的 schema 版本

class ResponseData(BaseModel):
    task_id: str
    entities: List[Dict[str, Any]]  # ✅ 使用 Dict 保持灵活性
    meta: MetaData

class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[ResponseData] = None
```

#### 修正后的 `app/services/prompt_builder.py`

```python
from app.models import ExtractionRequest
from app.config import settings

def build_system_prompt(schema_version: str) -> str:
    """
    根据 output_schema 版本构建系统指令
    """
    # 获取该 schema 版本的字段列表
    schema_fields = settings.OUTPUT_SCHEMA_TEMPLATES.get(
        schema_version, 
        settings.OUTPUT_SCHEMA_TEMPLATES[settings.DEFAULT_OUTPUT_SCHEMA]
    )
    
    fields_str = ", ".join(schema_fields)
    
    return f"""
你是一个债券交易助手。请从聊天信息中提取交易实体。

输出要求：
1. 严格按照 {schema_version} 模板输出 JSON 格式
2. 需要包含的字段：{fields_str}
3. 不要包含任何 Markdown 标记（如 ```json）
4. 如果某些字段无法从聊天内容中识别，请返回 null 或空字符串
5. 确保输出是有效的 JSON，可以直接被解析

{schema_version} 模板示例：
{{
    "timestamp": "2026/02/10 10:26:06",
    "quote_type": "群聊",
    "intent": "",
    "sales_qq": "0123456789",
    "sales_name": "赵钱",
    "cust_org_name": "xx 证券",
    ...
}}
"""

def build_user_prompt(request: ExtractionRequest) -> str:
    """
    构建用户输入内容 - 只包含业务数据
    """
    input_data = request.input
    
    context = f"""
消息时间：{input_data.timestamp}
发送人：{input_data.fromName} ({input_data.fromCorpName}) - QQ:{input_data.fromQQ}
接收人：{input_data.toName} ({input_data.toCorpName}) - QQ:{input_data.toQQ}
聊天内容：
{input_data.content}
"""
    return context

def build_messages(request: ExtractionRequest) -> list:
    """
    构建完整的 messages 列表（包含 system 和 user）
    """
    # ✅ 使用配置中的默认值
    effective_schema = request.config.get_effective_schema(
        settings.DEFAULT_OUTPUT_SCHEMA
    )
    
    return [
        {"role": "system", "content": build_system_prompt(effective_schema)},
        {"role": "user", "content": build_user_prompt(request)}
    ]
```

#### 修正后的 `app/main.py`

```python
import uuid
import logging
from fastapi import FastAPI, HTTPException
from app.config import settings
from app.models import (
    ExtractionRequest, ApiResponse, ResponseData, MetaData, LLMConfig
)
from app.services.prompt_builder import build_messages
from app.services.llm_client import llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

@app.post("/api/v1/llm/extract-transaction", response_model=ApiResponse)
async def extract_transaction(request: ExtractionRequest):
    task_id = str(uuid.uuid4())
    logger.info(f"Task {task_id} started. RequestID: {request.request_id}")
    
    try:
        # ✅ 获取实际生效的 output_schema
        effective_schema = request.config.get_effective_schema(
            settings.DEFAULT_OUTPUT_SCHEMA
        ) if request.config else settings.DEFAULT_OUTPUT_SCHEMA
        
        logger.info(f"Using output_schema: {effective_schema}")
        
        # 1. 构建完整的 messages (包含 system 和 user)
        messages = build_messages(request)
        
        # 2. 调用 LLM 服务
        llm_result = await llm_client.extract_entities(
            messages, 
            request.config or LLMConfig(),
            effective_schema  # ✅ 传入 schema 版本用于元数据
        )
        
        # 3. 封装响应
        response_data = ResponseData(
            task_id=task_id,
            entities=llm_result["entities"],
            meta=MetaData(
                model=llm_result["meta"]["model"],
                tokens_used=llm_result["meta"]["tokens_used"],
                latency_ms=llm_result["meta"]["latency_ms"],
                output_schema=effective_schema  # ✅ 记录使用的 schema 版本
            )
        )
        
        logger.info(f"Task {task_id} completed successfully.")
        
        return ApiResponse(
            code=200,
            message="success",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### 修正后的 `app/services/llm_client.py`

```python
import httpx
import time
import json
from app.config import settings
from app.models import LLMConfig

class LLMClient:
    def __init__(self):
        self.base_url = settings.LLM_API_URL
        self.api_key = settings.LLM_API_KEY
        self.timeout = settings.LLM_TIMEOUT

    async def extract_entities(
        self, 
        messages: list, 
        config: LLMConfig,
        output_schema: str  # ✅ 新增参数
    ) -> dict:
        """
        调用 LLM 服务进行实体抽取
        """
        start_time = time.time()
        
        payload = {
            "model": config.model_version or settings.DEFAULT_MODEL_VERSION,
            "messages": messages,
            "temperature": config.temperature if config.temperature is not None else settings.DEFAULT_TEMPERATURE,
            "response_format": {"type": "json_object"}
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.base_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                resp_json = response.json()
                
                content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                usage = resp_json.get("usage", {})
                model_used = resp_json.get("model", "unknown")
                
                entities = json.loads(content)
                
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                
                return {
                    "entities": entities if isinstance(entities, list) else [entities],
                    "meta": {
                        "model": model_used,
                        "tokens_used": usage.get("total_tokens", 0),
                        "latency_ms": latency_ms,
                        "output_schema": output_schema  # ✅ 传递 schema 版本
                    }
                }
                
            except httpx.HTTPError as e:
                raise Exception(f"LLM Service Error: {str(e)}")
            except json.JSONDecodeError as e:
                raise Exception(f"LLM Response Parse Error: {str(e)}")

llm_client = LLMClient()
```

---

## 修正后的架构对比

```
┌─────────────────────────────────────────────────────────────┐
│  app/config.py                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ OUTPUT_SCHEMA_TEMPLATES = {                         │   │
│  │     "v1_standard": [fields...],                     │   │
│  │     "v2_enhanced": [fields...]  ← 可扩展            │   │
│  │ }                                                   │   │
│  │ DEFAULT_OUTPUT_SCHEMA = "v1_standard"               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  app/main.py                                                │
│  effective_schema = config.output_schema or DEFAULT         │
│  ↓ 传递给 prompt_builder 和 llm_client                      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  app/services/prompt_builder.py                             │
│  system_prompt = 根据 effective_schema 动态生成             │
│  (包含对应版本的字段列表和示例)                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  app/models.py                                              │
│  EntityData: extra="allow"  ← 允许任意字段                  │
│  MetaData.output_schema: 记录实际使用的版本                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 使用示例

### 场景 1: 不指定 output_schema（使用默认）

```json
{
  "input": { ... },
  "config": {}
}
```
→ 使用 `v1_standard`，响应中 `meta.output_schema: "v1_standard"`

### 场景 2: 指定 output_schema

```json
{
  "input": { ... },
  "config": {
    "output_schema": "v2_enhanced"
  }
}
```
→ 使用 `v2_enhanced`，响应中 `meta.output_schema: "v2_enhanced"`

### 场景 3: 扩展新 schema 版本

```python
# app/config.py
OUTPUT_SCHEMA_TEMPLATES = {
    "v1_standard": [...],
    "v2_enhanced": [...],
    "v3_minimal": [...]  # 新增版本
}
```

无需修改其他代码，自动生效！

---

## 总结

| 问题 | 修正方案 |
|------|----------|
| 配置位置不清晰 | 明确优先级：环境变量 > .env > 代码默认值 |
| DEFAULT_OUTPUT_SCHEMA 未使用 | 在 `main.py` 和 `prompt_builder` 中实际使用 |
| EntityData 写死 | 使用 `Dict[str, Any]` + `extra="allow"` 动态适配 |
| Schema 版本不可扩展 | 在 `config.py` 中集中管理模板，支持新增版本 |
| 响应中无 schema 信息 | `MetaData` 增加 `output_schema` 字段 |

这样修改后，配置更清晰，架构更灵活，支持多版本 schema 扩展！


---
🙋**user**:
---
```
我可能懂app/config.py里的Settings和.env的关系了: BaseSettings基本类保证, 当没有.env文件时, 起作用的是Settings类变量LLM_API_URL等, 但是当有.env文件时，.env文件内配置的变量会覆盖掉Settings类的类变量。我理解地对吗？
```

---
🤖**assistant**:
---

你的理解**基本正确**，但有几个关键细节需要澄清，这样你在实际使用中会更有把握。

## 核心机制：优先级链条

```
系统环境变量 (最高)  >  .env 文件  >  代码默认值 (最低)
```

### 准确的理解

| 场景 | 行为 | 示例 |
|------|------|------|
| **没有 .env 文件** | 使用 Settings 类中定义的**默认值** | `LLM_API_URL = "http://default:8080"` |
| **有 .env 文件** | .env 中的值**优先于**代码默认值 | `.env` 中 `LLM_API_URL=http://prod:8080` 会生效 |
| **有系统环境变量** | 系统环境变量**优先于** .env 文件 | `export LLM_API_URL=http://env:8080` 会生效 |

### 关键澄清点

**❌ 不准确的说法**：".env 文件覆盖掉 Settings 类的类变量"

**✅ 准确的说法**：`BaseSettings` 在**实例化时**按照优先级读取配置，然后赋值给**实例属性**。类变量本身是**默认值**，不会被修改。

```python
# app/config.py
class Settings(BaseSettings):
    LLM_API_URL: str = "http://default:8080"  # 这是默认值
    class Config:
        env_file = ".env"

settings = Settings()  # 实例化时读取配置
```

```python
# 验证类变量 vs 实例属性
from app.config import Settings, settings

print(Settings.LLM_API_URL)   # 永远是 "http://default:8080" (类默认值)
print(settings.LLM_API_URL)   # 根据 .env 或环境变量动态决定 (实例值)
```

## 实际验证示例

### 测试 1: 没有 .env 文件

```bash
# 删除 .env 文件
rm .env

# 运行 Python
python -c "from app.config import settings; print(settings.LLM_API_URL)"
# 输出：http://default:8080  ← 使用代码默认值
```

### 测试 2: 有 .env 文件

```bash
# 创建 .env 文件
echo "LLM_API_URL=http://from-env-file:8080" > .env

# 运行 Python
python -c "from app.config import settings; print(settings.LLM_API_URL)"
# 输出：http://from-env-file:8080  ← .env 文件生效
```

### 测试 3: 系统环境变量优先级最高

```bash
# 同时有 .env 和系统环境变量
echo "LLM_API_URL=http://from-env-file:8080" > .env
export LLM_API_URL=http://from-system-env:8080

# 运行 Python
python -c "from app.config import settings; print(settings.LLM_API_URL)"
# 输出：http://from-system-env:8080  ← 系统环境变量优先级最高
```

## 优先级验证表

| 配置来源 | 设置方式 | 优先级 | 使用场景 |
|----------|----------|--------|----------|
| 系统环境变量 | `export LLM_API_URL=xxx` 或 K8s ConfigMap | ⭐⭐⭐ 最高 | 生产环境、CI/CD、云平台 |
| .env 文件 | `LLM_API_URL=xxx` 在项目中 | ⭐⭐ 中等 | 本地开发、Docker 本地测试 |
| 代码默认值 | `LLM_API_URL: str = "default"` | ⭐ 最低 | 兜底值、开发便利 |

## Docker 部署时的典型配置

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# .env 文件通常不打包进镜像（通过 .dockerignore 排除）
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  bond-llm-service:
    build: .
    ports:
      - "8000:8000"
    environment:  # ✅ 方式 1: 直接在 compose 中设置环境变量（优先级最高）
      - LLM_API_URL=http://llm-service:8080
      - LLM_API_KEY=sk-secret-key
    # env_file:  # ✅ 方式 2: 使用 .env 文件
    #   - .env
```

## 最佳实践建议

```
┌─────────────────────────────────────────────────────────────┐
│  开发环境                                                   │
│  ├── .env 文件（本地配置，不提交到 git）                    │
│  └── .env.example（模板，提交到 git）                       │
├─────────────────────────────────────────────────────────────┤
│  测试/生产环境                                              │
│  ├── K8s ConfigMap / Secrets                                │
│  ├── 云平台环境变量（AWS Secrets Manager 等）               │
│  └── CI/CD 流水线注入                                       │
├─────────────────────────────────────────────────────────────┤
│  代码默认值                                                 │
│  └── 仅作为兜底，确保服务能启动                             │
└─────────────────────────────────────────────────────────────┘
```

```bash
# .env.example（提交到 git）
LLM_API_URL=http://localhost:8080
LLM_API_KEY=change-me
DEFAULT_MODEL_VERSION=qwen-max

# .env（本地开发，不提交到 git）
LLM_API_URL=http://dev-llm:8080
LLM_API_KEY=sk-dev-secret-key
DEFAULT_MODEL_VERSION=qwen-max
```

```gitignore
# .gitignore
.env
.env.local
*.pyc
__pycache__/
```

## 总结

你的理解 **90% 正确**！只需要记住：

1. **不是"覆盖类变量"**，而是**实例化时按优先级读取**
2. **系统环境变量 > .env 文件 > 代码默认值**
3. **类变量是默认值，实例属性是实际值**

这样在不同环境（本地开发、Docker、K8s、云平台）部署时，你就知道该在哪里配置了！


---
🙋**user**:
---
```
帮我生成一个测试用request脚本。
```

---
🤖**assistant**:
---

## 测试请求脚本

我为你创建了一个完整的测试脚本，包含多种测试场景和清晰的输出。

### `tests/test_api.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
债券交易 LLM 抽取服务 - API 测试脚本
使用方法：python tests/test_api.py
"""

import httpx
import json
import time
from typing import Optional
from datetime import datetime

# ==================== 配置 ====================
BASE_URL = "http://localhost:8000"
API_ENDPOINT = "/api/v1/llm/extract-transaction"
TIMEOUT = 60  # 秒

# ==================== 测试数据 ====================

def get_base_input() -> dict:
    """基础输入数据模板"""
    return {
        "timestamp": "2026/02/10 10:26:06",
        "content": "",  # 测试时填充
        "fromCorpName": "XX 证券股份有限公司",
        "fromName": "赵钱",
        "fromOpenID": "wx_from_openid_123",
        "fromQQ": "0123456789",
        "msgUniqueID": f"msg_{int(time.time())}_{id}",
        "toCorpName": "YY 基金管理有限公司",
        "toGroupName": "债券交易群",
        "toGroupOpenID": "qq_group_openid_456",
        "toName": "孙李",
        "toOpenID": "wx_to_openid_789",
        "toQQ": "0987654321",
        "toQQGroup": "9876543210"
    }

# 测试用例 1: 标准债券交易消息
TEST_CASE_1 = {
    "name": "标准债券交易 - 使用默认 schema",
    "input": {
        **get_base_input(),
        "content": "出 24 国债 01，净价 99.5，量 1000 万，T+0 清算，有意向的私"
    },
    "config": {}  # 使用默认配置
}

# 测试用例 2: 指定 output_schema
TEST_CASE_2 = {
    "name": "标准债券交易 - 指定 v1_standard schema",
    "input": {
        **get_base_input(),
        "content": "收 23 进出 10，全价 101.2，5000 万，bid 方向"
    },
    "config": {
        "output_schema": "v1_standard",
        "model_version": "qwen-max",
        "temperature": 0.1
    }
}

# 测试用例 3: 群聊消息
TEST_CASE_3 = {
    "name": "群聊交易消息",
    "input": {
        **get_base_input(),
        "content": "【报价】24 附息国债 15，代码 240015.IB，收益率 2.35%，量 2 亿，ofr，T+1",
        "toGroupName": "机构交易聊天室",
        "toQQGroup": "123456789"
    },
    "config": {
        "output_schema": "v1_standard"
    }
}

# 测试用例 4: 带 request_id 的链路追踪
TEST_CASE_4 = {
    "name": "带链路追踪 ID",
    "input": {
        **get_base_input(),
        "content": "平盘过 23 国开 05，收益率 2.55%，1 亿"
    },
    "request_id": f"trace_{int(time.time())}_abc123",
    "config": {}
}

# 测试用例 5: 最小化配置（只填必填字段）
TEST_CASE_5 = {
    "name": "最小化输入",
    "input": {
        "timestamp": "2026/02/10 14:30:00",
        "content": "询价 24 农发 01",
        "fromCorpName": "测试证券",
        "fromName": "测试员",
        "fromQQ": "111111111",
        "msgUniqueID": "msg_min_001",
        "toCorpName": "测试基金",
        "toName": "交易员",
        "toQQ": "222222222"
    },
    "config": {}
}

# ==================== 测试函数 ====================

def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_json(title: str, data: dict, max_length: int = 500):
    """格式化打印 JSON"""
    print(f"\n【{title}】")
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    if len(json_str) > max_length:
        print(json_str[:max_length] + "... (内容过长，已截断)")
    else:
        print(json_str)

def run_test(test_case: dict, base_url: str = BASE_URL) -> dict:
    """
    执行单个测试用例
    
    Args:
        test_case: 测试用例字典
        base_url: 服务地址
    
    Returns:
        响应结果字典
    """
    url = f"{base_url}{API_ENDPOINT}"
    
    print_separator(f"测试：{test_case['name']}")
    
    # 打印请求信息
    print_json("请求参数", test_case)
    
    start_time = time.time()
    
    try:
        # 发送请求
        response = httpx.post(
            url,
            json=test_case,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # 打印响应信息
        print(f"\nHTTP 状态码：{response.status_code}")
        print(f"请求耗时：{elapsed_ms} ms")
        
        if response.status_code == 200:
            result = response.json()
            print_json("响应结果", result)
            
            # 验证响应结构
            validate_response(result)
            
            return {"success": True, "data": result, "elapsed_ms": elapsed_ms}
        else:
            print(f"❌ 请求失败：{response.text}")
            return {"success": False, "error": response.text, "elapsed_ms": elapsed_ms}
            
    except httpx.ConnectError as e:
        print(f"❌ 连接错误：{str(e)}")
        print(f"💡 请确认服务已启动：{base_url}")
        return {"success": False, "error": str(e), "elapsed_ms": 0}
    except httpx.TimeoutException as e:
        print(f"❌ 请求超时：{str(e)}")
        return {"success": False, "error": str(e), "elapsed_ms": TIMEOUT * 1000}
    except Exception as e:
        print(f"❌ 未知错误：{str(e)}")
        return {"success": False, "error": str(e), "elapsed_ms": 0}

def validate_response(response: dict):
    """验证响应结构是否符合规范"""
    print("\n【响应结构验证】")
    
    required_fields = ["code", "message", "data"]
    for field in required_fields:
        if field in response:
            print(f"  ✅ {field}: 存在")
        else:
            print(f"  ❌ {field}: 缺失")
    
    if "data" in response and response["data"]:
        data = response["data"]
        data_fields = ["task_id", "entities", "meta"]
        for field in data_fields:
            if field in data:
                print(f"  ✅ data.{field}: 存在")
            else:
                print(f"  ❌ data.{field}: 缺失")
        
        if "meta" in data:
            meta = data["meta"]
            meta_fields = ["model", "tokens_used", "latency_ms", "output_schema"]
            for field in meta_fields:
                if field in meta:
                    print(f"  ✅ meta.{field}: {meta[field]}")
                else:
                    print(f"  ⚠️  meta.{field}: 缺失")

def run_all_tests(base_url: str = BASE_URL):
    """运行所有测试用例"""
    test_cases = [
        TEST_CASE_1,
        TEST_CASE_2,
        TEST_CASE_3,
        TEST_CASE_4,
        TEST_CASE_5
    ]
    
    results = []
    success_count = 0
    
    print_separator("🚀 债券交易 LLM 抽取服务 - 批量测试")
    print(f"服务地址：{base_url}{API_ENDPOINT}")
    print(f"测试用例数：{len(test_cases)}")
    print(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n>>> 执行测试 {i}/{len(test_cases)}")
        result = run_test(test_case, base_url)
        results.append(result)
        
        if result["success"]:
            success_count += 1
        
        # 每个测试之间间隔 1 秒
        if i < len(test_cases):
            time.sleep(1)
    
    # 打印测试总结
    print_separator("📊 测试总结")
    print(f"总用例数：{len(test_cases)}")
    print(f"成功数：{success_count}")
    print(f"失败数：{len(test_cases) - success_count}")
    print(f"成功率：{success_count / len(test_cases) * 100:.1f}%")
    
    total_elapsed = sum(r.get("elapsed_ms", 0) for r in results)
    print(f"总耗时：{total_elapsed} ms")
    print(f"平均耗时：{total_elapsed / len(test_cases):.0f} ms")
    print(f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return results

# ==================== 快速测试函数 ====================

def quick_test(content: str, base_url: str = BASE_URL):
    """
    快速测试单个消息
    
    Args:
        content: 聊天内容
        base_url: 服务地址
    """
    test_case = {
        "input": {
            **get_base_input(),
            "content": content
        },
        "config": {}
    }
    return run_test(test_case, base_url)

# ==================== 主函数 ====================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="债券交易 LLM 抽取服务测试脚本")
    parser.add_argument(
        "--url", 
        type=str, 
        default=BASE_URL, 
        help=f"服务地址 (默认：{BASE_URL})"
    )
    parser.add_argument(
        "--quick", 
        type=str, 
        default=None, 
        help="快速测试指定内容"
    )
    parser.add_argument(
        "--case", 
        type=int, 
        default=None, 
        help="运行指定测试用例 (1-5)"
    )
    
    args = parser.parse_args()
    
    if args.quick:
        # 快速测试模式
        quick_test(args.quick, args.url)
    elif args.case:
        # 单用例测试模式
        test_cases = [
            TEST_CASE_1, TEST_CASE_2, TEST_CASE_3, 
            TEST_CASE_4, TEST_CASE_5
        ]
        if 1 <= args.case <= len(test_cases):
            run_test(test_cases[args.case - 1], args.url)
        else:
            print(f"❌ 无效的用例编号：{args.case} (1-{len(test_cases)})")
    else:
        # 批量测试模式
        run_all_tests(args.url)
```

### `tests/requirements-test.txt`

```text
httpx>=0.26.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
```

### 使用方式

```bash
# 1. 安装测试依赖
pip install -r tests/requirements-test.txt

# 2. 运行所有测试用例
python tests/test_api.py

# 3. 指定服务地址测试
python tests/test_api.py --url http://192.168.1.100:8000

# 4. 快速测试单条消息
python tests/test_api.py --quick "出 24 国债 01，净价 99.5，量 1000 万"

# 5. 运行指定测试用例
python tests/test_api.py --case 1
python tests/test_api.py --case 3
```

### 预期输出示例

```
================================================================================
  🚀 债券交易 LLM 抽取服务 - 批量测试
================================================================================
服务地址：http://localhost:8000/api/v1/llm/extract-transaction
测试用例数：5
开始时间：2026-02-10 15:30:00

>>> 执行测试 1/5

================================================================================
  测试：标准债券交易 - 使用默认 schema
================================================================================

【请求参数】
{
  "input": {
    "timestamp": "2026/02/10 10:26:06",
    "content": "出 24 国债 01，净价 99.5，量 1000 万，T+0 清算，有意向的私",
    ...
  },
  "config": {}
}

HTTP 状态码：200
请求耗时：1523 ms

【响应结果】
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "entities": [
      {
        "timestamp": "2026/02/10 10:26:06",
        "stock_code": "240001.IB",
        "stock_name": "24 国债 01",
        "price_type": "净价",
        "cust_trade_price": "99.5",
        "cust_trade_amount": "1000W",
        "clear_speed": "T+0",
        ...
      }
    ],
    "meta": {
      "model": "qwen-max",
      "tokens_used": 256,
      "latency_ms": 1450,
      "output_schema": "v1_standard"
    }
  }
}

【响应结构验证】
  ✅ code: 存在
  ✅ message: 存在
  ✅ data: 存在
  ✅ data.task_id: 存在
  ✅ data.entities: 存在
  ✅ data.meta: 存在
  ✅ meta.model: qwen-max
  ✅ meta.tokens_used: 256
  ✅ meta.latency_ms: 1450
  ✅ meta.output_schema: v1_standard

... (其他测试用例)

================================================================================
  📊 测试总结
================================================================================
总用例数：5
成功数：5
失败数：0
成功率：100.0%
总耗时：7845 ms
平均耗时：1569 ms
结束时间：2026-02-10 15:30:08
```

### Docker 测试（服务在容器中）

```bash
# 1. 启动服务
docker run -d -p 8000:8000 --env-file .env bond-llm-extractor:latest

# 2. 等待服务启动
sleep 5

# 3. 运行测试
python tests/test_api.py --url http://localhost:8000

# 4. 停止服务
docker stop $(docker ps -q --filter ancestor=bond-llm-extractor)
```

这个测试脚本提供了完整的测试覆盖，包括参数验证、响应结构检查、性能统计等功能！

