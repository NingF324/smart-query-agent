"""
数据库数据初始化脚本 - 执行 SQL 种子数据
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_URI
from sqlalchemy import create_engine

def main():
    """执行种子数据 SQL"""
    print("🌱 开始初始化数据库数据...")
    
    # 创建引擎
    engine = create_engine(DB_URI)
    
    # 读取种子数据 SQL
    seed_sql_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "seed_data.sql")
    
    with open(seed_sql_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 分割 SQL 语句
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
    
    # 执行每个语句
    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                conn.execute(stmt)
                conn.commit()
                if i % 10 == 0:
                    print(f"✅ 已执行 {i} 条语句")
            except Exception as e:
                print(f"⚠️  第 {i} 条语句执行失败: {e}")
                conn.rollback()
    
    print("\n🎉 数据初始化完成！")

if __name__ == "__main__":
    main()
