"""Streamlit 应用入口"""
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st


from agent.graph import build_graph
from agent.state import create_initial_state
from config import DB_URI
from services.conversation_service import build_assistant_message, get_recent_chat_history
from services.db_service import DatabaseService
from services.knowledge_base import get_knowledge_base


st.set_page_config(
    page_title="🤖 智能问数 Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stChatMessage { border-radius: 12px; }
    .stCodeBlock { border-radius: 8px; }
</style>
""",
    unsafe_allow_html=True,
)



def init_services():
    """初始化服务。"""
    if "db_service" not in st.session_state:
        st.session_state.db_service = DatabaseService(DB_URI)
    if "kb" not in st.session_state:
        st.session_state.kb = get_knowledge_base()
    if "agent_app" not in st.session_state:
        st.session_state.agent_app = build_graph()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None



def auto_generate_chart(df: pd.DataFrame, question: str):
    """根据数据自动选择合适的图表类型。"""
    if df.empty or len(df.columns) < 2:
        return None

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    text_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    if not numeric_cols:
        return None

    if any(keyword in question for keyword in ["趋势", "月", "日", "时间"]):
        if len(numeric_cols) >= 1 and len(df) > 1:
            return px.line(df, x=df.columns[0], y=numeric_cols[0], title="趋势分析")

    if any(keyword in question for keyword in ["排行", "最高", "最低", "前"]):
        if text_cols and numeric_cols:
            sorted_df = df.sort_values(numeric_cols[0], ascending=False).head(10)
            return px.bar(sorted_df, x=text_cols[0], y=numeric_cols[0], title="排行分析")

    if any(keyword in question for keyword in ["分布", "占比"]):
        if text_cols and numeric_cols:
            return px.pie(df, values=numeric_cols[0], names=text_cols[0], title="分布占比")

    if text_cols and numeric_cols:
        return px.bar(df.head(10), x=text_cols[0], y=numeric_cols[0], title="结果概览")

    return None



def queue_question(question: str):
    """将问题放入待处理队列。"""
    st.session_state.pending_question = question



def render_message(message: dict[str, Any], message_index: int):

    """渲染单条消息。"""
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message.get("sql"):
            with st.expander("🔍 SQL"):
                st.code(message["sql"], language="sql")

        table_data = message.get("table_data") or []
        if table_data:
            df = pd.DataFrame(table_data)
            tab1, tab2 = st.tabs(["📊 表格", "📈 图表"])
            with tab1:
                st.dataframe(df, use_container_width=True)
            with tab2:
                chart_question = message.get("resolved_question") or message.get("question") or message["content"]
                fig = auto_generate_chart(df, chart_question)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key=f"plotly_chart_{message_index}")
                else:
                    st.info("当前数据不适合图表展示")




def process_query(question: str):
    """处理用户查询 - 支持多轮对话。"""
    user_message = {"role": "user", "content": question}
    st.session_state.messages.append(user_message)

    agent_history = get_recent_chat_history(st.session_state.chat_history, max_turns=5)
    initial_state = create_initial_state(question, chat_history=agent_history)

    render_message(user_message, len(st.session_state.messages) - 1)


    with st.spinner("🤔 正在分析您的问题..."):
        try:
            result = st.session_state.agent_app.invoke(initial_state)
            assistant_message = build_assistant_message(question, result)
            st.session_state.messages.append(assistant_message)
            st.session_state.chat_history.extend([user_message, assistant_message])
            st.session_state.chat_history = get_recent_chat_history(st.session_state.chat_history, max_turns=10)
            render_message(assistant_message, len(st.session_state.messages) - 1)

        except Exception as e:
            error_message = {"role": "assistant", "content": f"处理失败：{str(e)}"}
            st.session_state.messages.append(error_message)
            st.session_state.chat_history.extend([user_message, error_message])
            st.session_state.chat_history = get_recent_chat_history(st.session_state.chat_history, max_turns=10)
            render_message(error_message, len(st.session_state.messages) - 1)




def main():
    """主函数。"""
    init_services()

    st.title("🤖 智能问数 Agent")
    st.caption("基于模块化智能体流水线 + RAG 的自然语言数据库查询系统")

    with st.sidebar:
        st.header("📊 数据库信息")
        try:
            tables = st.session_state.db_service.get_table_names()
            st.success(f"✅ 已连接 ({len(tables)} 张表)")
            for table_name in tables:
                with st.expander(f"📋 {table_name}"):
                    schema = st.session_state.db_service.get_table_schema(table_name)
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
            "上个月的复购率是多少？",
        ]
        for question in suggestions:
            if st.button(question, key=f"sug_{hash(question)}", use_container_width=True):
                queue_question(question)

        st.divider()
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.session_state.pending_question = None
            st.rerun()

    for idx, message in enumerate(st.session_state.get("messages", [])):
        render_message(message, idx)


    if prompt := st.chat_input("输入您的数据问题...", key="chat_input"):
        queue_question(prompt)

    pending_question = st.session_state.pop("pending_question", None)
    if pending_question:
        process_query(pending_question)


if __name__ == "__main__":
    main()
