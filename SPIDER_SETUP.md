# Spider 数据集支持指南

本项目支持 Spider 数据集的完整测试流程，使用 SQLite 数据库（推荐，确保与基线可比性）。

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

### 1. 构建 ChromaDB 知识库

#### 方式 A: 从 tables.json 构建（推荐 - 快速）

```bash
# 使用 tables.json 文件构建
python scripts/build_spider_kb.py

# 只处理指定的数据库
python scripts/build_spider_kb.py --db-list concert_singer employee

# 只处理指定数量的数据库
python scripts/build_spider_kb.py --max-db 10
```

#### 方式 B: 从 SQLite 数据库构建（更准确）

```bash
# 直接读取 SQLite 数据库的 schema 信息
python scripts/build_spider_kb.py --use-sqlite

# 只处理指定的数据库
python scripts/build_spider_kb.py --use-sqlite --db-list concert_singer employee

# 只处理指定数量的数据库
python scripts/build_spider_kb.py --use-sqlite --max-db 5
```

### 2. 运行 Spider 测试

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
| exact_sql_match | SQL 文本是否完全匹配 (True/False) |
| exact_result_match | SQL 执行结果是否匹配 (True/False) |
|** error | 错误信息（如果有） |

### 评估指标

```json
{
  "total": 10,              // 总测试数
  "correct_sql": 8,         // SQL 文本匹配正确数
  "correct_result": 7,       // 执行结果匹配正确数
  "accuracy_sql": 0.8,      // SQL 文本准确率
  "accuracy_result": 0.7,    // 执行结果准确率
  "avg_time": 3.25,         // 平均执行时间
  "by_database": {            // 按数据库统计
    "concert_singer": {
      "total": 5,
      "correct_sql": 4,
      "correct_result": 4,
      "accuracy_sql": 0.8,
      "accuracy_result": 0.8
    },
    ...
  }
}
```

## 🧪 快速示例

### 快速测试单个数据库

```bash
# 1. 启动 ChromaDB（如果还没启动）
docker-compose up -d chromadb

# 2. 构建知识库（方式 A）
python scripts/build_spider_kb.py --db-list concert_singer

# 3. 运行测试
python scripts/test_spider.py --db-list concert_singer --max-tests 5
```

### 小规模完整流程测试

```bash
# 1. 使用 SQLite 构建 5 个数据库的知识库
python scripts/build_spider_kb.py --use-sqlite --max-db 5

# 2. 运行 20 个测试用例
python scripts/test_spider.py --max-tests 20
```

## 🔧 高级用法

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
    spider_db_path=Path("E:/spider_data/spider_data/database"),
    use_sqlite=True
)

print(f"预测 SQL: {result.predicted_sql}")
print(f"SQL 匹配: {result.exact_sql_match}")
print(f"结果匹配: {result.exact_result_match}")
```

## 📈 Spider 数据集信息

| 数据集 | 测试用例数 | 数据库数 |
|--------|-----------|---------|
| Dev | 1,034 | 20 |
| Test | 2,000 | 未知 |
| Train | 7,000 + 1,659 | 140 + 6 |

### 数据库示例

- `concert_singer` - 演唱会和歌手信息
- `employee` - 员工管理
- `bike_1` - 自行车租赁
- `network_1` - 网络管理
- `student_1` - 学生信息
- ... （共 166 个数据库）

## 💡 为什么使用 SQLite？

1. **与基线可比性**: Spider 官方和所有 SOTA 方法（RAT-SQL、GAP-SQL、T5、DIN-SQL）都使用 SQLite
2. **复现性**: 评审人可以下载 Spider 数据集直接复现，无需额外配置
3. **SQL 一致性**: 避免因 PostgreSQL 方言差异导致的评估偏差
4. **论文简洁性**: 聚焦 Text-to-SQL 核心贡献，无需解释数据库迁移

## ⚠️ 注意事项

1. **内存要求**: 处理所有 166 个数据库需要较大内存，建议分批处理
2. **执行时间**: Spider 测试可能需要较长时间（复杂查询），建议设置合理超时
3. **知识库构建**: 使用 `--use-sqlite` 方式更准确，但速度稍慢
4. **环境变量**: 确保 `.env` 文件中配置了 `DEEPSEEK_API_KEY`

## 🐛 问题排查

### 问题: ChromaDB 连接失败

```
解决方案: 检查 ChromaDB 服务是否启动
docker-compose logs chromadb
docker-compose up -d chromadb
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

### 问题: SQLite 数据库未找到

```
解决方案: 确保数据库路径正确
ls E:/spider_data/spider_data/database/concert_singer/
```

## 📚 参考资料

- [Spider 数据集 GitHub](https://github.com/taoyds/spider)
- [Spider 论文](https://aclanthology.org/D18-1286/)
- [LangChain SQL Agent](https://docs.langchain.com/oss/python/langgraph/sql-agent)

## 🔄 PostgreSQL 支持（可选）

如果需要测试 PostgreSQL 兼容性（用于论文讨论部分），可以使用：

```bash
# 首先转换 SQLite 到 PostgreSQL
python scripts/spider_to_postgres.py --db-list concert_singer

# 使用 PostgreSQL 运行测试
python scripts/test_spider.py --db-list concert_singer --max-tests 5 --use-postgres
```

**注意**: Spider 官方评估使用 SQLite，论文主要结果应基于 SQLite。
