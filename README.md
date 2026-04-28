# 基于语义检索的增强型 Text-to-SQL 问数智能体

> 毕业设计项目 - 中南大学计算机学院

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)
[![Spider](https://img.shields.io/badge/Spider-EX%2075.1%25-brightgreen.svg)](https://yale-lily.github.io/spider)

## 📖 项目简介

本项目是一个基于语义检索增强的 Text-to-SQL 智能体系统，旨在提升自然语言到 SQL 查询的转换准确率和鲁棒性。系统采用 LangGraph 构建的多节点智能体流水线，集成 ChromaDB 向量数据库实现语义检索，支持复杂数据库模式下的自然语言查询。

**核心创新点**：
- 🔍 **三阶段混合语义检索** - 知识库向量搜索 + 排名补充 + 外键邻居扩展
- 🔄 **循环纠错机制** - SQL 校验与自修复，支持最多 3 次自动修正
- 🛡️ **多层安全防护** - SQL 注入检测 + EXPLAIN 预验证 + 执行超时控制

### 核心功能

- 🤖 **意图解析** - 识别查询类型、提取实体和时间范围，支持追问解析
- 🔍 **语义检索** - 基于 ChromaDB 的三阶段混合检索，精准筛选相关表结构
- 📝 **SQL 生成** - LLM 主路径 + 规则降级双策略，Few-shot 增强
- 🔄 **智能纠错** - EXPLAIN 验证 + 启发式修复 + LLM 修复，最多 3 次重试
- 📊 **结果可视化** - 自动生成柱状图、折线图、饼图（Plotly）
- 💬 **多轮对话** - 支持上下文记忆的自然语言交互
- 🛡️ **安全防护** - SQL 注入检测、语法验证、执行超时控制

## 🏗️ 技术架构

### 技术栈

| 类别 | 技术 |
|------|------|
| **编程语言** | Python 3.11+ |
| **LLM** | DeepSeek API (DeepSeek-V3, DeepSeek-R1) |
| **Embedding** | DeepSeek API + bge-small-zh (本地降级) |
| **向量数据库** | ChromaDB |
| **业务数据库** | PostgreSQL 16 / SQLite |
| **Agent 编排** | LangGraph + LangChain |
| **前端** | Streamlit |
| **部署** | Docker + Docker Compose |

### 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户界面   │────▶│  Agent 编排  │────▶│  数据库服务  │
│  Streamlit  │     │  LangGraph  │     │  PostgreSQL  │
└─────────────┘     └─────────────┘     └─────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  知识库服务  │
                       │   ChromaDB  │
                       └─────────────┘
```

### Agent 流水线架构（7节点 + 2条条件路由）

```
用户问题 → 意图解析 → Schema检索 → SQL生成 → SQL校验 → SQL执行 → 结果解释 → 回答
                                  ↑            ↓              ↓
                  (可修复/执行失败) ──── 循环纠错（最多3次）
                                              ↓
                                         错误响应
```

**7个核心节点**：
1. **意图解析节点** - 识别查询类型、提取实体和时间范围，支持追问解析
2. **Schema 检索节点** - 三阶段混合检索：向量搜索 + 排名补充 + 外键扩展
3. **SQL 生成节点** - LLM 主路径 + 规则降级，Few-shot 增强
4. **SQL 校验节点** - 安全检查 + EXPLAIN 验证 + 启发式修复 + LLM 修复
5. **SQL 执行节点** - 执行 SQL 查询，支持超时控制
6. **结果解释节点** - 将查询结果转换为自然语言描述
7. **错误响应节点** - 生成面向用户的错误提示（兜底节点）

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
│   │   ├── result_interpret.py# 结果解释节点
│   │   └── error_response.py  # 错误响应节点
│   ├── prompts/               # Prompt 模板
│   └── state.py               # AgentState 类型定义
│
├── services/                   # 基础服务模块
│   ├── llm_service.py         # LLM API 服务
│   ├── embedding_service.py   # Embedding 服务
│   ├── knowledge_base.py      # ChromaDB 知识库
│   ├── db_service.py          # 数据库连接服务
│   ├── conversation_service.py# 对话管理服务
│   ├── evaluation_service.py  # 评测服务
│   └── sql_utils.py           # SQL 工具函数
│
├── data/                       # 数据目录
│   ├── init_db.sql            # 数据库初始化脚本
│   ├── seed_data.sql          # 示例数据
│   └── spider_data/           # Spider 数据集
│
├── scripts/                    # 脚本目录
│   ├── build_knowledge.py      # 知识库构建脚本
│   ├── test_spider.py         # Spider 测试脚本
│   ├── evaluate.py            # 评测脚本
│   └── generate_figures.py    # 图表生成脚本
│
├── tests/                      # 测试目录
│   ├── test_agent.py          # Agent 测试
│   ├── test_services.py      # 服务测试
│   └── test_spider_eval.py   # Spider 评测测试
│
├── thesis/                     # 毕业论文（Typst 源码）
│   ├── main.typ              # 主文档
│   ├── chapters/             # 论文章节
│   ├── figures/              # 论文图片
│   └── ref.yml              # 参考文献
│
└── results/                    # 实验结果
    ├── spider_results.json    # Spider 测试结果
    └── figures/              # 结果可视化
```

## 💡 使用示例

### 示例查询

- "法国有哪些汽车制造商？"（简单查询）
- "2023年销售额最高的5个客户是谁？"（排行查询）
- "各个部门的员工数量是多少？"（聚合查询）
- "订单金额大于1000的客户有哪些？"（条件查询）
- "那上个月呢？"（多轮对话-追问）

### 支持的数据集

- **Spider 基准数据集** - 200+ 数据库，10285+ 自然语言查询
- **自定义数据库** - 支持任何 PostgreSQL/SQLite 数据库
- **演示数据库** - 包含多个示例数据库（演唱会、电商、人力资源等）

## 🧪 测试与评估

### 基础测试

```bash
# 运行单元测试
pytest tests/

# 生成测试报告
pytest tests/ --cov=services --cov-report=html
```

### Spider 数据集测试

本项目在 Spider Text-to-SQL 基准数据集上进行评估（1034 个测试用例）。

```bash
# 运行 Spider 测试
python scripts/test_spider.py --max-tests 20

# 完整评估
python scripts/test_spider.py --test-json data/spider_data/dev.json

# 生成评估报告
python scripts/evaluate.py --results results/spider_results.json
```

详细说明请参考 [SPIDER_SETUP.md](SPIDER_SETUP.md)。

## 📊 实验结果

### Spider 基准测试结果

| 指标 | 数值 |
|------|------|
| **执行准确率 (EX)** | **75.1%** |
| **精确匹配率 (EM)** | **15.6%** |
| 测试样本数 | 1034 |
| 相比早期版本提升 | +48.3 个百分点 |

### 错误分析

| 错误类型 | 占比 | 示例 |
|---------|------|------|
| 多余的 LIMIT | 60.0% | 生成了不必要的 LIMIT 子句 |
| 逻辑错误 | 22.8% | JOIN 路径错误或条件不完整 |
| 列别名差异 | 11.9% | 列名匹配不准确 |
| 其他 | 5.3% | 语法错误、超时等 |

### 消融实验

| 配置 | EX 准确率 | EM 准确率 |
|------|-----------|-----------|
| 无知识库检索 | 12.8% | 3.8% |
| 部分知识库检索 | 17.8% | 3.8% |
| 改进知识库检索 | 31.3% | 4.8% |
| **完整三阶段检索** | **75.1%** | **15.6%** |

## 📈 开发进度

| 阶段 | 任务 | 状态 |
|------|------|------|
| 2026年2月 | 调研与选题 | ✅ 完成 |
| 2026年3月 | 方案设计与调研报告 | ✅ 完成 |
| 2026年4月上旬 | 核心代码开发 | ✅ 完成 |
| 2026年4月中旬 | Spider 测试与优化 | ✅ 完成 |
| 2026年4月下旬 | 论文撰写 | 🚧 进行中 |
| 2026年5月 | 论文修改与答辩准备 | ⏳ 计划中 |
| 2026年6月 | 答辩与提交 | ⏳ 计划中 |

详细的实现方案请参考 [智能问数Agent完整实现方案.md](智能问数Agent完整实现方案.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📖 相关文献

If you use this project for research, please cite:

```bibtex
@thesis{chen2026smartquery,
  title={基于语义检索的增强型 Text-to-SQL 问数智能体的设计与应用},
  author={陈墨},
  school={中南大学计算机学院},
  year={2026},
  type={本科毕业论文}
}
```

## 📧 联系方式

- **作者**：陈墨（NingF324）
- **学校**：中南大学计算机学院
- **专业**：软件工程2206班
- **指导教师**：郁松
- **项目**：基于语义检索的增强型 Text-to-SQL 问数智能体（毕业设计）
- **GitHub**：https://github.com/NingF324/smart-query-agent

---

**⭐ 如果这个项目对你有帮助，请给个 Star！**
