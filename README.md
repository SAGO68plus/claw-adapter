<p align="center">
  <img src="icon.png" width="120" alt="ClawAdapter">
</p>

<h1 align="center">ClawAdapter</h1>

<p align="center">
  <strong>轻量级 API 密钥与服务配置管理中间件</strong><br>
  专为多 AI 服务环境设计
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/license-private-red" alt="License">
</p>

---

## ✨ 简介

ClawAdapter 统一管理你的 API 服务商、密钥和下游服务配置。通过绑定机制实现 **一处修改、多处同步**，告别在多个服务间反复粘贴 API Key 的痛苦。

## 🏗️ 架构

```
Vendor → Key → Provider → Adapter → Service
```

五层严格流向，不允许跳层。每个 Provider 必须关联 Key，每个 Key 必须属于 Vendor。

## 🚀 功能

| 功能 | 说明 |
|------|------|
| 🏢 服务商管理 | 集中管理 API 服务商（Vendor）、密钥（Key）、提供商（Provider） |
| 🔌 适配器系统 | Adapter Pattern 设计，当前支持 OpenClaw / SillyTavern / Claude Code Router |
| 🔄 配置同步 | 绑定 Provider 到 Adapter，支持自动同步配置到下游服务 |
| 🔐 密钥加密 | Fernet 对称加密存储所有 API Key，密钥文件权限隔离 |
| 📊 可视化拓扑 | ECharts 桑基图展示完整配置链路 |
| 🎨 单文件前端 | 内置 SPA 管理界面，OpenClaw 珊瑚红配色，无需额外构建 |

## 📦 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装依赖

```bash
pip install fastapi uvicorn cryptography python-multipart
```

### 启动服务

```bash
cd claw-adapter
python main.py
```

服务默认运行在 `http://localhost:8900`，打开浏览器访问即可。

### 首次运行

首次启动会自动：
- 📁 创建 SQLite 数据库 (`vault.db`)
- 🔑 生成加密密钥文件 (`.vault_key`)
- 🔌 注册内置适配器

> ⚠️ **重要：** `.vault_key` 是所有 API Key 的加密根密钥，请妥善保管。丢失后已存储的密钥将无法解密。

## 🧩 扩展适配器

新增服务只需两步：

**1.** 在 `adapters/` 下创建新文件，继承 `BaseAdapter`：

```python
from .base import BaseAdapter

class MyServiceAdapter(BaseAdapter):
    id = "myservice"
    label = "My Service"
    default_config_path = "/path/to/config"

    def read_current(self, config_path):
        ...

    def apply(self, config_path, base_url, api_key, **kwargs):
        ...
```

**2.** 在 `adapters/__init__.py` 中导入并注册。

## 📂 项目结构

```
claw-adapter/
├── main.py                # FastAPI 入口
├── db.py                  # 数据库 + Fernet 加密
├── models.py              # Pydantic 模型
├── adapters/
│   ├── base.py            # 适配器抽象基类
│   ├── openclaw.py        # OpenClaw 适配器
│   ├── sillytavern.py     # SillyTavern 适配器
│   └── claude_code_router.py
├── routes/                # API 路由
│   ├── providers.py       # 服务商 & Provider CRUD
│   ├── keys.py            # 密钥管理
│   ├── sync.py            # 配置同步
│   ├── stats.py           # 统计数据
│   ├── logs.py            # 请求日志
│   └── upload.py          # 图标上传
└── static/                # 前端 SPA
    ├── index.html
    └── app.js
```

## 🛠️ 技术栈

- **后端：** Python + FastAPI + Uvicorn
- **存储：** SQLite (WAL mode) + Fernet 对称加密
- **前端：** 原生 HTML/JS 单文件 SPA + ECharts 可视化

---

<p align="center">
  <sub>Private — 仅供个人使用</sub>
</p>
