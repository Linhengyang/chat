**system**:You are a helpful assistant specializing on BPE algorithm.


---
🙋**user**:
---
```
我现在要用 Cython/C++ 编写下面代码中的核心逻辑 split_count_batch
def bow_worker(pq_fpath, text_colname: str, split_pattern: str):
    '''
    执行BoW的进程: 分发得到 parquet 文件地址, 遍历 batch, 对每一个 batch 执行 split / count, 累积更新至 local_counter
    '''
    local_counter = Counter()
    pf = pq.ParquetFile(pq_fpath)
    for batch in pf.iter_batches(batch_size = 65536, columns=[text_colname]):
        batch_text = batch[text_colname].to_pylist()
        # accelerate by Cython/C++: 
        # input py-obj: list of text(string)/这种情况下python负责切分 or string/这种情况下Cython负责切分
        batch_counts = split_count_batch('\n'.join( batch_text ), split_pattern) # list of strings ->预切分/编码/计数-> dict of {bytes: uint64} 
        # output py-obj: dict of {bytes: uint64} 
        local_counter.update(batch_counts)
    return local_counter
正如注释, 有两种方案:
方案一: 在python层执行预切分, lines = re.findall(split_pattern, '\n'.join( batch_text )), 然后将lines作为list of string传给Cython, Cython/C++负责utf-8编码和计数
方法二: 将'\n'.join( batch_text )作为text传给Cython, 在Cython层执行预切分、utf-8编码、计数
哪个比较好？如果是方案二，那么Cython怎么写等价于 lines = re.findall(split_pattern, '\n'.join( batch_text )) 的预切分? 这里re是包regex
```

---
🤖**assistant**:
---

### 结论：方案二更好 (Cython 层控制流程)

**推荐方案二**，即：在 Python 层将文本合并并编码为 `bytes`，传给 Cython；在 Cython 层执行正则匹配（获取跨度）、切片、编码（已预编码）、计数。

#### 理由：
1.  **内存与对象开销（核心瓶颈）**：
    *   **方案一**：`re.findall` 会创建一个包含所有切分词的 **Python List**，且每个词都是一个 **Python String/Bytes 对象**。如果一批数据有 100 万个词，就会瞬间创建 100 万个 Python 对象。这会导致严重的内存分配压力和 GC 负担。
    *   **方案二**：在 Cython 中，我们可以避免创建中间 List。我们可以直接迭代匹配结果，使用 C++ `std::unordered_map` 进行计数，仅在最后返回结果时转换为 Python `dict`。这能减少 90% 以上的临时对象创建。
2.  **编码效率**：
    *   UTF-8 编码应该在合并后的大字符串上**只执行一次**（在 Python 层或 Cython 入口），而不是对每个切分出的词单独编码。
3.  **正则引擎的选择**：
    *   **不建议**在 C++ 中从头重写正则引擎（如使用 `std::regex`）。`std::regex` 性能通常较差且对 Unicode 支持不如 Python 的 `regex` 库完善。
    *   **最佳实践**：在 Cython 中 `import regex` 模块，利用其 C 语言底层的匹配能力，但**只获取匹配跨度 (span)**，不生成子串对象，配合 C++ 逻辑计数。

---

### Cython 实现方案 (方案二优化版)

这个实现结合了 Python `regex` 库的兼容性（支持复杂 Unicode 规则）和 C++ 的计数性能。

#### 1. 目录结构
```text
project/
├── bow_worker.py      # Python 调用层
├── bow_core.pyx       # Cython 核心逻辑
├── setup.py           # 编译配置
```

#### 2. Cython 核心代码 (`bow_core.pyx`)

```python
# distutils: language = c++
# cython: language_level=3, boundscheck=False, wraparound=False

import regex
from libc.stdlib cimport malloc, free
from libcpp.unordered_map cimport unordered_map
from libcpp.string cimport string
from cpython.bytes cimport PyBytes_AsString, PyBytes_GET_SIZE
from cpython.dict cimport PyDict_SetItem
from cpython.long cimport PyLong_FromLongLong

# 定义 C++ 计数器类型
cdef unordered_map[string, unsigned long long] cpp_counter

def split_count_batch(bytes text_bytes, str split_pattern):
    """
    text_bytes: 已经 utf-8 编码的整个 batch 文本 (b'\n'.join(...))
    split_pattern: 正则表达式字符串
    返回：dict of {bytes: int}
    """
    # 1. 编译正则 (注意：regex 库支持 bytes 模式，避免匹配时重复编码)
    # 实际生产中建议缓存 compiled_pattern，这里为了演示每次编译
    cdef bytes pattern_bytes = split_pattern.encode('utf-8')
    cdef compiled_regex = regex.compile(pattern_bytes)
    
    # 2. 获取底层 C 指针，避免 Python 切片开销
    cdef const char* buffer = PyBytes_AsString(text_bytes)
    cdef Py_ssize_t total_len = PyBytes_GET_SIZE(text_bytes)
    
    # 3. C++ 计数器
    cdef unordered_map[string, unsigned long long] local_map
    cdef string token_str
    cdef unsigned long long count
    
    # 4. 迭代匹配 (finditer 不会像 findall 那样一次性生成列表)
    # 注意：这里仍然会创建 Match 对象，但避免了创建子串 bytes 对象
    for match in compiled_regex.finditer(text_bytes):
        cdef int start = match.start()
        cdef int end = match.end()
        
        # 安全校验
        if start < 0 or end > total_len or start >= end:
            continue
            
        # 5. 直接从 buffer 构造 std::string，无 Python 对象分配
        # string(const char* s, size_t n) 构造函数
        token_str = string(buffer + start, end - start)
        
        local_map[token_str] += 1
        
    # 6. 将 C++ map 转换回 Python dict (仅在最后发生一次)
    cdef dict result = {}
    cdef unordered_map[string, unsigned long long].iterator it = local_map.begin()
    cdef string key
    cdef unsigned long long val
    
    while it != local_map.end():
        key = it.first
        val = it.second
        # 构造 Python bytes 对象 (这是必须的，因为要返回给 Python)
        # 但此时只针对唯一词表，而非所有 token
        py_key = bytes(key) 
        result[py_key] = val
        it += 1
        
    return result
```

#### 3. Python 调用层 (`bow_worker.py`)

```python
import pyarrow.parquet as pq
from collections import Counter
from bow_core import split_count_batch  # 导入编译后的模块

def bow_worker(pq_fpath, text_colname: str, split_pattern: str):
    local_counter = Counter()
    pf = pq.ParquetFile(pq_fpath)
    
    for batch in pf.iter_batches(batch_size=65536, columns=[text_colname]):
        batch_text_list = batch[text_colname].to_pylist()
        
        # 过滤 None，避免 join 报错
        batch_text_list = [t for t in batch_text_list if t]
        if not batch_text_list:
            continue
            
        # 【关键优化】在 Python 层只做一次 join 和 encode
        # 传入 Cython 的是 bytes，避免 Cython 内部重复编码
        joined_text = '\n'.join(batch_text_list)
        text_bytes = joined_text.encode('utf-8')
        
        # 调用 Cython 核心
        batch_counts = split_count_batch(text_bytes, split_pattern)
        
        local_counter.update(batch_counts)
        
    return local_counter
```

#### 4. 编译配置 (`setup.py`)

```python
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(
        "bow_core.pyx",
        compiler_directives={'language_level': "3"},
        annotate=True  # 生成 html 报告查看优化情况
    ),
    zip_safe=False,
)
```
编译命令：`python setup.py build_ext --inplace`

---

### 性能优化细节解析

1.  **`bytes` 传输**：
    *   Python 的 `str` 是 Unicode，C++ 处理起来需要编码。我们在 Python 层一次性 `encode('utf-8')` 传给 Cython `bytes`。Cython 通过 `PyBytes_AsString` 拿到 `char*` 指针，这是零拷贝的。
2.  **`regex.finditer` vs `findall`**：
    *   `findall` 返回 `list[bytes]`，意味着如果文本有 100 万个词，内存里瞬间多了 100 万个 `bytes` 对象。
    *   `finditer` 返回迭代器，每次只生成一个 `Match` 对象。虽然 `Match` 也是 Python 对象，但它的生命周期极短，且我们只读取 `.start()` 和 `.end()` 整数，不提取子串。
3.  **`std::string` 缓冲**：
    *   代码中 `token_str = string(buffer + start, end - start)` 使用的是 C++ `std::string`。这在循环内部**不会**触发 Python 的内存管理（GIL 竞争、引用计数）。
    *   只有在最后 `result[py_key] = val` 时，才将唯一的词转换为 Python `bytes` 对象。假设词表大小为 5 万，而 Token 总数为 100 万，这减少了 95% 的对象创建。
4.  **正则缓存（进阶）**：
    *   上面的代码每次 batch 都 `regex.compile`。如果 `split_pattern` 在整个任务中不变，建议在 Python 层编译好，将 `compiled_regex` 对象传给 Cython，或者在 Cython 内部使用 `functools.lru_cache` 缓存编译结果。

### 如果追求极致性能 (纯 C++ 正则)

如果你的 `split_pattern` 非常简单（例如只是按空白符 `\s+` 或单词 `\w+` 切分），**不要使用 `regex` 模块**。直接在 Cython 中写一个简单的状态机或使用 `re2` 库。

例如，简单的空白符切分 C++ 逻辑（无需 `import regex`）：

```cython
# 在 bow_core.pyx 中替代 regex 部分
cdef int is_separator(char c):
    return c == 32 or c == 10 or c == 13 or c == 9  # space, \n, \r, \tab

# ... 在循环中 ...
cdef int i = 0
cdef int start = -1
while i < total_len:
    if not is_separator(buffer[i]):
        if start == -1: start = i
    else:
        if start != -1:
            token_str = string(buffer + start, i - start)
            local_map[token_str] += 1
            start = -1
    i += 1
# 处理最后一个词
if start != -1:
    token_str = string(buffer + start, i - start)
    local_map[token_str] += 1
```
**这种纯 C++ 扫描比调用 `regex` 模块快 5-10 倍**，但仅适用于简单规则。如果必须兼容 Python `regex` 的复杂语义（如 lookahead, Unicode 属性），请使用前文的 `regex.finditer` 方案。


---
🙋**user**:
---
```
那在 Python 层编译好split_pattern，将 compiled_regex 对象传给 Cython。如何修改？只需给出修改部分
```

---
🤖**assistant**:
---

### 1. Python 层修改 (`bow_worker.py`)

主要在循环外预编译正则，并传入编译后的对象。

```python
import regex  # <--- 新增：需要导入 regex 模块
import pyarrow.parquet as pq
from collections import Counter
from bow_core import split_count_batch

def bow_worker(pq_fpath, text_colname: str, split_pattern: str):
    local_counter = Counter()
    pf = pq.ParquetFile(pq_fpath)
    
    # <--- 新增：在循环外预编译正则 (注意传入 bytes 模式)
    compiled_regex = regex.compile(split_pattern.encode('utf-8'))
    
    for batch in pf.iter_batches(batch_size=65536, columns=[text_colname]):
        batch_text_list = batch[text_colname].to_pylist()
        batch_text_list = [t for t in batch_text_list if t]
        if not batch_text_list:
            continue
            
        joined_text = '\n'.join(batch_text_list)
        text_bytes = joined_text.encode('utf-8')
        
        # <--- 修改：传入 compiled_regex 对象而不是字符串 pattern
        batch_counts = split_count_batch(text_bytes, compiled_regex)
        
        local_counter.update(batch_counts)
        
    return local_counter
```

### 2. Cython 层修改 (`bow_core.pyx`)

移除内部编译逻辑，调整函数签名接收 `object` 类型的正则对象。

```cython
# distutils: language = c++
# cython: language_level=3, boundscheck=False, wraparound=False

# import regex  <--- 删除：不再需要在 Cython 内部导入模块进行编译
from libc.stdlib cimport malloc, free
from libcpp.unordered_map cimport unordered_map
from libcpp.string cimport string
from cpython.bytes cimport PyBytes_AsString, PyBytes_GET_SIZE
from cpython.dict cimport PyDict_SetItem
from cpython.long cimport PyLong_FromLongLong

cdef unordered_map[string, unsigned long long] cpp_counter

# <--- 修改：第二个参数改为 object 类型的 compiled_regex
def split_count_batch(bytes text_bytes, object compiled_regex):
    cdef const char* buffer = PyBytes_AsString(text_bytes)
    cdef Py_ssize_t total_len = PyBytes_GET_SIZE(text_bytes)
    
    cdef unordered_map[string, unsigned long long] local_map
    cdef string token_str
    cdef unsigned long long count
    
    # <--- 修改：直接使用传入的 compiled_regex 对象
    # 无需再执行 regex.compile()
    for match in compiled_regex.finditer(text_bytes):
        cdef int start = match.start()
        cdef int end = match.end()
        
        if start < 0 or end > total_len or start >= end:
            continue
            
        token_str = string(buffer + start, end - start)
        local_map[token_str] += 1
        
    cdef dict result = {}
    cdef unordered_map[string, unsigned long long].iterator it = local_map.begin()
    cdef string key
    cdef unsigned long long val
    
    while it != local_map.end():
        key = it.first
        val = it.second
        py_key = bytes(key) 
        result[py_key] = val
        it += 1
        
    return result
```

### 主要改动点说明
1.  **避免重复编译**：`regex.compile` 是开销较大的操作，将其移出 `batch` 循环，每个文件只编译一次。
2.  **类型提示**：Cython 中接收 Python 对象使用 `object` 类型声明。虽然这会引入微小的动态方法查找开销（`finditer`），但相比每次 batch 都重新解析正则表达式，性能提升巨大。
3.  **编码一致性**：确保 Python 层编译正则时也使用了 `.encode('utf-8')`，这样 `compiled_regex` 期望输入的是 `bytes`，与传入的 `text_bytes` 匹配，避免 Cython 内部再次编码。


---
🙋**user**:
---
```
我从BoW.parquet文件读取unique_words和freqs, schema分别是largeList of list of u32和u64. 我希望做到用python读取, 然后通过cython传递给C++函数，对每个list of U32执行Word class的构造
Word class的构造参数是list of u32。完成构造后, 真正要用的是vector of Word。
我的问题是，python层对于unique_words应该是用什么读取? 列表还是numpy array(用flattened value + offsets来读)? 如果是用后者，那么在C++函数这里有没有办法可以用flattened values+offsets, 直接零拷贝地原地placenment new成vector of Word?
```

---
🤖**assistant**:
---

### 核心结论

1.  **Python 层读取方式**：**必须使用 PyArrow 的 Buffer 接口**（`combined_chunk().buffers()`），**绝对不要**用 `to_pylist()` 或 `to_numpy()`。
    *   `to_pylist()`：创建百万级 Python 对象，内存爆炸。
    *   `to_numpy()`：会触发一次内存拷贝（Arrow -> NumPy）。
    *   `buffers()`：**零拷贝**获取底层内存地址。
2.  **C++ 层零拷贝 Placement New**：
    *   **传输零拷贝**：可以做到。Python Arrow Buffer 指针直接传给 C++，无拷贝。
    *   **存储零拷贝**：**取决于 `Word` 类的定义**。
        *   如果 `Word` 内部拥有数据（如 `std::vector<uint32_t>`）：**无法零拷贝**。`Word` 构造时必须 `malloc` 并 `memcpy` 数据，因为 `Word` 生命周期可能长于 Arrow 对象。
        *   如果 `Word` 是视图（如 `const uint32_t* data + size_t len`）：**可以零拷贝**。但**必须保证 Python 端的 Arrow 对象不被 GC**，否则 C++ 指针会悬空（Segfault）。

---

### 1. Python 层：读取 Buffer 指针

不要转换数据，直接拿内存地址。注意处理 `combine_chunks` 以保证内存连续。

```python
# bow_loader.py
import pyarrow as pq
import pyarrow.compute as pc

def load_word_buffers(pq_fpath):
    table = pq.read_table(pq_fpath, columns=['unique_words'])
    col = table.column('unique_words')
    
    # 1. 合并分块 (重要！)
    # Parquet 读取可能是 chunked 的，为了获取单一连续指针，必须合并
    # 这会触发一次内存拷贝 (在 Arrow 内部)，但比转 Python 对象快得多
    arr = col.combine_chunks() 
    
    # 2. 获取底层 Buffers
    # LargeList 结构: [Validity, Offsets, Values]
    buffers = arr.buffers()
    
    # 3. 提取指针和长度
    # offsets 是 int64, values 是 uint32
    offsets_ptr = buffers[1].address  # Buffer 1 是 Offsets
    values_ptr = buffers[2].address   # Buffer 2 是 Values
    
    # 逻辑长度 (单词个数 = offsets 长度 - 1)
    num_words = len(arr) 
    total_values = len(arr.null_count) # 或者直接从 offsets 计算
    
    # 4. 必须保持 arr 对象存活！
    # 如果 arr 被 GC，buffers 指针失效
    return arr, offsets_ptr, values_ptr, num_words
```

### 2. Cython 层：传递指针

```cython
# bow_bridge.pyx
# distutils: language = c++
# cython: language_level=3

from libcpp.vector cimport vector
from libcpp.cmath cimport uintptr_t

# 引入 C++ 头文件
cdef extern from "word_builder.h" namespace "std":
    # 假设你的 C++ 函数定义如下
    cdef vector[Word] build_words(const long long* offsets, const unsigned int* values, size_t num_words)

def cython_build_words(object arrow_array, long long offsets_addr, long long values_addr, size_t num_words):
    """
    arrow_array: 必须传入以保持引用计数，防止 Python GC 回收底层内存
    """
    # 将地址转换为 C 指针
    cdef const long long* offsets_ptr = <const long long*>offsets_addr
    cdef const unsigned int* values_ptr = <const unsigned int*>values_addr
    
    # 调用 C++ 核心逻辑
    # 注意：arrow_array 在这里被引用，只要本函数未返回，内存就是安全的
    cdef vector[Word] result = build_words(offsets_ptr, values_ptr, num_words)
    
    return result # 这里需要定义如何将 vector[Word] 转回 Python 对象，或者直接在此处理
```

### 3. C++ 层：构造 `vector<Word>`

这里回答你关于 **Placement New** 的问题。

#### 方案 A：`Word` 拥有数据 (安全，推荐)
如果 `Word` 内部是 `std::vector<uint32_t>`，你**不能**完全零拷贝（因为 `Word` 需要自己 `new` 内存）。但你可以优化 `vector<Word>` 的扩容开销。

```cpp
// word_builder.h
#include <vector>
#include <cstdint>

struct Word {
    std::vector<uint32_t> token_ids;
    Word(const uint32_t* begin, const uint32_t* end) {
        // 这里必然发生一次 memcpy/分配，无法避免，除非改 Word 结构
        token_ids.assign(begin, end); 
    }
};

std::vector<Word> build_words(const int64_t* offsets, const uint32_t* values, size_t num_words) {
    std::vector<Word> words;
    
    // 1. 预分配内存，避免 push_back 时的多次扩容 (这是主要优化点)
    words.reserve(num_words); 
    
    for (size_t i = 0; i < num_words; ++i) {
        int64_t start = offsets[i];
        int64_t end = offsets[i+1];
        
        // 2. 构造 Word
        // 推荐用 emplace_back，它在 reserve 后效果等同于 placement new 且更安全
        words.emplace_back(values + start, values + end);
        
        /* 
         * 如果你坚持要用 Placement New (不推荐，除非你有特殊内存池需求):
         * 需要手动管理构造状态，容易出错。
         * new (&words[i]) Word(values + start, values + end); 
         * 且需要确保析构时不会重复释放未构造的内存。
         */
    }
    return words;
}
```

#### 方案 B：`Word` 是视图 (真·零拷贝，高风险)
如果你追求极致性能且能保证生命周期，修改 `Word` 为视图。

```cpp
// word_builder.h
#include <vector>
#include <cstdint>
#include <span> // C++20, 或者用 pointer+size

struct WordView {
    const uint32_t* data;
    size_t size;
    
    WordView(const uint32_t* d, size_t s) : data(d), size(s) {}
};

// 注意：返回的 vector 包含的指针指向 Python 管理的内存
// 必须确保 Python 端的 arrow_array 对象比这个 vector 活得更久！
std::vector<WordView> build_words_view(const int64_t* offsets, const uint32_t* values, size_t num_words) {
    std::vector<WordView> words;
    words.reserve(num_words);
    
    for (size_t i = 0; i < num_words; ++i) {
        int64_t start = offsets[i];
        int64_t end = offsets[i+1];
        size_t len = end - start;
        
        // 这里没有 memcpy，没有 new，纯零拷贝
        words.emplace_back(values + start, len);
    }
    return words;
}
```

### 关键风险提示 (必读)

1.  **生命周期管理 (Lifetime)**：
    *   如果采用 **方案 B (视图/零拷贝)**：C++ 中的指针直接指向 Python PyArrow 的内存。**绝对不能**在 C++ 侧保存这个 `vector<WordView>` 超过 Python 函数调用的生命周期。一旦 Python 的 `arrow_array` 变量超出作用域被 GC，C++ 指针立即悬空，访问即崩溃。
    *   如果采用 **方案 A (拥有数据)**：C++ 侧会复制一份数据。这是构建词表（Vocabulary）的标准做法，因为词表通常需要长期驻留内存，不依赖原始 Parquet 文件。

2.  **Placement New 的陷阱**：
    *   在 `std::vector` 上使用 placement new (`new (&vec[i])`) 是非常危险的。`std::vector` 的析构函数会尝试销毁所有元素。如果你只对部分元素进行了 placement new，或者 `vector` 扩容了（移动了内存），会导致双重释放或未定义行为。
    *   **最佳实践**：使用 `reserve()` 预分配容量，然后使用 `emplace_back()`。这在效果上等同于你想要的“原地构造”，但由 STL 保证内存安全。

3.  **Offsets 类型**：
    *   PyArrow `large_list` 的 offsets 是 `int64` (`long long`)。
    *   PyArrow `list` 的 offsets 是 `int32` (`int`)。
    *   请务必确认你的 Parquet schema 是 `large_list`，C++ 接收指针时类型要匹配 (`const int64_t*`)。

### 总结建议

*   **读取**：Python 层用 `combine_chunks().buffers()` 拿地址。
*   **传递**：Cython 层透传 `address` 指针，并**持有 `arrow_array` 对象引用**以防 GC。
*   **构造**：C++ 层 `vector.reserve(N)` + `emplace_back`。
*   **零拷贝**：除非你能严格保证 C++ 对象不存活过 Python 调用栈，否则**建议让 `Word` 复制数据**。对于 BoW 词表构建，数据复制的开销远小于 Python 对象创建的开销，且更安全。


---
🙋**user**:
---
```
unique words在后面要被in-place merge, 即vector of words中的每个word都会in-place修改。不过我倒是确实能严格保证C++对象能存活过Python调用栈.所以我有点迷惑了。
我对于从parquet文件(硬盘)、python读到内存(read_table/column取列/combine_chunks+buffers取地址)、cython传递指针、C++构造vector<Word>这条链路，是否有拷贝的必要性存在疑问。理论上来说，硬盘中的parquet文件保证了数据原始备份，从它被读到内存中后似乎零拷贝是可以的，但是似乎按你的意思，还是再发生一次拷贝以保证独立的数据生命周期比较好。这次拷贝可以是to_numpy(pyarrow.buffer->numpy.array), 但你的意思似乎是，numpy这一次的拷贝是没有必要的，buffer读地址直接在vector<Word>构造时拷贝更好
```

---
🤖**assistant**:
---

你的直觉非常敏锐，这确实是高性能数据处理中最关键的权衡点。针对你的**In-Place 修改**需求，结论非常明确：

**必须在 C++ 构造 `vector<Word>` 时进行数据拷贝，不能零拷贝。**

且**绝对不要**用 `to_numpy()`，应直接使用 `buffer` 地址在 C++ 层拷贝。

### 1. 为什么“零拷贝”在你的场景下不可行？

虽然你能保证 C++ 对象存活过 Python 调用栈，但 **In-Place 修改** 这一需求直接否定了零拷贝（视图）方案：

| 特性 | 零拷贝视图方案 (`const uint32_t*`) | 拥有数据方案 (`std::vector<uint32_t>`) |
| :--- | :--- | :--- |
| **内存归属** | 属于 PyArrow (Python 管理) | 属于 C++ (`Word` 对象) |
| **可写性** | ❌ **不可写** (是 `const` 指针) | ✅ **可写** (拥有独立副本) |
| **修改后果** | 会污染 PyArrow 内存，导致后续读取错误 | 安全，不影响原始数据 |
| **生命周期** | 依赖 Python 对象存活 | 完全独立 |

**核心风险**：
如果你强行去掉 `const` 进行 In-Place 修改，实际上是在修改 PyArrow 管理的内存。PyArrow 的 Buffer 可能是**内存映射 (mmap)** 的，或者被多个对象**共享引用**。修改它会破坏原始数据的一致性，甚至导致 Segfault。

### 2. 为什么 `to_numpy()` 是多余的拷贝？

你提到的两种拷贝路径对比：

| 路径 | 拷贝次数 | 说明 |
| :--- | :--- | :--- |
| **方案 A (推荐)**: Arrow Buffer -> C++ `Word` | **1 次** | 直接在 C++ 构造时从原始 Buffer 拷贝 |
| **方案 B (不推荐)**: Arrow Buffer -> NumPy -> C++ `Word` | **2 次** | `to_numpy()` 拷贝一次，C++ 再拷贝一次 |

**结论**：`to_numpy()` 在中间多创建了一个完整的 NumPy 数组副本，纯属浪费内存和带宽。既然最终数据要落入 `vector<Word>`，不如直接从源头（Arrow Buffer）拷贝到终点。

### 3. 最佳实践代码实现

#### Python 层：获取指针 (零拷贝)
```python
# bow_loader.py
import pyarrow as pq

def load_word_buffers(pq_fpath):
    table = pq.read_table(pq_fpath, columns=['unique_words'])
    arr = table.column('unique_words').combine_chunks()
    
    buffers = arr.buffers()
    # large_list: [validity, offsets, values]
    offsets_ptr = buffers[1].address  # int64
    values_ptr = buffers[2].address   # uint32
    num_words = len(arr)
    
    # 关键：返回 arr 保持引用，防止在 Cython 调用期间被 GC
    return arr, offsets_ptr, values_ptr, num_words
```

#### Cython 层：透传指针
```cython
# bow_bridge.pyx
# distutils: language = c++

from libcpp.vector cimport vector

cdef extern from "word_builder.h":
    cdef cppclass Word:
        Word()
    # 声明构建函数
    cdef vector[Word] build_words(const long long* offsets, 
                                  const unsigned int* values, 
                                  size_t num_words)

def cython_build_words(object arrow_array, 
                       long long offsets_addr, 
                       long long values_addr, 
                       size_t num_words):
    cdef const long long* offsets_ptr = <const long long*>offsets_addr
    cdef const unsigned int* values_ptr = <const unsigned int*>values_addr
    
    # arrow_array 作为参数持有引用，确保内存安全
    cdef vector[Word] words = build_words(offsets_ptr, values_ptr, num_words)
    
    return words
```

#### C++ 层：构造 + 拷贝 (关键优化点)
```cpp
// word_builder.h
#include <vector>
#include <cstdint>

struct Word {
    std::vector<uint32_t> token_ids;
    
    // 构造函数：从指针范围拷贝数据
    Word(const uint32_t* begin, const uint32_t* end) 
        : token_ids(begin, end) {}  // std::vector 的范围构造函数会内部拷贝
    
    // In-Place 修改接口 (安全，因为数据是自己拥有的)
    void modify_in_place() {
        if (!token_ids.empty()) {
            token_ids[0] = 999;  // 安全修改
        }
    }
};

std::vector<Word> build_words(const int64_t* offsets, 
                              const uint32_t* values, 
                              size_t num_words) {
    std::vector<Word> words;
    
    // 关键优化：预分配内存，避免 push_back 时的多次扩容
    words.reserve(num_words);
    
    for (size_t i = 0; i < num_words; ++i) {
        int64_t start = offsets[i];
        int64_t end = offsets[i+1];
        
        // emplace_back 在 reserve 后等效于 placement new + 构造
        // 数据在这里发生唯一的一次必要拷贝 (Arrow Buffer -> Word 内部)
        words.emplace_back(values + start, values + end);
    }
    
    return words;
}
```

### 4. 关于 Placement New 的补充

你问到能否用 `flattened values + offsets` 直接 **placement new** 成 `vector<Word>`。

**答案**：`std::vector` 的内存布局是连续的 `Word` 对象，但每个 `Word` 内部的 `std::vector<uint32_t>` 是**堆上独立分配**的。

```
vector<Word> 内存布局:
[ Word Header | vector Header | pointer -> [uint32, uint32...] (堆上) ]
[ Word Header | vector Header | pointer -> [uint32, uint32...] (堆上) ]
...
```

即使你用 placement new 构造 `Word` 对象本身，`Word` 内部的 `token_ids` 仍然需要 `malloc` 和 `memcpy`。所以**无法避免数据拷贝**，只能用 `reserve() + emplace_back()` 来避免 `vector<Word>` 本身的扩容开销。

### 总结

| 环节 | 操作 | 是否拷贝 | 理由 |
| :--- | :--- | :--- | :--- |
| Parquet -> Arrow | `read_table` | 必要 | 从磁盘加载到内存 |
| Arrow -> Python | `buffer.address` | **零拷贝** | 直接拿指针，不创建对象 |
| Python -> Cython | 透传指针 | **零拷贝** | 仅传递地址值 |
| Arrow -> Word | `emplace_back` | **必要拷贝** | 为了 In-Place 修改的安全性和独立性 |
| NumPy 中转 | `to_numpy()` | ❌ 避免 | 多余的中间拷贝 |

**最终建议**：接受这一次必要的拷贝，它是为了**内存所有权清晰**和**修改安全性**付出的最小代价。

