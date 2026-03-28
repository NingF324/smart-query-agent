# 智能问数 Agent (Smart Query Agent)

> 基于 Multi-Agent + RAG 的自然语言数据库查询系统

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

## 📖 项目简介

智能问数 Agent 是一个毕业设计项目，旨在让非技术用户通过自然语言对数据库进行查询和分析。系统基于大语言模型（LLM），采用模块化智能体流水线架构，支持 Text-to-SQL 自动生成、智能纠错、多轮对话和结果可视化。

### 核心功能

- 🤖 **自然语言理解** - 准确解析中文自然语言查询意图
- 📝 **SQL 自动生成** - 根据用户意图自动生成正确的 SQL 语句
- 🔄 **智能纠错** - SQL 执行失败时自动分析原因并修正
- 📊 **结果可视化** - 将查询结果以表格和图表形式展示
- 💬 **多轮对话** - 支持上下文记忆的多轮对话交互
- 🛡️ **安全防护** - 防止 SQL 注入，确保数据库安全

## 🏗️ 技术架构

### 技术栈

| 类别 | 技术 |
|------|------|
| **后端** | Python 3.11+, Streamlit |
| **LLM** | DeepSeek API (deepseek-chat, deepseek-reasoner) |
| **Embedding** | DeepSeek API + bge-small-zh (本地降级) |
| **向量数据库** | ChromaDB |
| **数据库** | PostgreSQL 16 |
| **Agent 编排** | LangGraph + LangChain |
| **部署** | Docker + Docker Compose |

### 架构设计

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户界面   │────▶│  Agent 编排  │────▶│  数据库服务  │
│  Streamlit  │     │  LangGraph  │     │  PostgreSQL │
└─────────────┘     └─────────────┘     └─────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  知识库服务  │
                       │   ChromaDB  │
                       └─────────────┘
```

### Agent 流水线节点

1. **意图解析节点** - 分析用户查询意图，提取关键信息
2. **Schema 检索节点** - 从知识库检索相关表结构
3. **SQL 生成节点** - 基于 Schema 和意图生成 SQL
4. **SQL 校验节点** - EXPLAIN 校验 + LLM 修复
5. **SQL 执行节点** - 执行 SQL 并返回结果
6. **结果解释节点** - 将结果转换为自然语言描述

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Docker & Docker Compose
- DeepSeek API Key ([申请地址](https://platform.deepseek.com/))

### 1. 克隆项目

```bash
git clone https://github.com/NingF324/smart-query-agent.git
cd smart-query-agent
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=your_api_key_here
```

### 3. 使用 Docker 启动（推荐）

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 访问应用
# 浏览器打开: http://localhost:8501
```

### 4. 本地开发模式

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动 PostgreSQL 和 ChromaDB
docker-compose up -d db chromadb

# 运行应用
streamlit run app.py
```

## 📂 项目结构

```
smart-query-agent/
├── app.py                      # Streamlit 应用入口
├── config.py                   # 配置文件
├── requirements.txt            # Python 依赖
├── docker-compose.yml          # Docker 编排配置
├── Dockerfile                  # Docker 镜像构建
├── .env.example                # 环境变量模板
├── .gitignore
├── README.md
│
├── agent/                      # Agent 编排核心模块
│   ├── graph.py               # LangGraph StateGraph 定义
│   ├── nodes/                 # 图节点实现
│   │   ├── intent_parse.py    # 意图解析节点
│   │   ├── schema_retrieve.py # Schema 检索节点
│   │   ├── sql_generate.py    # SQL 生成节点
│   │   ├── sql_validate.py    # SQL 校验节点
│   │   ├── sql_execute.py     # SQL 执行节点
│   │   └── result_interpret.py# 结果解释节点
│   ├── prompts/               # Prompt 模板
│   └── state.py               # State 类型定义
│
├── services/                   # 基础服务模块
│   ├── llm_service.py         # LLM API 服务
│   ├── embedding_service.py   # Embedding 服务
│   ├── knowledge_base.py      # ChromaDB 知识库
│   └── db_service.py          # 数据库连接服务
│
├── data/                       # 数据目录
│   ├── init_db.sql            # 数据库初始化脚本
│   └── seed_data.sql          # 示例数据（电商场景）
│
└── scripts/                    # 脚本目录
    ├── build_knowledge.py      # 知识库构建脚本
    └── seed_data.py            # 数据生成脚本
```

## 💡 使用示例

### 示例查询

- "本月订单总数是多少？"
- "各品类的销售额排行"
- "最近30天的客单价趋势"
- "好评率最高的前10个产品"
- "各城市的用户分布"
- "上个月的复购率是多少？"

### 演示数据库

项目包含一个完整的电商演示数据库，包含以下表：

- **users** - 用户信息
- **products** - 产品信息
- **orders** - 订单信息
- **order_items** - 订单明细
- **reviews** - 商品评价

## 🧪 测试

```bash
# 运行测试
pytest tests/

# 生成测试报告
pytest tests/ --cov=services --cov-report=html
```

## 📊 开发进度

| 阶段 | 任务 | 状态 |
|------|------|------|
| Week 1 | 环境搭建与基础框架 | ✅ 完成 |
| Week 2 | 基础服务开发 | 🚧 进行中 |
| Week 3-4 | 核心 Agent 开发 | ⏳ 计划中 |
| Week 5 | 纠错机制与安全性 | ⏳ 计划中 |
| Week 6 | 前端与多轮对话 | ⏳ 计划中 |
| Week 7 | 测试与评估 | ⏳ 计划中 |
| Week 8 | 部署与论文 | ⏳ 计划中 |

详细的实现方案请参考 [智能问数Agent完整实现方案.md](智能问数Agent完整实现方案.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📧 联系方式

- 作者：NingF324
- 项目：智能问数 Agent（毕业设计）

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
