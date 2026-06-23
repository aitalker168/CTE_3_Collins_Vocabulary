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

# ------------------ 凭据配置 ------------------
st.markdown("### 🔑 凭据配置")

# 仓库操作 Token（用于笔记同步、上传音频）
github_token = st.text_input(
    "GitHub Token（用于仓库操作：笔记同步、上传音频）",
    value=settings.get("github_token", ""),
    type="password",
    help="Classic Token 或 Fine-grained Token，需有 repo 和 contents: write 权限"
)

# 新增：专用 AI Token（用于生成练习题）
ai_github_token = st.text_input(
    "GitHub Token for AI（用于调用 GitHub Models 生成练习题）",
    value=settings.get("ai_github_token", ""),
    type="password",
    help="Classic Token，只需 read:user 权限即可；或任何可调用 GitHub Models 的 Token"
)

st.markdown("### 📦 GitHub 仓库配置")
github_repo = st.text_input(
    "GitHub 仓库（格式：用户名/仓库名）",
    value=settings.get("github_repo", "")
)

# ------------------ 音频源 ------------------
st.markdown("### 🔊 音频源")
audio_raw_base = st.text_input(
    "GitHub raw 基础URL（用于云端播放）",
    value=settings.get("audio_raw_base", ""),
    help="例如：https://raw.githubusercontent.com/用户名/仓库名/main/audio_cache"
)
st.caption("更换GitHub账户后修改此URL即可，无需改动代码。")

# ------------------ 纯听模式音频文件夹 ------------------
st.markdown("### 📁 纯听模式音频文件夹")
current_audio_dir = settings.get("audio_scan_dir", str(_AUDIO_CACHE_DIR))
audio_scan_dir = st.text_input(
    "音频文件夹路径（纯听模式将扫描此目录下的所有 .mp3 文件）",
    value=current_audio_dir
)
st.caption("建议设置为 audio_cache 目录")

# ------------------ 在线词典 ------------------
st.markdown("### 📖 在线词典URL模板")
dict_url = st.text_input(
    "词典查询URL（使用 {word} 作为单词占位符）",
    value=settings.get("dict_url", "https://dict.youdao.com/result?word={word}&lang=en")
)

# ------------------ 纯听间隔 ------------------
st.markdown("### ⏱️ 纯听模式")
listen_interval = st.number_input(
    "默认间隔（秒）", min_value=1, max_value=10,
    value=int(settings.get("listen_interval", "3"))
)

# ------------------ 缓存管理 ------------------
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

# ------------------ 导出笔记到新仓库 ------------------
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

# ------------------ 保存按钮 ------------------
if st.button("保存所有设置", type="primary"):
    db.set_setting("github_token", github_token)
    db.set_setting("ai_github_token", ai_github_token)  # 新增
    db.set_setting("github_repo", github_repo)
    db.set_setting("audio_raw_base", audio_raw_base)
    db.set_setting("audio_scan_dir", audio_scan_dir)
    db.set_setting("dict_url", dict_url)
    db.set_setting("listen_interval", str(listen_interval))
    st.success("设置已保存！")
