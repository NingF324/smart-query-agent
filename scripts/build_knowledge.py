"""
知识库构建脚本 - 自动从数据库读取 Schema 并构建向量知识库
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from config import DB_URI, CHROMA_HOST, CHROMA_PORT
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService


def main():
    """自动构建知识库"""
    print("🚀 开始构建知识库...")

    try:
        # 初始化数据库服务
        print("\n📦 初始化数据库服务...")
        db_service = DatabaseService(DB_URI)

        # 测试数据库连接
        if not db_service.test_connection():
            print("❌ 数据库连接失败，请检查配置")
            return

        # 初始化知识库
        print(f"📦 初始化知识库服务 ({CHROMA_HOST}:{CHROMA_PORT})...")
        kb = KnowledgeBase(host=CHROMA_HOST, port=CHROMA_PORT)

        # 清空旧知识库（可选）
        print("\n🗑️  清空旧知识库...")
        kb.clear_collection()

        # 获取所有表名
        tables = db_service.get_table_names()
        print(f"📋 发现 {len(tables)} 张表: {', '.join(tables)}")

        # 为每个表构建知识库
        for table_name in tables:
            print(f"\n⚙️  处理表: {table_name}")

            # 获取表信息
            table_info = db_service.get_table_info(table_name)
            ddl = db_service.get_table_schema(table_name)

            # 添加到知识库
            kb.add_ddl(
                table_name=table_name,
                ddl=ddl,
                columns=table_info['columns'],
                description=f"包含 {table_info['row_count']} 条记录"
            )
            print(f"✅ 已添加 {table_name} ({len(table_info['columns'])} 列, {table_info['row_count']} 行)")

        # 添加一些 SQL 示例
        print("\n📝 添加 SQL 示例...")
        sql_examples = [
            {
                "question": "查询本月订单总数",
                "sql": "SELECT COUNT(*) as order_count FROM orders WHERE EXTRACT(MONTH FROM order_date) = EXTRACT(MONTH FROM CURRENT_DATE)",
                "table": "orders"
            },
            {
                "question": "各品类的销售额排行",
                "sql": "SELECT p.category, SUM(oi.quantity * oi.unit_price) as total_sales FROM order_items oi JOIN products p ON oi.product_id = p.product_id GROUP BY p.category ORDER BY total_sales DESC",
                "table": "order_items, products"
            },
            {
                "question": "好评率最高的前10个产品",
                "sql": "SELECT p.product_name, AVG(r.rating) as avg_rating, COUNT(*) as review_count FROM reviews r JOIN products p ON r.product_id = p.product_id GROUP BY p.product_id, p.product_name HAVING COUNT(*) >= 5 ORDER BY avg_rating DESC LIMIT 10",
                "table": "reviews, products"
            },
            {
                "question": "各城市的用户分布",
                "sql": "SELECT city, COUNT(*) as user_count FROM users GROUP BY city ORDER BY user_count DESC",
                "table": "users"
            }
        ]

        for example in sql_examples:
            kb.add_sql_example(
                question=example['question'],
                sql=example['sql'],
                table_name=example['table']
            )
            print(f"✅ 已添加示例: {example['question']}")

        # 添加业务术语
        print("\n📚 添加业务术语...")
        terms = [
            {
                "term": "客单价",
                "definition": "平均每笔订单的金额，计算公式为总销售额除以订单数",
                "table": "orders"
            },
            {
                "term": "复购率",
                "definition": "重复购买的用户比例，反映用户忠诚度",
                "table": "orders, users"
            },
            {
                "term": "销售额",
                "definition": "订单金额的总和，反映业务收入",
                "table": "order_items"
            }
        ]

        for term in terms:
            kb.add_business_term(
                term=term['term'],
                definition=term['definition'],
                related_table=term['table']
            )
            print(f"✅ 已添加术语: {term['term']}")

        # 显示统计信息
        print("\n📊 知识库统计:")
        stats = kb.get_stats()
        print(f"   总数据量: {stats['total']}")
        print(f"   DDL 文档: {stats['ddl_count']}")
        print(f"   SQL 示例: {stats['sql_example_count']}")
        print(f"   业务术语: {stats['business_term_count']}")

        print("\n🎉 知识库构建完成！")

    except Exception as e:
        print(f"\n❌ 知识库构建失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n✨ 现在可以使用知识库进行检索了！")


if __name__ == "__main__":
    main()
