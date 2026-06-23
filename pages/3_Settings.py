import streamlit as st
from pathlib import Path
import sys

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils import database as db

st.set_page_config(page_title="设置", page_icon="⚙️", layout="centered")
st.title("⚙️ 设置")

settings = db.get_settings()
_AUDIO_CACHE_DIR = _project_root / "audio_cache"

# 检测是否在云端
def is_cloud():
    import os
    return os.environ.get("IS_STREAMLIT_CLOUD", "false") == "true" or os.path.exists("/home/appuser")

if is_cloud():
    st.info("⚠️ 当前运行在云端，设置可能无法持久化保存。建议将以下配置添加到 Streamlit Cloud Secrets 中：\n\n"
            "```toml\n"
            "github_token = \"你的仓库操作Token\"\n"
            "ai_github_token = \"你的AI专用Token\"\n"
            "github_repo = \"aitalker168/CTE_3_Collins_Vocabulary\"\n"
            "audio_raw_base = \"https://raw.githubusercontent.com/aitalker168/CTE_3_Collins_Vocabulary/main/audio_cache\"\n"
            "```\n\n"
            "如需修改，请在 Streamlit Cloud App 设置 → Secrets 中编辑。")

st.markdown("### 🔑 凭据配置")

github_token = st.text_input(
    "GitHub Token（用于仓库操作：笔记同步、上传音频）",
    value=settings.get("github_token", ""),
    type="password",
    help="需有 repo 和 contents: write 权限"
)

ai_github_token = st.text_input(
    "GitHub Token for AI（用于调用 GitHub Models 生成练习题）",
    value=settings.get("ai_github_token", ""),
    type="password",
    help="Classic Token，只需 read:user 权限即可"
)

st.markdown("### 📦 GitHub 仓库配置")
github_repo = st.text_input(
    "GitHub 仓库（格式：用户名/仓库名）",
    value=settings.get("github_repo", "")
)

st.markdown("### 🔊 音频源")
audio_raw_base = st.text_input(
    "GitHub raw 基础URL（用于云端播放）",
    value=settings.get("audio_raw_base", ""),
    help="例如：https://raw.githubusercontent.com/用户名/仓库名/main/audio_cache"
)
st.caption("更换GitHub账户后修改此URL即可，无需改动代码。")

st.markdown("### 📁 纯听模式音频文件夹")
current_audio_dir = settings.get("audio_scan_dir", str(_AUDIO_CACHE_DIR))
audio_scan_dir = st.text_input(
    "音频文件夹路径（纯听模式将扫描此目录下的所有 .mp3 文件）",
    value=current_audio_dir
)
st.caption("建议设置为 audio_cache 目录")

st.markdown("### 📖 在线词典URL模板")
dict_url = st.text_input(
    "词典查询URL（使用 {word} 作为单词占位符）",
    value=settings.get("dict_url", "https://dict.youdao.com/result?word={word}&lang=en")
)

st.markdown("### ⏱️ 纯听模式")
listen_interval = st.number_input(
    "默认间隔（秒）", min_value=1, max_value=10,
    value=int(settings.get("listen_interval", "3"))
)

st.markdown("### 🎵 缓存管理")
col1, col2 = st.columns(2)
with col1:
    if st.button("从有道下载当前级别所有音频"):
        st.warning("此功能将在后续版本中实现（可手动在本地运行后自动缓存）")
with col2:
    if st.button("清空音频缓存"):
        if st.checkbox("确认清空？"):
            import shutil
            audio_cache = _project_root / "audio_cache"
            if audio_cache.exists():
                shutil.rmtree(audio_cache)
                st.success("音频缓存已清空")

st.markdown("### 💾 导出笔记到新仓库")
st.markdown("将本地所有笔记推送到另一个GitHub仓库（用于迁移）。")
new_token = st.text_input("新仓库的Token", type="password", key="new_token")
new_repo = st.text_input("新仓库（用户名/仓库名）", key="new_repo")
if st.button("导出笔记"):
    import base64, requests
    if new_token and new_repo:
        conn = db.get_connection()
        notes = conn.execute("SELECT * FROM notes").fetchall()
        conn.close()
        if not notes:
            st.info("没有笔记需要导出。")
        else:
            success_count = 0
            fail_count = 0
            for note in notes:
                ok, msg = db.sync_note_to_github(note["word_id"], note["content"],
                                                  new_token, new_repo)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
            st.success(f"导出完成：成功 {success_count} 条，失败 {fail_count} 条。")
    else:
        st.error("请填写新仓库的Token和仓库名。")

if st.button("保存所有设置", type="primary"):
    db.set_setting("github_token", github_token)
    db.set_setting("ai_github_token", ai_github_token)
    db.set_setting("github_repo", github_repo)
    db.set_setting("audio_raw_base", audio_raw_base)
    db.set_setting("audio_scan_dir", audio_scan_dir)
    db.set_setting("dict_url", dict_url)
    db.set_setting("listen_interval", str(listen_interval))
    if is_cloud():
        st.warning("云端环境无法持久化保存，请将以上配置添加到 Streamlit Secrets 中（见页面顶部提示）。")
    else:
        st.success("设置已保存！")
