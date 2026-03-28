"""Streamlit 应用入口"""
import streamlit as st
import pandas as pd
import plotly.express as px
from agent.graph import build_graph
from services.knowledge_base import KnowledgeBase
from services.db_service import DatabaseService
from config import DB_URI

st.set_page_config(
    page_title="🤖 智能问数 Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stChatMessage { border-radius: 12px; }
    .stCodeBlock { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

def init_services():
    """初始化服务"""
    if "db_service" not in st.session_state:
        st.session_state.db_service = DatabaseService(DB_URI)
    if "kb" not in st.session_state:
        st.session_state.kb = KnowledgeBase()
    if "agent_app" not in st.session_state:
        st.session_state.agent_app = build_graph()
    if "messages" not in st.session_state:
        st.session_state.messages = []

def auto_generate_chart(df: pd.DataFrame, question: str):
    """根据数据自动选择合适的图表类型"""
    if df.empty or len(df.columns) < 2:
        return None

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    text_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()

    if not numeric_cols:
        return None

    if "趋势" in question or "月" in question or "日" in question or "时间" in question:
        if len(numeric_cols) >= 1 and len(df) > 1:
            return px.line(df, x=df.columns[0], y=numeric_cols[0],
                         title="趋势分析")

    if "排行" in question or "最高" in question or "最低" in question or "前" in question:
        if text_cols and numeric_cols:
            sorted_df = df.sort_values(numeric_cols[0], ascending=False).head(10)
            return px.bar(sorted_df, x=text_cols[0], y=numeric_cols[0],
                         title="排行分析")

    if "分布" in question or "占比" in question:
        if text_cols and numeric_cols:
            return px.pie(df, values=numeric_cols[0], names=text_cols[0],
                         title="分布占比")

    if text_cols and numeric_cols:
        return px.bar(df.head(10), x=text_cols[0], y=numeric_cols[0])

    return None

def process_query(question: str):
    """处理用户查询 - 支持多轮对话"""
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    chat_history = st.session_state.messages[-10:]

    with st.spinner("🤔 正在分析您的问题..."):
        try:
            result = st.session_state.agent_app.invoke({
                "question": question,
                "messages": [],
                "chat_history": chat_history,
                "intent": {},
                "relevant_schemas": [],
                "generated_sql": "",
                "validation_result": {},
                "query_result": [],
                "final_answer": "",
                "retry_count": 0,
                "max_retries": 3,
                "error_type": None
            })

            with st.chat_message("assistant"):
                st.markdown(result["final_answer"])

                if result.get("generated_sql"):
                    with st.expander("🔍 查看生成的 SQL"):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.code(result["generated_sql"], language="sql")

                if result.get("query_result"):
                    df = pd.DataFrame(result["query_result"])
                    tab1, tab2 = st.tabs(["📊 表格", "📈 图表"])
                    with tab1:
                        st.dataframe(df, use_container_width=True)
                    with tab2:
                        fig = auto_generate_chart(df, question)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("当前数据不适合图表展示")

                msg = {
                    "role": "assistant",
                    "content": result["final_answer"],
                    "sql": result.get("generated_sql"),
                    "table": pd.DataFrame(result["query_result"]) if result.get("query_result") else None
                }
                st.session_state.messages.append(msg)

        except Exception as e:
            with st.chat_message("assistant"):
                st.error(f"处理失败：{str(e)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"处理失败：{str(e)}"
            })

def main():
    """主函数"""
    init_services()

    st.title("🤖 智能问数 Agent")
    st.caption("基于 Multi-Agent + RAG 的自然语言数据库查询系统")

    with st.sidebar:
        st.header("📊 数据库信息")
        try:
            tables = st.session_state.db_service.get_table_names()
            st.success(f"✅ 已连接 ({len(tables)} 张表)")
            for t in tables:
                with st.expander(f"📋 {t}"):
                    schema = st.session_state.db_service.get_table_schema(t)
                    st.code(schema, language="sql")
        except Exception as e:
            st.error(f"❌ 数据库连接失败: {e}")

        st.divider()
        st.header("💡 推荐问题")
        suggestions = [
            "本月订单总数是多少？",
            "各品类的销售额排行",
            "最近30天的客单价趋势",
            "好评率最高的前10个产品",
            "各城市的用户分布",
            "上个月的复购率是多少？"
        ]
        for q in suggestions:
            if st.button(q, key=f"sug_{hash(q)}", use_container_width=True):
                process_query(q)

        st.divider()
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    for msg in st.session_state.get("messages", []):
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])
            if "sql" in msg and msg["sql"]:
                with st.expander("🔍 SQL"):
                    st.code(msg["sql"], language="sql")
            if "table" in msg and msg["table"] is not None:
                st.dataframe(msg["table"], use_container_width=True)

    if prompt := st.chat_input("输入您的数据问题...", key="chat_input"):
        process_query(prompt)

if __name__ == "__main__":
    main()
