# app.py
import streamlit as st
from pathlib import Path
import sys

_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.database import init_database, import_vocab_files, get_all_words

st.set_page_config(
    page_title="柯林斯词汇学习",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 首次运行：初始化数据库 + 导入词汇
if "db_initialized" not in st.session_state:
    init_database()
    # 检查是否已有数据
    words = get_all_words()
    if not words:
        inserted, skipped = import_vocab_files()
        st.success(f"词汇导入完成：新增 {inserted} 个单词，跳过 {skipped} 个已有单词")
    st.session_state.db_initialized = True

# 自定义全局样式
st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; }
    .main > div { padding: 1rem 2rem; }
</style>
""", unsafe_allow_html=True)

# 侧边栏导航
with st.sidebar:
    st.markdown("### 柯林斯词汇学习器")
    st.caption("版本 1.0 · 本地 + 云端模式")
    st.divider()
    st.markdown("请通过上方的页面菜单导航。")

# 主区域提示（当无页面被选中时显示）
st.markdown("## 👈 请从左侧页面菜单选择一个页面")
st.markdown("- **学习**：浏览词汇卡片、发音、笔记、录音、练习题")
st.markdown("- **备份管理**：全局/增量备份与恢复")
st.markdown("- **设置**：配置 API Key、音频源、导出笔记等")