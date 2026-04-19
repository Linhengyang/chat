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

