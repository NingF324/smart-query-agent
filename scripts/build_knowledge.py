"""
知识库构建脚本 - 自动从数据库读取 Schema 并构建向量知识库
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_URI
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService

def main():
    """自动构建知识库"""
    print("🚀 开始构建知识库...")
    
    # 初始化数据库服务
    db_service = DatabaseService(DB_URI)
    
    # 初始化知识库
    kb = KnowledgeBase()
    
    # 获取所有表名
    tables = db_service.get_table_names()
    print(f"📋 发现 {len(tables)} 张表: {', '.join(tables)}")
    
    # 为每个表构建知识库
    for table_name in tables:
        print(f"\n⚙️  处理表: {table_name}")
        
        # 获取 DDL
        ddl = db_service.get_table_schema(table_name)
        
        # 获取列信息
        columns = []
        inspector = db_service.engine.inspect(db_service.engine)
        col_info = inspector.get_columns(table_name)
        for col in col_info:
            columns.append({
                "name": col["name"],
                "type": str(col["type"])
            })
        
        # 添加到知识库
        kb.add_ddl(table_name, ddl, columns)
        print(f"✅ 已添加 {table_name} 到知识库")
    
    print("\n🎉 知识库构建完成！")
    print(f"📊 共处理 {len(tables)} 张表")

if __name__ == "__main__":
    main()
