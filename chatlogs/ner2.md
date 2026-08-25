**system**:You are a helpful assistant about AI & LLM properties.


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

