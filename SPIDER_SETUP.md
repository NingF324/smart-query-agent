# Spider 数据集支持指南

本项目现已支持 Spider 数据集的完整测试流程。

## 📁 目录结构

```
E:/spider_data/spider_data/
├── database/          # SQLite 数据库和 schema.sql
├── dev.json          # 开发集测试用例
├── dev_gold.sql      # 开发集标准答案
├── test.json         # 测试集
├── test_gold.sql     # 测试集标准答案
├── tables.json       # 数据库表结构信息
└── ...              # 其他文件
```

## 🚀 完整流程

### 1. 转换 SQLite 到 PostgreSQL

Spider 数据集提供的是 SQLite 数据库，需要先转换为 PostgreSQL：

```bash
# 激活虚拟环境
source .venv/Scripts/activate  # Windows

# 转换所有所有数据库（166个）
python scripts/spider_to_postgres.py

# 只转换指定数量的数据库（用于快速测试）
python scripts/spider_to_postgres.py --max-db 5

# 只转换指定的数据库
python scripts/spider_to_postgres.py --db-list concert_singer employee
```

### 2. 构建 ChromaDB 知识库

有两种方式构建知识库：

#### 方式 A: 从 tables.json 构建（推荐）

```bash
# 使用 tables.json 文件构建
python scripts/build_spider_kb.py

# 只处理指定的数据库
python scripts/build_spider_kb.py --db-list concert_singer employee

# 只处理指定数量的数据库
python scripts/build_spider_kb.py --max-db 10
```

#### 方式 B: 从 PostgreSQL schema 构建

```bash
# 直接读取 PostgreSQL 中的 schema 信息
python scripts/build_spider_kb.py --use-postgres

# 只处理指定的数据库
python scripts/build_spider_kb.py --use-postgres --db-list concert_singer employee
```

### 3. 运行 Spider 测试

```bash
# 运行开发集测试（默认前 10 个）
python scripts/test_spider.py --max-tests 10

# 运行完整的开发集（1034个测试）
python scripts/test_spider.py --test-json E:/spider_data/spider_data/dev.json

# 只测试指定数据库
python scripts/test_spider.py --db-list concert_singer employee --max-tests 20

# 自定义输出路径
python scripts/test_spider.py --output results/my_test.csv
```

## 📊 测试输出

测试完成后会生成以下文件：

```
results/
├── spider_test_results.csv      # 详细测试结果
└── spider_test_results_metrics.json  # 评估指标
```

### CSV 文件格式

| 列名 | 说明 |
|-------|------|
| db_id | 数据库名称 |
| question | 自然语言问题 |
| gold_sql | 标准答案 SQL |
| predicted_sql | 模型生成的 SQL |
| execution_time | 执行时间（秒） |
| exact_match | 是否完全匹配 (True/False) |
| error | 错误信息（如果有） |

### 评估指标

```json
{
  "total": 10,              // 总测试数
  "correct": 8,            // 正确数
  "wrong": 2,              // 错误数
  "accuracy": 0.8,         // 准确率
  "avg_time": 3.25,        // 平均执行时间
  "by_database": {          // 按数据库统计
    "concert_singer": {
      "total": 5,
      "correct": 4,
      "accuracy": 0.8
    },
    ...
  }
}
```

## 🧪 快速示例

### 快速测试单个数据库

```bash
# 1. 启动 PostgreSQL 和 ChromaDB（如果还没启动）
docker-compose up -d db chromadb

# 2. 转换单个数据库
python scripts/spider_to_postgres.py --db-list concert_singer

# 3. 构建知识库（方式 A）
python scripts/build_spider_kb.py --db-list concert_singer

# 4. 运行测试
python scripts/test_spider.py --db-list concert_singer --max-tests 5
```

### 小规模完整流程测试

```bash
# 1. 转换 5 个数据库
python scripts/spider_to_postgres.py --max-db 5

# 2. 构建知识库
python scripts/build_spider_kb.py --max-db 5

# 3. 运行 20 个测试用例
python scripts/test_spider.py --max-tests 20
```

## 🔧 高级用法

### 自定义 PostgreSQL 连接参数

编辑 `scripts/spider_to_postgres.py` 中的连接参数：

```python
pg_params = {
    "host": "localhost",
    "port": 55432,
    "database": "spider",
    "user": "postgres",
    "password": "your_password"
}
```

### 指定测试集文件

```bash
# 使用测试集而非开发集
python scripts/test_spider.py \
  --test-json E:/spider_data/spider_data/test.json \
  --gold-sql E:/spider_data/spider_data/test_gold.sql \
  --max-tests 50
```

### 查看单个测试详情

```python
from scripts.test_spider import run_single_test, build_graph
from agent.state import create_initial_state

# 构建图
graph = build_graph()

# 运行单个测试
result = run_single_test(
    db_id="concert_singer",
    question="How many singers do we have?",
    gold_sql="SELECT count(*) FROM singer",
    graph=graph,
    db_uri="postgresql://postgres:password@localhost:55432/spider"
)

print(f"预测 SQL: {result.predicted_sql}")
print(f"完全匹配: {result.exact_match}")
```

## 📈 Spider 数据集信息

| 数据集 | 测试用例数 | 数据库数 |
|--------|-----------|---------|
| Dev | 1,034 | 20 |
| Test | 2,000 | 未知 |
| Train | 7,000 + 1,659 | 140 + 6 |

### 数据库示例

- `concert_singer` - 演唱会和歌手信息
- `employee` - 命工管理
- `bike_1` - 自行车租赁
- `network_1` - 网络管理
- `student_1` - 学生信息
- ... （共 166 个数据库）

## ⚠️ 注意事项

1. **内存要求**: 处理所有 166 个数据库需要较大内存，建议分批处理
2. **执行时间**: Spider 测试可能需要较长时间（复杂查询），建议设置合理超时
3. **知识库构建**: 使用 `--use-postgres` 方式可能更准确，但需要先完成数据库转换
4. **环境变量**: 确保 `.env` 文件中配置了 `DEEPSEEK_API_KEY`

## 🐛 问题排查

### 问题: 数据库连接失败

```
解决方案: 检查 PostgreSQL 服务是否启动
docker-compose logs db
```

### 问题: 知识库为空

```
解决方案: 确保先构建知识库再运行测试
python scripts/build_spider_kb.py --max-db 5
```

### 问题: 找不到 Spider 数据

```
解决方案: 检查路径是否正确，或修改脚本中的默认路径
E:/spider_data/spider_data/
```

## 📚 参考资料

- [Spider 数据集 GitHub](https://github.com/taoyds/spider)
- [Spider 论文](https://aclanthology.org/D18-1286/)
- [LangChain SQL Agent](https://docs.langchain.com/oss/python/langgraph/sql-agent)
