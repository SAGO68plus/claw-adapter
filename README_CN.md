<p align="center">
  <a href="README.md">English</a> | <strong>中文</strong>
</p>

<p align="center">
  <img src="icon.png" width="120" alt="ClawAdapter">
</p>

<h1 align="center">ClawAdapter</h1>

<p align="center">
  <strong>轻量级 API 密钥与服务配置管理中间件</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
</p>

---

## 🚧 开发中

- API 站计价功能正在制作中

## 简介

管多个 AI 服务的 API Key 很烦——每个服务各自配置，改一个 key 要到处粘贴。

ClawAdapter 把服务商、密钥、下游服务的配置集中到一处管理，绑定之后改一次就能同步到所有关联的服务。

<p align="center">
  <img src="imgFrontPage.png?v=20260224" width="800" alt="ClawAdapter 界面">
</p>

## 架构

```
Vendor → Key → Provider → Adapter → Service
```

五层严格流向，不允许跳层。Provider 必须关联 Key，Key 必须属于 Vendor。

## 功能

| 功能 | 说明 |
|------|------|
| 🏢 服务商管理 | 集中管理 Vendor、Key、Provider |
| 🔌 适配器 | 当前支持 OpenClaw / SillyTavern / Claude Code Router，新增只需继承 BaseAdapter |
| 🔄 配置同步 | 绑定 Provider 到 Adapter，修改后自动同步 |
| 🔐 密钥加密 | Fernet 加密存储，密钥文件权限隔离 |
| 📊 拓扑可视化 | ECharts 桑基图展示完整配置链路 |

## 快速开始

### 安装依赖

```bash
pip install fastapi uvicorn cryptography python-multipart
```

### 启动

```bash
python main.py
```

默认运行在 `http://localhost:8900`。

首次启动会自动创建数据库、生成加密密钥、注册内置适配器。

> ⚠️ `.vault_key` 是所有 API Key 的加密根密钥，丢失后已存储的密钥无法解密。

## 扩展适配器

1. 在 `adapters/` 下新建文件，继承 `BaseAdapter`：

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

2. 在 `adapters/__init__.py` 中导入并注册。

## 项目结构

```
claw-adapter/
├── main.py              # FastAPI 入口
├── db.py                # 数据库 + 加密
├── models.py            # Pydantic 模型
├── adapters/
│   ├── base.py          # 适配器基类
│   ├── openclaw.py
│   ├── sillytavern.py
│   └── claude_code_router.py
├── routes/
│   ├── providers.py
│   ├── keys.py
│   ├── sync.py
│   ├── stats.py
│   ├── logs.py
│   └── upload.py
└── static/
    ├── index.html
    └── app.js
```

## 技术栈

- Python + FastAPI + Uvicorn
- SQLite (WAL) + Fernet 加密
- 原生 HTML/JS + ECharts

---

<p align="center">
  <sub>Licensed under the Apache License 2.0</sub>
</p>
