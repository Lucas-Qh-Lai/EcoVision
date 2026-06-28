# 🌿 EcoVision 环保之眼

> **AI 驱动的实时垃圾分类识别系统**
>
> Version 2.0 · 2025-2026 · 泉州五中科技节项目

[English Docs](README.en.md)

---

## 📋 项目概述

**EcoVision** 是一个 AI 驱动的垃圾分类识别系统，通过浏览器摄像头或图片上传即可识别 **265 种** 生活垃圾。系统采用 **ConvNeXt-Base** 深度神经网络架构（ImageNet-22K 预训练 + 垃圾分类微调），支持 Apple Silicon GPU 加速（MPS）和 CPU 回退。

后端基于 **FastAPI** + **PyTorch** + **SQLite** 构建，前端为响应式网页界面，支持深/浅双主题切换。

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📷 实时摄像头拍摄 | 浏览器 WebRTC → Canvas → JPEG（质量 0.93，最大 800px） |
| 🤖 AI 精准识别 | ConvNeXt-Base，265 种垃圾类别，置信度 0.5% 过滤阈值 |
| 📋 处理指南 | 每类 8 条通用指南 + 25+ 种常见物品专属提示 |
| 📊 数据统计 | 总数、每日趋势、分类分布环形图、Top 20 物品排行 |
| 🌓 深/浅主题 | 明暗主题切换，localStorage 持久化，CSS 变量驱动 |
| 📱 响应式布局 | 三档断点：桌面 → 平板 → 手机 |
| 🔄 自动拍照 | 可选 3 秒间隔循环，定时器漂移补偿 |
| 🚀 MPS 加速 | Apple Silicon 原生 GPU 加速（M1–M4） |
| 🔒 输入校验 | base64 10MB 限制，Pydantic 字段校验，SQL 参数化查询 |

---

## 🧠 技术架构

```
┌─────────────────────┐     POST /api/predict      ┌──────────────────────────┐
│     浏览器客户端     │ ◄───── (base64 JPEG) ─────► │   FastAPI 服务端         │
│  ┌─────────────────┐ │     JSON 响应              │   Python 3.10+           │
│  │  index.html     │ │ ◄────── (PredictResponse) ─│                          │
│  │  app.js         │ │     GET /api/stats         │  ├─ /api/predict  POST   │
│  │  style.css      │ │ ◄────── (统计数据) ────────►│  ├─ /api/health   GET    │
│  └─────────────────┘ │     GET /api/health        │  ├─ /api/labels   GET    │
│  ┌─────────────────┐ │ ◄────── (状态) ───────────►│  ├─ /api/stats    GET    │
│  │  stats.html     │ │                            │  ├─ /api/stats/export    │
│  │  Chart.js 4.4.7 │ │                            │  └──/  /stats  (静态)    │
│  └─────────────────┘ │                            │                          │
└─────────────────────┘                            │  asyncio.to_thread()     │
                                                   │         │                │
                                                   │         ▼                │
                                                   │  ┌──────────────┐        │
                                                   │  │ classifier   │        │
                                                   │  │ .py          │        │
                                                   │  │ ConvNeXt-Base│        │
                                                   │  │ MPS / CPU    │        │
                                                   │  └──────┬───────┘        │
                                                   │         │                │
                                                   │  ┌──────▼───────┐        │
                                                   │  │ guides_db.py │        │
                                                   │  │ guides.json  │        │
                                                   │  └──────┬───────┘        │
                                                   │         │                │
                                                   │  ┌──────▼───────┐        │
                                                   │  │ ecovision_   │        │
                                                   │  │ stats.db     │        │
                                                   │  │ (SQLite WAL) │        │
                                                   │  └──────────────┘        │
                                                   └──────────────────────────┘
```

### 技术组件

| 层次 | 技术 | 说明 |
|------|------|------|
| **HTTP 服务** | FastAPI (uvicorn) | 异步 ASGI，lifespan 生命周期管理 |
| **AI 模型** | ModelScope ConvNeXt-Base | `iic/cv_convnext-base_image-classification_garbage` rev `v1.0.2` |
| **模型推理** | PyTorch 2.0+ | 手动绕过 pipeline：CPU 预处理 → GPU 推理 → CPU 后处理 |
| **后端** | Python 3.10+ | `threading.Lock` 保护分类器单例 |
| **数据库** | SQLite 3 | WAL 模式 + `synchronous=NORMAL`，7 列 |
| **前端** | 原生 JS (ES6) | fetch、Canvas 2D、getUserMedia WebRTC |
| **图表** | Chart.js 4.4.7 | 环形图（分类分布）+ 柱状图（每日趋势） |
| **校验** | Pydantic v2 | @field_validator base64 大小限制 |

---

## 📊 数据库结构

`ecovision_stats.db` — `recognition_log` 表：

```sql
CREATE TABLE recognition_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT    NOT NULL,       -- 如 "可回收物-饮料瓶"
    display_name TEXT    NOT NULL,       -- 如 "饮料瓶"
    category     TEXT    NOT NULL,       -- 如 "可回收物"
    confidence   REAL    NOT NULL,       -- 0.00–1.00
    inference_ms REAL    NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_log_created ON recognition_log(created_at);
```

---

## 📖 API 接口文档

### `POST /api/predict` — 实时识别

**请求**：
```json
{ "image": "data:image/jpeg;base64,..." }
```

**响应** (200)：
```json
{
  "success": true,
  "label": "可回收物-饮料瓶",
  "display_name": "饮料瓶",
  "category": "可回收物",
  "category_info": {"color": "#3B82F6", "icon": "♻️", "label": "可回收垃圾"},
  "confidence": 95.3,
  "top_predictions": [
    {"label": "可回收物-饮料瓶", "display_name": "饮料瓶", "score": 95.3}
  ],
  "guide": {
    "display_name": "饮料瓶",
    "category": "可回收垃圾",
    "color": "#3B82F6",
    "icon": "♻️",
    "tips": ["清洁干净后投入蓝色可回收物桶", "塑料瓶压扁后再投放，减少体积", ...]
  },
  "inference_ms": 72.5
}
```

**错误** (400 — 图片无效)：
```json
{ "detail": "图片解码失败: Invalid base64 string" }
```

### `GET /api/health` — 健康检查
```json
{
  "status": "ok",
  "classifier_loaded": true,
  "device": "mps",
  "mps_active": true,
  "guide_count": 265,
  "stats_db_size": 237568
}
```

### `GET /api/labels` — 标签列表
返回 `{"count": 265, "labels": ["可回收物-饮料瓶", ...]}`

### `GET /api/stats?days=7` — 统计数据
总数、平均置信度、分类分布、每日趋势、Top 20 物品。

### `GET /api/stats/export?days=7` — 导出记录
返回 JSON 数组（最多 10,000 行）。

### 静态路由

| 路径 | 文件 |
|------|------|
| `/` | `static/index.html` |
| `/stats` | `static/stats.html` |
| `/static/app.js` | 前端逻辑 |
| `/static/style.css` | 主题 + 布局 |

---

## 🚀 快速开始

### 环境要求

- Python ≥ 3.10
- pip
- 现代浏览器（Chrome/Safari/Firefox）
- （可选）Apple Silicon Mac 获取 MPS 加速
- （可选）摄像头（上传模式不需要）

### 安装与运行

```bash
cd EcoVision
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install modelscope datasets mmcv  # （可选）AI 识别依赖
python build_guides.py              # （一次性）构建指南数据库
uvicorn server:app --host 0.0.0.0 --port 8765
```

然后在浏览器打开 [前端页面](http://localhost:8765)。

### 快捷脚本

```bash
./start.sh   # 后台启动
./stop.sh    # 停止所有进程
```

**首次启动**：模型从 ModelScope 下载（约 500MB，约 25 秒）。之后从缓存加载，瞬间完成。

---

## 📁 项目结构

```
EcoVision/
├── server.py            # FastAPI：路由、数据库、生命周期
├── classifier.py        # AI：ConvNeXt 推理、MPS 加速、模型加载
├── guides_db.py         # 指南数据：分类、处理提示、图标
├── guides.json          # 预构建的 265 条指南条目
├── build_guides.py      # 从模型标签构建指南
├── model_labels.json    # 模型标签缓存（265 项）
├── requirements.txt     # Python 依赖
├── start.sh / stop.sh   # 启动/停止脚本
├── static/
│   ├── index.html       # 主页面
│   ├── app.js           # 前端逻辑
│   ├── style.css        # 主题 + 响应式布局
│   └── stats.html       # 数据统计仪表盘
├── .gitignore
├── LICENSE
└── README.*.md          # 本文档
```

---

## ⚙️ 配置说明

| 参数 | 默认值 | 位置 |
|------|--------|------|
| 端口 | 8765 | `start.sh` |
| 图片大小限制 | 10MB（base64） | `server.py:PredictRequest` |
| Canvas 最大尺寸 | 800px | `app.js` |
| 自动拍照间隔 | 3000ms | `app.js` |
| 日志记录阈值 | ≥0.50（50%） | `server.py` |
| 导出上限 | 10,000 行 | `server.py` |
| 模型版本 | `v1.0.2` | `classifier.py` |

---

## 🔒 安全特性

- ✅ SQL 参数化查询（无注入风险）
- ✅ Base64 大小校验（Pydantic，10MB 上限）
- ✅ PyTorch `weights_only=True` + 安全全局白名单
- ✅ 线程安全分类器（双检锁模式）
- ✅ XSS 防护（textContent + escapeHtml 函数）

---



---

## 🍎 Apple Silicon 优化说明

本系统针对 **Apple Silicon（M1–M4）** 芯片进行了深度优化：

- **MPS 后端加速**：自动检测并使用 Metal Performance Shaders 后端，将模型推理卸载到 GPU
- **统一内存架构**：CPU 和 GPU 共享内存，避免数据拷贝开销
- **自动回退**：检测到无 MPS 支持时自动切换为 CPU 推理
- **内存管理**：推理后主动调用 `torch.mps.empty_cache()` 释放 GPU 临时张量

> 其他平台（Intel Mac、Windows、Linux）默认使用 CPU 推理，性能约为 MPS 的 1/3 到 1/5。如有 NVIDIA GPU，可自行配置 CUDA 加速。

---

## 🪟 Windows 平台适配

系统在 Windows 环境下也可正常运行：

- **后端**：Python 标准库跨平台，FastAPI + uvicorn 在 Windows 上无兼容问题
- **前端**：支持 Chrome / Edge / Firefox 等主流浏览器，摄像头通过 WebRTC 访问
- **GPU 加速**：代码内置 CUDA 检测，如有 NVIDIA GPU 且安装 CUDA 版 PyTorch，推理自动使用 GPU（未经充分测试，不保证稳定性）
- **依赖安装**：与 macOS 安装步骤一致，推荐使用 PowerShell 或 Git Bash 运行

```bash
# Windows PowerShell 示例
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8765
```

## ⚡ 性能指标

> **注**：以下数据基于 MacBook Pro M1 Pro + Safari 实测，实际表现因设备、网络和浏览器而异。
> Apple Silicon 优化平台为 M1–M4 系列，其他平台性能不保证。

| 阶段 | 参考值 | 备注 |
|------|--------|------|
| 拍摄 → Canvas | < 20ms | 浏览器 Canvas 2D 渲染 |
| 图片传输 | ~30–80ms | 本地局域网，JPEG 压缩后 ~100KB |
| 模型推理（MPS，Apple Silicon） | 60–120ms | M1 Pro + Safari，MPS 加速推理 |
| 模型推理（CUDA，NVIDIA GPU） | 50–100ms | Windows/Linux，需自行安装 CUDA 版 PyTorch（未经实测） |
| 模型推理（CPU，其他平台） | 200–500ms | CPU 回退模式 |
| 总请求→响应（MPS） | 100–250ms | 含传输 + 推理 + 后处理 |
| SQLite 写入 | < 5ms | WAL 模式，< 1 万行 |

---

## 🤖 模型来源

本项目使用的 AI 模型来自 **ModelScope** 社区：

| 属性 | 内容 |
|------|------|
| **来源** | [ModelScope 模型库](https://modelscope.cn/models/iic/cv_convnext-base_image-classification_garbage/summary) |
| **模型 ID** | `iic/cv_convnext-base_image-classification_garbage` |
| **版本** | `v1.0.2` |
| **架构** | ConvNeXt-Base（ImageNet-22K 预训练 → 垃圾分类微调） |
| **框架** | PyTorch 2.0+ 通过 ModelScope pipeline |
| **许可证** | ModelScope License（研究及教育用途） |

---

## ©️ 致谢

本项目使用 **OpenAI Codex** 辅助开发 © 2025-2026

---

## 📝 开源许可证

本项目采用 **MIT 许可证** — 完全开放，可商用，可修改，无需额外授权。

- ✅ **商用**：可用于商业项目，无需付费
- ✅ **修改**：可自由修改、衍生
- ✅ **分发**：可重新分发，需保留原版权声明
- ❌ **无担保**：作者不承担任何使用风险

详见 [LICENSE](LICENSE) 文件。

<p align="center"><em>为环保意识而建 · Built for environmental awareness</em></p>
