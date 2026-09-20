**system**:You are a helpful assistant about IT & network.


---
🙋**user**:
---
```
steam加速器的原理是什么？它与我在用的代理clash verge会冲突吗？
```

---
🤖**assistant**:
---

可以，但**可能会冲突**。关键取决于你说的“Steam 加速器”是哪一种，以及它和 Clash Verge 是否同时抢占了系统代理、TUN/虚拟网卡、DNS、hosts 或端口。

下面分开讲。

---

## 一、Steam 加速器一般是什么原理？

“Steam 加速器”这个词其实包含好几种东西，原理不完全一样。

---

### 1. Steam 商店 / 社区加速器

比如用于加速 `steamcommunity.com`、Steam 商店、社区、创意工坊、个人资料页等。

常见原理：

- 在本地启动一个代理或反向代理；
- 修改系统代理、hosts 或 DNS，把 Steam 社区/商店域名指向本地代理；
- 由加速器程序连接到它提供的中转服务器或可用线路；
- 最终访问 Steam 的 Web 服务器。

这类工具本质上类似一个**专门针对 Steam 域名的定向代理**。

有些工具会：

- 修改系统代理；
- 修改 hosts；
- 启动本地 HTTP/HTTPS 代理；
- 替换或安装本地证书；
- 对特定域名做重定向。

所以它和 Clash Verge 的冲突概率相对较高。

---

### 2. Steam 下载加速器

Steam 游戏下载通常走 Valve/CDN 的下载服务器。

所谓下载加速，常见方式是：

- 帮你选择更合适的 Steam 下载区域；
- 测试并推荐延迟更低、负载更低的下载服务器；
- 使用中转节点或线路优化；
- 有些只是修改 Steam 客户端配置或 hosts，让它连接到更容易访问的 CDN 节点。

但需要注意：  
**Steam 下载速度主要取决于你的宽带、运营商到 Steam CDN 的线路、下载服务器负载。**  
如果 Steam 下载流量被代理绕到很远的节点，反而会更慢。

---

### 3. 游戏联机加速器

比如用于降低某款游戏的联机延迟、减少丢包、改善 NAT 等。

原理通常是：

- 在你的电脑和游戏服务器之间建立一条加速节点中转路径；
- 通过加速商的专线、中转服务器、智能路由来降低延迟；
- 对 TCP/UDP 流量进行转发；
- 有些会使用虚拟网卡、进程代理、路由表修改等方式接管游戏流量。

这类加速器更关注游戏进程流量，而不是单纯的 Steam 商店流量。

---

## 二、它会和 Clash Verge 冲突吗？

**可能会，但不是必然。**

如果只是其中一个工具接管流量，通常问题不大。  
但如果两边同时修改系统代理、TUN、DNS、hosts、路由或监听相同端口，就容易冲突。

---

## 三、常见冲突场景

### 1. 两边都开启“系统代理”

Clash Verge 可以开启系统代理。  
一些 Steam 加速器也会开启系统代理，或者通过本地代理转发 Steam 流量。

如果两个工具都试图修改系统代理，可能出现：

- 浏览器打不开网页；
- Steam 商店反复加载；
- Steam 登录异常；
- 加速器显示成功但实际无效；
- Clash Verge 日志里出现大量奇怪请求；
- 流量被多次转发，形成代理套娃。

例如：

```text
浏览器 → Clash 系统代理 → Steam 加速器本地代理 → 远端节点
```

或者反过来：

```text
浏览器 → Steam 加速器代理 → Clash 本地代理 → 远端节点
```

这种链路很容易导致速度慢、连接失败或规则混乱。

---

### 2. 两边都开启 TUN / 虚拟网卡 / 增强模式

Clash Verge 如果开启了 TUN、增强模式、虚拟网卡、全局路由接管等功能，它可能会接管整个系统流量。

而一些游戏加速器也会：

- 创建虚拟网卡；
- 修改路由表；
- 接管游戏进程流量；
- 劫持 UDP；
- 对特定端口做转发。

如果两者都尝试全局接管，可能出现：

- 游戏延迟反而变高；
- 加速器节点连接失败；
- 游戏无法搜索服务器；
- 语音软件异常；
- UDP 流量被丢弃；
- Clash 日志里看到游戏流量被代理到不合适节点；
- Steam 下载变慢。

---

### 3. DNS / hosts 冲突

有些 Steam 加速器会通过 hosts 或 DNS 把 Steam 域名解析到特定 IP。

而 Clash 可能会：

- 接管 DNS；
- 使用 Fake-IP；
- 对域名重新解析；
- 根据规则决定走代理还是直连。

如果加速器把 Steam 域名指向某个本地地址或专用 IP，而 Clash 的 Fake-IP/DNS 机制又改写了它，就可能导致：

- Steam 社区打不开；
- 加速器显示加速成功但实际无效；
- Steam 商店页面空白；
- 图片加载失败；
- 创意工坊异常。

---

### 4. 端口冲突

Clash 常见本地端口例如：

```text
7890
7891
7892
9090
```

某些加速器也可能使用本地代理端口。如果它们监听相同端口，或者加速器配置里写了和 Clash 相同的本地端口，就可能冲突。

表现包括：

- Clash Verge 启动失败；
- 加速器启动失败；
- 端口被占用；
- 系统代理设置后无效；
- 日志显示端口绑定失败。

---

### 5. Steam 下载被 Clash 代理，反而变慢

如果你开着 Clash，并且 Steam 下载流量被规则分配到远端代理节点，那么下载可能变慢。

因为 Steam 下载本身是 CDN 流量，通常直连到较近的 Steam 下载服务器会更快。  
如果经过代理节点绕一圈，可能适得其反。

例如：

```text
Steam 下载流量 → Clash 海外节点 → Steam CDN
```

这通常不如：

```text
Steam 下载流量 → 运营商直连 → Steam CDN
```

---

## 四、简单判断：是否冲突？

你可以用这个方式快速判断。

### 方法 1：只开 Clash，不开 Steam 加速器

观察：

- Steam 商店是否正常；
- Steam 社区是否正常；
- 下载速度是否正常；
- 游戏联机是否正常。

---

### 方法 2：只开 Steam 加速器，关闭 Clash Verge

观察：

- Steam 是否恢复正常；
- 游戏是否恢复正常；
- 下载是否变快或变慢。

---

### 方法 3：两个同时开

如果此时出现：

- 网页异常；
- Steam 商店加载慢；
- 加速器显示成功但无效；
- 游戏掉线；
- 下载速度明显下降；

基本说明两者存在流量接管冲突。

---

## 五、不同需求下怎么处理？

### 情况 A：你只是想打开 Steam 商店 / 社区

如果你只是访问 Steam 商店、社区、创意工坊，通常用 Clash 就可以处理，不一定需要额外开 Steam 加速器。

建议：

- 使用 Clash Verge 的规则，把 Steam 相关域名分流；
- 不要同时开另一个会修改系统代理的 Steam 加速器；
- 如果加速器只是“本地反代工具”，尽量避免和 Clash 系统代理同时开启。

例如可以让：

```text
steamcommunity.com → 代理
store.steampowered.com → 代理或按需
api.steampowered.com → 按需
steamcontent.com → 直连
steamcdn-a.akamaihd.net → 直连
```

不过具体规则要看你的网络环境和需求。

---

### 情况 B：你主要是 Steam 下载慢

Steam 下载慢更建议先检查：

1. Steam 客户端设置里的下载服务器；
2. 下载区域是否离你较近；
3. 是否开启了带宽限制；
4. 是否被路由器或运营商限速；
5. 是否使用 Wi-Fi 导致不稳定；
6. 是否某些下载节点本身拥堵。

一般建议：

```text
Steam 下载流量尽量直连
```

如果 Clash 开着，最好让 Steam 下载相关域名或进程直连。

例如可以考虑：

```text
steam.exe → DIRECT
steamwebhelper.exe → 按需
Steam 下载 CDN 域名 → DIRECT
```

注意：  
`steamwebhelper.exe` 既可能处理商店/社区页面，也可能参与部分网络请求，所以不能一刀切。最好根据实际日志调整。

---

### 情况 C：你玩联机游戏，需要降低延迟

如果你玩的是联机游戏，通常游戏加速器比 Clash 更适合处理游戏流量。

原因是：

- 游戏经常使用 UDP；
- 游戏对延迟和抖动敏感；
- 很多代理节点对 UDP 支持不好；
- 游戏服务器可能不在普通代理规则覆盖范围内；
- 加速商通常有针对游戏的线路优化。

建议：

- 玩联机游戏时，开启游戏加速器；
- Clash Verge 最好不要全局接管游戏流量；
- 如果 Clash 开了 TUN，建议把游戏进程、Steam 进程或相关端口绕过；
- 如果不确定，玩游戏时先关闭 Clash 的系统代理或 TUN 测试。

---

## 六、如果想让 Clash Verge 和 Steam 加速器共存，建议这样做

### 原则 1：不要同时开启两个“全局接管”功能

避免同时出现：

```text
Clash 系统代理 + Steam 加速器系统代理
```

或者：

```text
Clash TUN 全局接管 + Steam 加速器全局路由/虚拟网卡
```

同一时间最好只有一个工具负责全局流量。

---

### 原则 2：让 Steam 下载尽量直连

Steam 下载一般不建议走远端代理。

建议：

```text
Steam 下载 → 直连
Steam 商店/社区 → 按需代理
游戏联机 → 加速器或直连优化
```

---

### 原则 3：如果你开 Clash TUN，给加速器留白名单

如果你必须开 Clash 的 TUN/增强模式，可以尝试：

- 绕过局域网；
- 绕过本机地址；
- 绕过加速器进程；
- 绕过游戏进程；
- 绕过 Steam 下载进程或 CDN 域名；
- 对 UDP 游戏流量谨慎处理。

否则可能出现加速器连不上、游戏 UDP 被丢弃或绕路。

---

### 原则 4：检查端口占用

如果你怀疑端口冲突，可以在 Windows 下检查：

```powershell
netstat -ano | findstr :7890
netstat -ano | findstr :7891
netstat -ano | findstr :7892
netstat -ano | findstr :9090
```

如果看到异常进程占用，可以对应任务管理器查看。

---

### 原则 5：注意 Fake-IP 模式

如果 Clash 使用 Fake-IP，某些依赖 IP 直连、本地 hosts 或特定 DNS 解析的加速器可能异常。

可以尝试：

- 对 Steam 加速器进程使用直连；
- 对相关域名关闭 Fake-IP；
- 使用 Redir-Host 或普通 DNS 模式测试；
- 把加速器加入绕过列表。

---

## 七、实际推荐方案

### 如果你只是想正常访问 Steam 商店和社区

推荐：

```text
使用 Clash Verge 即可
关闭额外 Steam 加速器
```

避免双代理。

---

### 如果你只是下载游戏慢

推荐：

```text
Steam 下载相关流量直连
关闭或绕过 Steam 加速器
更换 Steam 下载服务器/区域
```

---

### 如果你玩联机游戏

推荐：

```text
游戏流量交给游戏加速器
Clash 只处理浏览器、聊天、下载等普通流量
不要让 Clash TUN 全局接管游戏流量
```

---

## 八、总结

Steam 加速器本质通常是：

> 针对 Steam 商店、社区、下载或游戏流量做定向代理、线路优化、路由接管或中转加速。

它和 Clash Verge **可能冲突**，尤其是当它们同时做这些事情：

1. 修改系统代理；
2. 开启 TUN/虚拟网卡；
3. 修改 DNS；
4. 修改 hosts；
5. 监听相同本地端口；
6. 全局接管路由；
7. 处理同一段 Steam 或游戏流量。

最稳妥的使用方式是：

```text
同一时间只保留一个全局代理/接管工具。
Steam 下载尽量直连。
Steam 商店/社区可以用 Clash 规则处理。
联机游戏优先使用专门游戏加速器，并避免 Clash 干扰。
```

如果你告诉我你具体是用哪种 Steam 加速器，以及 Clash Verge 是否开了系统代理、TUN/增强模式，我可以帮你判断更具体的冲突点和配置思路。


---
🙋**user**:
---
```
TUN模式到底是什么？我现在用clash verge的方法很简单，就是开启系统代理。大概原理我也明白，就是网络连接本来走443端口的，现在开启7897端口，然后这些网络流量在443和7897之间作桥接转发。我的理解没错吧？
我看TUN模式的简介说是让某些特殊应用（不遵循系统代理模式）也可以享用代理。什么意思呢？
```

---
🤖**assistant**:
---

你的大方向是对的，但有一个关键细节要修正：

> **不是“原本走 443 的流量被自动改到 7897”**，而是“支持系统代理的应用会主动先连接本地 7897 代理端口，然后由 Clash 替你去连接目标网站的 443 端口”。

也就是说：

```text
443 是目标服务器的端口
7897 是你本机 Clash 监听的代理端口
```

它们不是简单的本机端口映射关系。

---

# 一、你现在开的“系统代理”是什么原理？

你现在用的方式大概是：

```text
Windows 系统代理 → 127.0.0.1:7897 → Clash Verge → 代理节点 → 目标网站
```

以访问一个 HTTPS 网站为例：

## 不开系统代理时

浏览器直接访问：

```text
浏览器 → example.com:443
```

流程大概是：

```text
你的电脑
  ↓
直接连接 example.com 的 443 端口
```

---

## 开启系统代理后

如果浏览器遵循系统代理，它会先连接 Clash：

```text
浏览器 → 127.0.0.1:7897 → Clash
```

然后浏览器会告诉 Clash：

```text
我要访问 example.com:443
```

对于 HTTPS，通常会使用类似 `CONNECT example.com:443` 的请求。

然后 Clash 再根据规则决定：

```text
直连？
走代理节点？
拒绝？
```

如果走代理，实际路径可能是：

```text
浏览器
  ↓
127.0.0.1:7897
  ↓
Clash 内核
  ↓
远端代理节点
  ↓
example.com:443
```

所以你说的“桥接转发”可以这么理解，但更准确地说是：

> **浏览器主动连接本地代理端口，由代理软件替你建立到目标服务器 443 端口的连接，并在中间转发数据。**

---

# 二、为什么系统代理不能代理所有软件？

因为系统代理本质上是一种“建议”或“接口”，不是强制接管。

Windows、macOS 的系统代理设置大概是告诉应用：

> “如果你要上网，可以走这个代理：127.0.0.1:7897。”

但是，应用可以选择：

1. 听从系统代理；
2. 不听从系统代理；
3. 自己有代理设置；
4. 完全不走 HTTP/HTTPS 代理；
5. 直接发 TCP/UDP 原始网络包。

---

## 哪些软件通常会遵循系统代理？

常见的是浏览器和部分 HTTP 客户端：

```text
Chrome
Edge
Firefox，取决于设置
很多基于 HTTP/HTTPS 的桌面客户端
部分下载器
部分 IDE / 工具
```

例如你开系统代理后，浏览器一般能走 Clash。

---

## 哪些软件可能不遵循系统代理？

很多软件不会读系统代理设置，比如：

```text
游戏客户端
游戏联机进程
某些语音软件
某些 P2P 下载
某些命令行工具
某些旧软件
某些 UDP 流量
某些系统服务
某些 VPN / 加速器组件
```

例如：

```text
Steam 商店页面可能走 HTTP/HTTPS
Steam 下载可能走自己的下载通道
游戏联机经常走 UDP
```

这些不一定都乖乖使用你的系统代理。

---

# 三、“某些特殊应用不遵循系统代理模式”是什么意思？

意思就是：

> 这些应用不会因为你开了系统代理，就把自己的网络请求发给 `127.0.0.1:7897`。

它们会直接创建自己的网络连接，例如：

```text
游戏进程 → 目标游戏服务器:27015/3478/3074 等
```

或者直接发：

```text
TCP
UDP
ICMP
```

这类流量不会经过系统代理设置的 `127.0.0.1:7897`。

所以如果你只开系统代理，就会出现：

```text
浏览器可以代理
但游戏不能代理
Steam 某些组件不走代理
某些终端工具不走代理
某些后台服务不走代理
```

---

# 四、TUN 模式到底是什么？

TUN 模式可以理解成：

> **Clash 创建一个虚拟网卡，然后让操作系统把网络流量路由到这个虚拟网卡里，从而实现更底层的流量接管。**

它不是“应用主动把流量交给 Clash”，而是：

```text
操作系统层面把 IP 包交给 Clash 处理
```

简单流程：

```text
应用发出网络请求
  ↓
操作系统网络栈
  ↓
虚拟网卡 TUN
  ↓
Clash 内核
  ↓
根据规则直连 / 代理 / 拒绝
```

---

## 系统代理模式

```text
应用是否主动遵守代理？
        ↓
是 → 走 127.0.0.1:7897 → Clash
否 → 直接出去
```

---

## TUN 模式

```text
应用是否遵守代理？不重要
        ↓
操作系统把 IP 包路由到 TUN 虚拟网卡
        ↓
Clash 接管
        ↓
按规则处理
```

所以 TUN 的关键是：

> **它不是靠应用自觉，而是靠系统路由/虚拟网卡把流量送进来。**

---

# 五、TUN 是虚拟网卡吗？

可以这么理解。

TUN 通常是一个三层虚拟网卡，处理的是 IP 包。

常见网络栈分层可以粗略理解为：

```text
应用层：浏览器、游戏、Steam 客户端
传输层：TCP / UDP
网络层：IP
数据链路层：网卡 / MAC
```

系统代理主要影响的是“应用层/部分 HTTP 客户端的行为”。

TUN 则更靠近底层：

```text
应用发出请求
  ↓
TCP/UDP/IP 包
  ↓
TUN 虚拟网卡
  ↓
Clash 用户态网络栈处理
```

因此它可以处理很多系统代理管不到的流量。

---

# 六、TUN 模式能代理哪些系统代理代理不了的东西？

比如：

## 1. 游戏联机流量

很多游戏使用 UDP：

```text
UDP → 游戏服务器
```

普通系统代理主要是 HTTP/HTTPS/SOCKS 场景，不一定能处理游戏 UDP。

TUN 可以把这些 IP 包抓进来，然后决定是否转发。

---

## 2. 不读系统代理的软件

有些软件直接调用底层 socket，不关心系统代理。

例如：

```text
某些命令行工具
某些下载器
某些旧软件
某些系统服务
```

TUN 可以强制接管。

---

## 3. DNS 请求

有些 DNS 请求不走系统代理。

TUN 模式下，Clash 可以配合 DNS 设置处理域名解析，例如：

```text
fake-ip
redir-host
dns hijack
```

这也是为什么 TUN 模式经常要配合 DNS 设置。

---

## 4. 非 HTTP/HTTPS 流量

系统代理通常对 HTTP/HTTPS 最友好。

TUN 可以处理更广泛的 IP 流量，包括：

```text
TCP
UDP
ICMP，取决于实现和配置
```

---

# 七、一个比喻

## 系统代理像小区门口的指示牌

小区门口立了个牌子：

```text
要外出的人请走这个代理门：127.0.0.1:7897
```

听话的人会走这个门。

不听话的人直接翻墙出去了。

---

## TUN 模式像把小区所有出口都改道到保安亭

不管你想从哪个门出去，系统都会把你先带到保安亭。

保安亭就是 Clash。

然后 Clash 决定：

```text
你可以直接出去
你必须走代理
你不能出去
```

---

# 八、你的理解哪里对，哪里需要修正？

你说：

> 网络连接本来走 443 端口的，现在开启 7897 端口，然后这些网络流量在 443 和 7897 之间作桥接转发。

这里需要修正一下。

## 对的部分

你理解了：

```text
代理端口和本地端口之间会转发流量
```

这个方向没问题。

---

## 需要修正的部分

不是这样：

```text
目标网站的 443 端口流量被自动搬到本地 7897
```

而是这样：

```text
支持代理的应用主动连接本地 7897
然后 Clash 替你连接目标网站的 443
```

也就是：

```text
浏览器 → 127.0.0.1:7897 → Clash → 目标网站:443
```

而不是：

```text
目标网站:443 的数据直接变成本机:7897
```

---

# 九、系统代理和 TUN 的区别表

| 项目 | 系统代理 | TUN 模式 |
|---|---|---|
| 工作层级 | 应用层/系统代理设置 | 网络层，虚拟网卡/路由 |
| 是否需要应用配合 | 需要 | 不需要 |
| 能处理浏览器 | 通常可以 | 可以 |
| 能处理不走代理的软件 | 不一定 | 通常可以 |
| 能处理 UDP | 有限 | 更容易 |
| 能处理游戏联机 | 通常不好说 | 更有机会 |
| 能接管整个系统流量 | 不一定 | 可以 |
| 配置复杂度 | 简单 | 较复杂 |
| 冲突风险 | 相对低 | 相对高 |
| 对 Steam/游戏影响 | 视应用而定 | 可能全局接管 |

---

# 十、为什么 TUN 模式能让“不遵循系统代理的应用”也走 Clash？

因为这些应用虽然不读系统代理，但它们发出的流量仍然要经过操作系统网络栈。

TUN 模式通过虚拟网卡/路由表，让操作系统把这些流量送进 Clash。

例如：

## 只开系统代理

```text
游戏进程 → 直接发 UDP → 游戏服务器
```

Clash 不一定能管到。

---

## 开 TUN

```text
游戏进程 → 操作系统网络栈 → TUN 虚拟网卡 → Clash → 规则处理
```

这时即使游戏不读系统代理，它发出的 IP 包也可能被 Clash 接管。

---

# 十一、但 TUN 不是万能的

TUN 能接管流量，不代表一定适合所有场景。

如果规则不好，可能会出问题。

例如：

```text
Steam 下载被 TUN 接管
↓
Clash 把它送到远端代理节点
↓
下载反而变慢
```

或者：

```text
游戏 UDP 被 TUN 接管
↓
经过不支持/不适合的节点
↓
延迟更高、丢包、掉线
```

再比如：

```text
局域网流量被 TUN 接管
↓
无法访问路由器、打印机、NAS、WSL、虚拟机
```

所以 TUN 模式通常需要配合规则：

```text
局域网地址 → 直连
国内网站 → 直连
Steam 下载 → 直连
游戏 → 视情况直连或绕过
海外网站 → 代理
```

---

# 十二、结合你之前的 Steam 加速器问题

如果你只是：

```text
开 Clash Verge 系统代理
浏览网页 / 打开 Steam 商店
```

那一般比较简单。

但如果你开了：

```text
Clash Verge TUN 模式
```

那么 Clash 就可能把更多流量吸进来，包括：

```text
Steam 客户端
Steam 下载
游戏进程
加速器进程
语音软件
系统更新
```

这时如果你又开了一个 Steam 加速器，而那个加速器也做路由、虚拟网卡、进程代理、hosts、DNS，冲突概率就会明显变大。

所以对你来说可以这样理解：

```text
只开系统代理：影响面相对小
开启 TUN：影响面更大，更容易和加速器/游戏/Steam 下载互相影响
```

---

# 十三、你现在这种用法，有必要开 TUN 吗？

如果你目前只是：

- 浏览器翻墙；
- 偶尔打开 Steam 商店/社区；
- 不涉及游戏联机；
- 没有特殊软件必须走 Clash；
- 下载速度正常；

那么：

```text
只用系统代理通常就够了
```

没必要开 TUN。

---

如果你有以下需求，才考虑 TUN：

1. 某些软件不走系统代理，但想让它们走 Clash；
2. 想处理某些 UDP 流量；
3. 想全局接管系统流量；
4. 想处理 DNS；
5. 某些终端、开发工具、虚拟机、WSL 场景需要更彻底的网络控制。

但开 TUN 前建议做好规则，避免误伤：

```text
Steam 下载
游戏联机
局域网
NAS
打印机
WSL
虚拟机
加速器
```

---

# 十四、最简短总结

你原来的理解可以改成这样：

> 开启系统代理后，支持系统代理的应用会先连接 Clash 的本地端口，比如 7897，然后由 Clash 替它连接目标服务器的 443 或其他端口，并在中间转发流量。

而 TUN 模式是：

> Clash 创建虚拟网卡，让操作系统把原本不走系统代理的网络流量也路由进来，从而由 Clash 统一处理。

一句话区分：

```text
系统代理：应用自愿把流量交给 Clash
TUN：操作系统把流量强制交给 Clash
```

所以“某些特殊应用不遵循系统代理模式”的意思就是：

> 这些应用根本不看你的系统代理设置，所以系统代理对它们无效；而 TUN 通过虚拟网卡/路由层接管流量，因此可以让它们也经过 Clash。


---
🙋**user**:
---
```
我不想下载各种加速器之类的软件，我怕它们瞎搞我的电脑。我希望自己写程序或者脚本去给steam商店、steam游戏加速。我该怎么做？
```

---
🤖**assistant**:
---

可以，但先说结论：

> **你能自己写脚本/程序优化 Steam 商店、社区、下载和网络诊断；但很难完全替代商业游戏加速器，尤其是“Steam 游戏联机加速”这部分。**  
> 因为真正影响游戏延迟的是：你的运营商 → 国际/跨省链路 → 游戏服务器之间的线路质量。  
> 脚本本身不能凭空变出一条更好的物理线路，它只能做：**分流、选路、测速、DNS 修复、端口优化、绕过错误代理**。

另外，你不想装各种加速器是对的。很多加速器会装虚拟网卡、驱动、修改路由表、改 hosts、装证书，风险确实比普通代理软件高。

下面我给你一套**尽量不折腾系统、不装驱动、不乱改系统**的方案。

---

# 一、先分清你要加速的是哪一种 Steam 流量

Steam 至少分三类流量：

| 类型 | 举例 | 是否容易自己优化 |
|---|---|---|
| Steam 商店 / 社区 | 商店页面、社区、创意工坊、个人资料、聊天 | 相对容易 |
| Steam 下载 | 游戏下载、更新 | 通常应直连，不适合走远端代理 |
| Steam 游戏联机 | 游戏服务器、P2P 联机、语音 | 最难，脚本作用有限 |

你需要分别处理。

---

# 二、Steam 商店 / 社区：最适合你自己做

这部分一般是 HTTPS 网页流量，适合用 Clash 规则、浏览器代理、PAC、DNS 优化处理。

你现在已经开了 Clash Verge 的系统代理，那么最简单、最安全的方案是：

> **继续只用系统代理，不开 TUN；在 Clash 规则里单独处理 Steam 域名。**

也就是说，不要让所有流量都走代理，也不要让 Steam 下载被误代理。

---

## 1. 最安全思路：Clash 规则分流

例如：

```text
Steam 商店 / 社区 / 登录 → 走你的代理节点
Steam 下载 / CDN → 直连
游戏联机 → 直连，或绕过
```

不要写成：

```text
所有流量 → 代理
```

否则 Steam 下载和游戏可能被绕到很远的节点，反而更慢。

---

## 2. 可以加入的 Steam 商店/社区规则

下面给你一个保守版本。  
注意：不同 Clash 内核和配置里代理策略名不一样，可能是：

```text
PROXY
Proxy
DIRECT
REJECT
🚀 节点选择
♻️ 自动选择
```

你需要把下面的 `PROXY` 替换成你自己的代理策略组名。

---

### Steam 商店/社区代理规则示例

```yaml
rules:
  # 局域网直连
  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
  - IP-CIDR,127.0.0.0/8,DIRECT,no-resolve

  # Steam 下载 / CDN 尽量直连
  - DOMAIN-SUFFIX,steamcontent.com,DIRECT
  - DOMAIN-SUFFIX,steamcdn-a.akamaihd.net,DIRECT
  - DOMAIN-SUFFIX,cdn.cloudflare.steamcontent.com,DIRECT
  - DOMAIN-SUFFIX,cdn.akamai.steamcontent.com,DIRECT

  # Steam 商店 / 社区 / 登录相关
  - DOMAIN,store.steampowered.com,PROXY
  - DOMAIN,api.steampowered.com,PROXY
  - DOMAIN,login.steampowered.com,PROXY
  - DOMAIN,help.steampowered.com,PROXY
  - DOMAIN,steamcommunity.com,PROXY
  - DOMAIN-SUFFIX,steamcommunity.com,PROXY
  - DOMAIN-SUFFIX,steamusercontent.com,PROXY

  # Steam 静态资源：先尝试直连，不行再改代理
  - DOMAIN,community.cloudflare.steamstatic.com,PROXY
  - DOMAIN-SUFFIX,steamstatic.com,DIRECT
```

这里有个细节：

```yaml
- DOMAIN-SUFFIX,steamstatic.com,DIRECT
```

`steamstatic.com` 很多是图片、CSS、头像、静态资源。  
如果全部代理，可能反而慢；但如果某些社区图片加载异常，可以把部分 `steamstatic.com` 子域改成代理。

你可以先从直连开始，发现哪个资源加载失败，再加精确规则。

---

## 3. 如果你想更省事，可以用域名后缀

更激进一点：

```yaml
rules:
  - DOMAIN-SUFFIX,steamcontent.com,DIRECT
  - DOMAIN-SUFFIX,steamcdn-a.akamaihd.net,DIRECT

  - DOMAIN-SUFFIX,steampowered.com,PROXY
  - DOMAIN-SUFFIX,steamcommunity.com,PROXY
  - DOMAIN-SUFFIX,steamusercontent.com,PROXY
  - DOMAIN-SUFFIX,steamstatic.com,DIRECT
```

这种写法简单，但可能会把一些你不希望代理的子域也代理。  
所以建议你先用精确域名，再逐步看日志调整。

---

## 4. 在 Clash Verge 里怎么观察是否生效？

你可以打开 Clash Verge 的：

```text
连接 / Connections
日志 / Logs
```

然后访问：

```text
https://store.steampowered.com
https://steamcommunity.com
```

看日志里有没有出现：

```text
store.steampowered.com
steamcommunity.com
api.steampowered.com
```

如果这些请求走了你的代理策略，说明规则生效。

如果你访问 Steam 商店时日志里完全没有相关请求，说明：

1. 你没开系统代理；
2. 浏览器不走系统代理；
3. 你是在 Steam 客户端内打开商店，而 Steam 客户端没有走系统代理；
4. 浏览器用了自己的代理设置，比如 SwitchyOmega；
5. 规则被其他规则提前命中。

---

# 三、Steam 客户端内的商店不一定走系统代理

这是一个重点。

你用浏览器访问：

```text
https://store.steampowered.com
```

一般会遵循 Windows 系统代理，所以能走 Clash。

但是 Steam 客户端里面的商店页面，不一定完全遵循系统代理。  
它有自己的网络栈、内置浏览器、下载器、聊天组件。

所以可能出现：

```text
浏览器打开 Steam 商店正常
Steam 客户端内商店仍然慢或打不开
```

如果你不想开 TUN，也不想装进程代理工具，那么最简单的替代方案是：

> **尽量用外部浏览器访问 Steam 商店和社区。**

例如：

```text
Chrome / Edge / Firefox 打开 Steam 商店
浏览器走 Clash 系统代理
```

这是最安全、最可控的方式。

---

# 四、Steam 下载：通常不要代理

Steam 下载流量建议：

```text
DIRECT
```

也就是直连。

原因很简单：  
Steam 下载走的是 CDN/内容服务器，通常直连到离你较近的下载服务器更快。  
如果走代理节点绕一圈，可能更慢。

例如：

```text
你的电脑
  ↓
代理节点
  ↓
Steam 下载服务器
```

通常不如：

```text
你的电脑
  ↓
运营商直连
  ↓
Steam 下载服务器
```

---

## 1. Steam 下载优化脚本能做什么？

脚本能做的比较有限，但可以帮你：

1. 自动测试不同 Steam 下载区域的连通性；
2. 提醒你修改 Steam 下载区；
3. 检测是否开启了带宽限制；
4. 检测本地网络是否有线、Wi-Fi 信号是否稳定；
5. 备份/恢复网络配置；
6. 检查是否被其他代理软件影响。

但脚本不能直接让 Steam 下载服务器变快。

---

## 2. 下载慢时优先检查这些

你可以自己写一个检查脚本，按顺序检查：

```text
1. 是否使用 Wi-Fi？
2. 是否 5GHz？
3. 是否开启 Steam 带宽限制？
4. Steam 下载区域是否合适？
5. 是否开了 VPN / Clash TUN / 系统代理？
6. 是否有其他下载占满带宽？
7. 路由器是否过热或负载高？
8. 运营商是否在高峰期限速？
```

其中 Steam 客户端里可以检查：

```text
Steam → 设置 → 下载
```

重点看：

```text
下载区域
限制带宽
限制后台下载
```

---

# 五、Steam 游戏联机：自己写程序最难替代加速器

如果你说的“Steam 游戏加速”是指联机游戏，例如：

```text
Apex
Wallpaper Engine 不是
CS2
Dota 2
PUBG
Rust
L4D2
怪物猎人
人类一败涂地
双人成行
```

那么这类流量通常不是普通网页流量，而是：

```text
游戏客户端 → 游戏服务器 IP:端口
```

并且大量使用：

```text
UDP
```

例如：

```text
UDP 27000-27100
UDP 3478
UDP 4380
UDP 3074
```

具体端口取决于游戏。

---

## 1. 系统代理为什么对游戏联机基本没用？

因为系统代理主要影响的是：

```text
HTTP
HTTPS
部分 SOCKS-aware 应用
```

而游戏通常直接发：

```text
TCP
UDP
```

它不一定会读系统代理。

所以你可能遇到：

```text
浏览器能翻墙
Steam 商店能打开
但游戏仍然高延迟
```

这很正常。

---

## 2. 游戏加速器为什么可能有效？

商业游戏加速器通常做了这些事：

1. 创建虚拟网卡；
2. 修改进程路由；
3. 拦截游戏流量；
4. 把游戏流量送到专用中转节点；
5. 通过更好的运营商线路连接到游戏服务器；
6. 对 UDP 做低延迟转发；
7. 改善 NAT 类型；
8. 降低丢包。

也就是说，它不是简单改个端口，而是：

```text
游戏流量 → 加速器接管 → 专线/中转节点 → 游戏服务器
```

这类功能往往需要系统级权限。

如果你不想装这类软件，那么你就很难做到同样的效果。

---

## 3. 自己写脚本能给游戏做什么？

可以做这些“辅助优化”：

### 1. 测试游戏服务器延迟

例如测试某个游戏服务器 IP 是否通。

但注意：  
很多游戏服务器不响应普通 ping，所以 ICMP ping 不一定准。

---

### 2. 检测本机到游戏服务器的路由

例如：

```text
tracert 游戏服务器IP
```

可以看路径中哪里开始延迟变高。

---

### 3. 选择更合适的游戏区域

比如游戏里有：

```text
Asia
Southeast Asia
Japan
Korea
US West
EU
```

脚本可以帮你记录每次选择的延迟、丢包、稳定性。

---

### 4. 优化本地网络

例如检查：

```text
是否使用有线
是否开启 QoS
是否开启 UPnP
是否有 CGNAT
路由器是否 NAT4/Symmetric NAT
是否端口转发
是否 DMZ
```

这些对 P2P 联机有影响。

---

### 5. 避免游戏流量被 Clash 或 VPN 干扰

如果你开了 Clash 的 TUN，或者开了其他 VPN，游戏可能被错误路由。  
脚本可以帮你检查：

```text
是否开启虚拟网卡
是否存在多个默认网关
是否存在异常路由表
是否存在 VPN 网卡
是否存在代理软件监听端口
```

---

## 4. 但脚本不能解决什么？

脚本不能解决：

```text
你的运营商到游戏服务器的国际线路差
高峰时段拥塞
游戏服务器本身很远
运营商之间互联质量差
UDP 国际链路丢包严重
```

这些问题需要更好的线路，比如：

```text
优质中转节点
专线
IPLC/IEPL 类线路
低延迟跨国路由
```

这不是本地脚本能凭空创造的。

---

# 六、如果你想自己写程序，应该写什么？

我不建议你一上来写“加速器核心”。  
更安全、更实用的是写一个 **Steam 网络助手**。

它可以分为几个模块。

---

## 模块 1：网络诊断

功能：

```text
检查 DNS
检查 Steam 域名解析
检查 443 端口是否可达
检查常见 Steam 域名延迟
检查是否开启系统代理
检查是否开启 TUN/虚拟网卡
检查端口占用
```

这个最实用，也最安全。

---

## 模块 2：Clash 规则生成器

功能：

```text
自动生成 Steam 商店/社区规则
自动生成下载直连规则
自动生成游戏绕过规则
```

例如你维护一个列表：

```python
steam_web_domains = [
    "store.steampowered.com",
    "api.steampowered.com",
    "login.steampowered.com",
    "help.steampowered.com",
    "steamcommunity.com",
    "steamusercontent.com",
]

steam_direct_domains = [
    "steamcontent.com",
    "steamcdn-a.akamaihd.net",
]
```

然后生成：

```yaml
rules:
  - DOMAIN-SUFFIX,steamcontent.com,DIRECT
  - DOMAIN-SUFFIX,steamcdn-a.akamaihd.net,DIRECT
  - DOMAIN,store.steampowered.com,PROXY
  - DOMAIN,api.steampowered.com,PROXY
  - DOMAIN,login.steampowered.com,PROXY
  - DOMAIN,help.steampowered.com,PROXY
  - DOMAIN-SUFFIX,steamcommunity.com,PROXY
  - DOMAIN-SUFFIX,steamusercontent.com,PROXY
```

这比手动维护方便。

---

## 模块 3：Steam 下载区测试器

功能：

```text
测试不同 Steam 下载服务器域名或 IP 的 TCP 连接时间
输出推荐下载区域
```

但注意，Steam 下载服务器不一定允许你随便测，而且地址会变。  
所以它更多是辅助，不是绝对准确。

---

## 模块 4：游戏服务器测速器

功能：

```text
输入游戏服务器 IP/端口
测试 TCP 连接延迟
尝试 UDP 探测
记录历史结果
```

但注意：

1. 很多游戏服务器不响应任意 UDP 包；
2. 有些服务器只接受特定协议握手；
3. ICMP 可能被禁用；
4. 真实延迟最好看游戏内延迟。

---

## 模块 5：网络配置备份恢复

功能：

```text
备份 hosts
备份 DNS
备份路由表
备份网络适配器状态
检查是否被第三方软件修改
```

这很适合你这种不想被加速器乱改系统的人。

---

# 七、给你一套“自己写脚本”的推荐路线

我建议你按这个顺序来。

---

## 第一阶段：先用 Clash 规则，不写复杂程序

目标：

```text
Steam 商店/社区能访问
Steam 下载不被代理
游戏不被干扰
```

你只需要：

1. Clash Verge 开启系统代理；
2. 不开 TUN；
3. 不开增强模式；
4. 不开全局代理；
5. 使用规则模式；
6. 加入 Steam 规则。

这是最低风险方案。

---

## 第二阶段：写一个诊断脚本

例如用 PowerShell 写一个 `SteamCheck.ps1`。

简单示例：

```powershell
$domains = @(
    "store.steampowered.com",
    "steamcommunity.com",
    "api.steampowered.com",
    "login.steampowered.com",
    "cdn.cloudflare.steamcontent.com"
)

foreach ($domain in $domains) {
    Write-Host "===== $domain ====="

    try {
        $dns = Resolve-DnsName -Name $domain -Type A -ErrorAction Stop
        Write-Host "DNS 解析成功:" -ForegroundColor Green
        $dns | Select-Object IPAddress | Format-Table -AutoSize
    } catch {
        Write-Host "DNS 解析失败" -ForegroundColor Red
    }

    try {
        $tcp = Test-NetConnection -ComputerName $domain -Port 443 -WarningAction SilentlyContinue
        if ($tcp.TcpTestSucceeded) {
            Write-Host "443 端口连接成功" -ForegroundColor Green
        } else {
            Write-Host "443 端口连接失败" -ForegroundColor Red
        }
    } catch {
        Write-Host "443 端口测试异常" -ForegroundColor Red
    }

    Write-Host ""
}
```

你可以在 PowerShell 里运行：

```powershell
.\SteamCheck.ps1
```

如果提示执行策略，可以用：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

然后再运行。

这个脚本不会改你系统，只做检测。

---

## 第三阶段：写 Clash 规则生成器

例如 Python：

```python
steam_proxy_domains = [
    "store.steampowered.com",
    "api.steampowered.com",
    "login.steampowered.com",
    "help.steampowered.com",
    "steamcommunity.com",
]

steam_proxy_suffixes = [
    "steamcommunity.com",
    "steamusercontent.com",
]

steam_direct_suffixes = [
    "steamcontent.com",
    "steamcdn-a.akamaihd.net",
]

proxy_policy = "PROXY"  # 改成你自己的策略组名

rules = []

rules.append("# Steam 下载 / CDN 直连")
for domain in steam_direct_suffixes:
    rules.append(f"- DOMAIN-SUFFIX,{domain},DIRECT")

rules.append("")
rules.append("# Steam 商店 / 社区代理")
for domain in steam_proxy_domains:
    rules.append(f"- DOMAIN,{domain},{proxy_policy}")

for domain in steam_proxy_suffixes:
    rules.append(f"- DOMAIN-SUFFIX,{domain},{proxy_policy}")

print("rules:")
for rule in rules:
    print(f"  {rule}")
```

输出类似：

```yaml
rules:
  - DOMAIN-SUFFIX,steamcontent.com,DIRECT
  - DOMAIN-SUFFIX,steamcdn-a.akamaihd.net,DIRECT
  - DOMAIN,store.steampowered.com,PROXY
  - DOMAIN,api.steampowered.com,PROXY
  - DOMAIN,login.steampowered.com,PROXY
  - DOMAIN,help.steampowered.com,PROXY
  - DOMAIN-SUFFIX,steamcommunity.com,PROXY
  - DOMAIN-SUFFIX,steamusercontent.com,PROXY
```

然后你把生成的规则合并到 Clash 配置里。

---

# 八、不建议你自己写的东西

你既然怕软件瞎搞电脑，那下面这些不建议你自己做。

---

## 1. 不建议自己写驱动级网络过滤

驱动级过滤可以做很深的流量接管，但风险很高：

```text
蓝屏
断网
系统不稳定
安全漏洞
```

没有必要。

---

## 2. 不建议自己随意修改全局路由表

例如：

```text
route add 0.0.0.0 mask 0.0.0.0 ...
```

这类操作可能导致：

```text
断网
局域网不可用
游戏掉线
加速器冲突
```

除非你非常清楚每条路由的作用。

---

## 3. 不建议大量修改 hosts

hosts 只能解决一部分 DNS 问题。

而且 Steam 的 CDN IP 会变。  
你今天写的 IP，明天可能失效。

另外，HTTPS 还涉及证书和 SNI。  
如果你把某个 HTTPS 域名 hosts 到自己的本地服务器，但没有合法证书，浏览器会报证书错误。

所以除非你只是临时修复少量域名解析，否则不建议靠 hosts 做加速器。

---

## 4. 不建议自己装本地根证书

有些加速器为了处理 HTTPS，会安装本地证书，做中间人解密。  
这会带来安全风险。

你自己写程序时尽量避免：

```text
安装根证书
解密 HTTPS
替换系统证书
劫持 443 流量
```

---

# 九、如果你想加速游戏联机，可以怎么做？

在不装商业加速器的前提下，你能做的有这些。

---

## 1. 优先使用有线网络

无线对游戏影响很大：

```text
Wi-Fi 2.4GHz：容易干扰
Wi-Fi 5GHz：好很多，但穿墙差
有线：最稳定
```

如果你玩竞技游戏，建议：

```text
网线 > 5GHz Wi-Fi > 2.4GHz Wi-Fi
```

---

## 2. 路由器开启 QoS

如果你家有多个设备抢带宽，可以给游戏设备做 QoS。

例如：

```text
优先保障游戏电脑/主机
限制下载设备
限制视频设备
```

但 QoS 对不同路由器效果差异很大。

---

## 3. 检查 NAT 类型

很多联机游戏受 NAT 影响。

常见 NAT 类型：

```text
Open / Full Cone：较好
Moderate / Restricted：一般
Strict / Symmetric：较差
```

如果你是：

```text
CGNAT
大内网
Symmetric NAT
```

P2P 联机可能会差。

可以尝试：

```text
路由器开启 UPnP
给游戏设备做端口转发
必要时向运营商申请公网 IP
```

但注意：

- 不要随便把设备放进 DMZ；
- 端口转发只针对需要的端口；
- 公网 IP 会增加暴露面，注意防火墙。

---

## 4. 检查游戏服务器区域

很多游戏允许选择区域：

```text
Asia
Japan
Korea
Southeast Asia
US West
EU
```

脚本可以帮你记录不同区域的体验，但最终要看游戏内延迟。

---

## 5. 关闭无关代理/VPN

玩游戏时建议关闭：

```text
VPN
Clash TUN
全局代理
游戏加速器
其他虚拟网卡软件
```

只保留必要网络。

---

## 6. 如果必须自建中转，你需要有心理准备

理论上你可以：

```text
自己的低延迟服务器
  ↓
运行中继程序
  ↓
转发游戏流量
```

但问题是：

1. 你需要一台线路非常好的服务器；
2. 游戏流量常常是 UDP；
3. UDP 转发需要低丢包；
4. 很多游戏不能自定义服务器地址；
5. 你可能仍需要系统级路由或进程接管；
6. 效果不一定比商业加速器好；
7. 还要考虑带宽成本和稳定性。

所以自建游戏加速器通常不划算，除非你只是研究技术。

---

# 十、最适合你的现实方案

结合你“不想装加速器软件、怕系统被乱改”的需求，我建议你这样做：

---

## 方案 A：最安全方案

适合你目前这种只用系统代理的人。

```text
1. Clash Verge 只开系统代理
2. 不开 TUN
3. 不开增强模式
4. 使用规则模式
5. Steam 商店/社区走代理
6. Steam 下载直连
7. 游戏联机尽量直连，不让 Clash 管
8. 浏览器访问 Steam 商店/社区
```

这是我最推荐的。

---

## 方案 B：写一个本地 Steam 网络助手

你可以写一个只读型脚本工具，不改系统。

功能：

```text
检测 Steam 域名 DNS
检测 443 端口
检测当前代理端口
检测是否开启虚拟网卡
检测异常路由
检测端口占用
生成 Clash 规则
备份/恢复 hosts
```

这个方案安全，而且很适合你。

---

## 方案 C：只针对游戏做路由器优化

如果你主要想改善游戏联机，不要从电脑端乱装软件，可以从路由器入手：

```text
有线连接
QoS
UPnP
端口转发
检查 NAT 类型
检查公网 IP/CGNAT
选择游戏区域
```

这比装不明加速器软件更安全。

---

# 十一、你可以立刻做的配置

如果你现在只想快速改善，可以按这个来：

## 1. Clash Verge

保持：

```text
系统代理：开
TUN：关
增强模式：关
全局代理：关
规则模式：开
```

---

## 2. 加入 Steam 规则

把下面的规则合并到你的规则最前面附近，注意替换 `PROXY`：

```yaml
# 局域网直连
- IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
- IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
- IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
- IP-CIDR,127.0.0.0/8,DIRECT,no-resolve

# Steam 下载直连
- DOMAIN-SUFFIX,steamcontent.com,DIRECT
- DOMAIN-SUFFIX,steamcdn-a.akamaihd.net,DIRECT
- DOMAIN-SUFFIX,cdn.cloudflare.steamcontent.com,DIRECT
- DOMAIN-SUFFIX,cdn.akamai.steamcontent.com,DIRECT

# Steam 商店/社区代理
- DOMAIN,store.steampowered.com,PROXY
- DOMAIN,api.steampowered.com,PROXY
- DOMAIN,login.steampowered.com,PROXY
- DOMAIN,help.steampowered.com,PROXY
- DOMAIN-SUFFIX,steamcommunity.com,PROXY
- DOMAIN-SUFFIX,steamusercontent.com,PROXY
- DOMAIN,community.cloudflare.steamstatic.com,PROXY
- DOMAIN-SUFFIX,steamstatic.com,DIRECT
```

如果你发现某些静态资源加载慢，再把对应的 `steamstatic.com` 子域改成代理。

---

## 3. Steam 下载设置

进入：

```text
Steam → 设置 → 下载
```

检查：

```text
下载区域：选择离你近、速度稳定的区域
限制带宽：关闭或确认没有设太低
后台下载限制：按需设置
```

---

## 4. 游戏联机时

建议：

```text
关闭 VPN
关闭 Clash TUN，如果你开过的话
关闭不必要的代理
优先有线
```

如果你只开系统代理，大部分游戏不会走它。  
但仍建议玩游戏前观察一下是否异常。

---

# 十二、判断你的方案是否成功

你可以用这几个标准。

---

## 商店/社区是否成功？

看：

```text
浏览器打开 store.steampowered.com 是否正常
浏览器打开 steamcommunity.com 是否正常
图片是否加载
登录是否正常
创意工坊是否正常
```

同时看 Clash 日志，相关域名是否走代理。

---

## 下载是否成功？

看：

```text
Steam 下载速度是否接近你的宽带能力
下载时代理节点流量是否异常增大
```

如果一开 Clash 下载反而变慢，说明下载流量可能被代理了。  
需要把相关域名、进程或 IP 段改成直连。

---

## 游戏是否成功？

看：

```text
游戏内延迟
丢包率
匹配速度
是否掉线
NAT 类型
```

注意：  
脚本测出来的延迟只能参考，游戏内延迟最真实。

---

# 十三、最后给你一个明确结论

如果你不想装各种加速器，最推荐的路线是：

```text
不要写驱动
不要装虚拟网卡
不要乱改全局路由
不要大量改 hosts
不要装根证书
不要做全局 TUN
```

而是：

```text
用 Clash Verge 系统代理
写规则分流
浏览器访问 Steam 商店/社区
Steam 下载直连
游戏联机优先直连
自己写脚本做诊断、测速、规则生成
```

如果你只是要商店和社区：

> **Clash 规则 + 浏览器访问，基本够用。**

如果你要游戏下载：

> **直连 + 选合适下载区，比代理更靠谱。**

如果你要游戏联机：

> **本地脚本能辅助诊断和优化，但不能替代优质线路。真正低延迟通常需要更好的网络路径或中转线路。**

