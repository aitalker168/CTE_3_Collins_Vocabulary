import streamlit as st
import streamlit.components.v1 as components
import json
import time
import base64
import requests as req
from pathlib import Path
import sys
import os

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils import database as db
from utils import audio as au
from utils import ai_exercise as ai

st.set_page_config(page_title="学习", page_icon="📖", layout="wide")

def is_cloud():
    """检测是否运行在 Streamlit Cloud"""
    return os.environ.get("IS_STREAMLIT_CLOUD", "false") == "true" or \
           os.path.exists("/home/appuser")

if "db_initialized" not in st.session_state:
    db.init_database()
    st.session_state.db_initialized = True

settings = db.get_settings()
if "audio_raw_base" not in st.session_state:
    st.session_state.audio_raw_base = settings.get("audio_raw_base", "")
if "pure_listen_folder" not in st.session_state:
    st.session_state.pure_listen_folder = ""

_AUDIO_CACHE_DIR = _project_root / "audio_cache"

@st.cache_data(ttl=60)
def get_cached_words(level):
    return db.get_all_words(level=level, frequency=None)

st.sidebar.header("筛选")
level = st.sidebar.selectbox(
    "格林斯级别",
    ["全部", "Level1", "Level2", "Level3", "Level4", "Level5"],
    key="level_selector"
)
level_param = None if level == "全部" else level
words = get_cached_words(level_param)
st.sidebar.caption(f"当前词汇量：{len(words)} 个")

PAGE_SIZE = 20
total_words = len(words)
total_pages = max(1, (total_words + PAGE_SIZE - 1) // PAGE_SIZE)
if "page" not in st.session_state:
    st.session_state.page = 1

col_prev, col_page, col_next = st.sidebar.columns([1, 1, 1])
with col_prev:
    if st.button("⬅ 上一页", use_container_width=True):
        if st.session_state.page > 1:
            st.session_state.page -= 1
            st.rerun()
with col_page:
    st.markdown(f"<div style='text-align:center'>{st.session_state.page}/{total_pages}</div>", unsafe_allow_html=True)
with col_next:
    if st.button("下一页 ➡", use_container_width=True):
        if st.session_state.page < total_pages:
            st.session_state.page += 1
            st.rerun()

page = st.session_state.page
start_idx = (page - 1) * PAGE_SIZE
end_idx = min(start_idx + PAGE_SIZE, total_words)
page_words = words[start_idx:end_idx]

st.markdown("""
<style>
.vocab-card { background-color: #1a1f33; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem; border: 1px solid #2a2f44; }
.main-word { font-size: 1.3rem; font-weight: bold; color: #e2e8f0; }
.pos-tag { background-color: #2563eb; color: white; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem; }
.syn-word { color: #93c5fd; }
</style>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    display_level = level if level != "全部" else "全部级别"
    st.markdown(f"### 柯林斯 {display_level}（第 {page}/{total_pages} 页）")
with col2:
    if not is_cloud():
        if st.button("▶ 纯听模式", type="primary", use_container_width=True):
            st.session_state.pure_listen_dialog_open = True
            st.session_state.pure_listen_finished = False
            st.rerun()
    else:
        st.button("▶ 纯听模式(云端不可用)", disabled=True, use_container_width=True)
with col3:
    st.markdown(f"<span style='color:#94a3b8'>显示 {start_idx+1}-{end_idx} / 共 {total_words}</span>",
                unsafe_allow_html=True)

for word in page_words:
    word_id = word["word_id"]
    syns = db.get_synonyms(word_id)
    note = db.get_note(word_id)
    with st.container():
        st.markdown(f'<div class="vocab-card">', unsafe_allow_html=True)
        cols1 = st.columns([0.3, 1.5, 0.5, 0.7, 0.3, 0.3, 0.3, 0.3])
        with cols1[0]:
            st.markdown(f"<span style='color:#94a3b8'>{word.get('word_id','')}</span>", unsafe_allow_html=True)
        with cols1[1]:
            st.markdown(f"<span class='main-word'>{word['word']}</span>", unsafe_allow_html=True)
        with cols1[2]:
            pos = word.get("part_of_speech", "")
            if pos:
                st.markdown(f"<span class='pos-tag'>{pos}</span>", unsafe_allow_html=True)
        with cols1[3]:
            st.markdown(f"<span style='color:#94a3b8'>{word.get('phonetic','')}</span>", unsafe_allow_html=True)
        with cols1[4]:
            st.markdown(f"<span>{word.get('translation','')}</span>", unsafe_allow_html=True)
        with cols1[5]:
            if st.button("🔊", key=f"audio_{word_id}", help="发音"):
                audio_url = f"http://dict.youdao.com/dictvoice?audio={word['word']}&type=1"
                st.markdown(f'<audio src="{audio_url}" autoplay></audio>', unsafe_allow_html=True)
        with cols1[6]:
            if st.button("📝", key=f"note_{word_id}", help="笔记"):
                st.session_state[f"expand_note_{word_id}"] = not st.session_state.get(f"expand_note_{word_id}", False)
        with cols1[7]:
            if st.button("📥", key=f"dl_{word_id}", help="下载MP3"):
                audio_url = f"http://dict.youdao.com/dictvoice?audio={word['word']}&type=1"
                try:
                    resp = req.get(audio_url, timeout=10)
                    if resp.status_code == 200:
                        st.download_button(
                            label="点击下载",
                            data=resp.content,
                            file_name=f"{word['word']}.mp3",
                            mime="audio/mpeg"
                        )
                except Exception as e:
                    st.error(f"下载失败: {e}")
        if st.session_state.get(f"expand_note_{word_id}", False):
            st.markdown("---")
            note_content = note["content"] if note else ""
            st.markdown("**我的笔记**")
            new_content = st.text_area("编辑笔记", value=note_content, height=100, key=f"text_{word_id}")
            col_save, col_rec = st.columns([1, 1])
            with col_save:
                if st.button("保存笔记", key=f"save_{word_id}"):
                    db.save_note(word_id, new_content)
                    gh_token = settings.get("github_token", "")
                    gh_repo = settings.get("github_repo", "")
                    if gh_token and gh_repo:
                        success, msg = db.sync_note_to_github(word_id, new_content, gh_token, gh_repo)
                        if success:
                            st.success("笔记已保存并同步到GitHub")
                        else:
                            st.warning(f"笔记已本地保存，GitHub同步失败：{msg}")
                    else:
                        st.success("笔记已保存（本地）。如需同步到GitHub，请在Secrets中配置github_token和github_repo。")
            with col_rec:
                if st.button("🎙️ 录音", key=f"rec_{word_id}"):
                    st.warning("录音功能仅在本地运行可用（云端不支持）")
            if note and note.get("recording_path"):
                rec_path = Path(note["recording_path"])
                if rec_path.exists():
                    st.audio(str(rec_path), format="audio/mp3")
        if syns:
            st.markdown("**同义词**")
            for syn in syns:
                c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 0.5, 0.5])
                with c1: st.markdown(f"<span class='syn-word'>{syn['synonym']}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span style='color:#94a3b8'>{syn.get('phonetic','')}</span>", unsafe_allow_html=True)
                with c3: st.markdown(f"<span>{syn.get('translation','')}</span>", unsafe_allow_html=True)
                with c4:
                    if st.button("🔊", key=f"syn_audio_{syn['syn_id']}"):
                        audio_url = f"http://dict.youdao.com/dictvoice?audio={syn['synonym']}&type=1"
                        st.markdown(f'<audio src="{audio_url}" autoplay></audio>', unsafe_allow_html=True)
                with c5:
                    if st.button("🔗", key=f"syn_link_{syn['syn_id']}", help="查询在线词典"):
                        dict_url = settings.get("dict_url", "https://dict.youdao.com/result?word={word}&lang=en")
                        url = dict_url.format(word=syn["synonym"])
                        st.markdown(f'<a href="{url}" target="_blank">打开词典</a>', unsafe_allow_html=True)
        col_ex = st.columns([1])
        with col_ex[0]:
            if st.button(f"🧠 练习 - {word['word']}", key=f"ex_{word_id}"):
                st.session_state[f"exercise_{word_id}"] = True
        if st.session_state.get(f"exercise_{word_id}", False):
            st.markdown("---")
            ai_key = settings.get("github_token", "")
            if not ai_key:
                st.warning("请先在Secrets中配置 GitHub Personal Access Token（将同时用于AI调用和仓库同步）")
            else:
                with st.spinner("生成练习题..."):
                    syn_words = [s["synonym"] for s in syns] if syns else []
                    questions = ai.generate_exercises(word["word"], word.get("translation", ""), syn_words, ai_key)
                if questions:
                    for q in questions:
                        st.markdown(f"**{q.get('question','')}**")
                        if q.get("type") == "choice":
                            for opt in q.get("options", []):
                                st.markdown(f"- {opt}")
                        st.info(f"答案：{q.get('answer','')}")
                        st.divider()
                    conn = db.get_connection()
                    conn.execute("INSERT INTO exercises (word_id, question_json) VALUES (?, ?)",
                                 (word_id, json.dumps(questions)))
                    conn.commit()
                    conn.close()
                    gh_token = settings.get("github_token", "")
                    gh_repo = settings.get("github_repo", "")
                    if gh_token and gh_repo:
                        with st.spinner("同步练习题到GitHub..."):
                            ai.save_exercises_to_github(word_id, questions, gh_token, gh_repo)
                    st.success("练习题已生成并保存")
            st.session_state[f"exercise_{word_id}"] = False
        st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.get("pure_listen_dialog_open", False):
    @st.dialog("🎧 纯听控制面板")
    def pure_listen_dialog():
        if is_cloud():
            st.warning("纯听模式仅支持本地运行（云端无本地音频文件夹）")
            if st.button("✖ 关闭", use_container_width=True):
                st.session_state.pure_listen_dialog_open = False
                st.rerun()
            return
        st.markdown("选择本地音频文件夹并设定播放参数。")
        audio_scan_dir = settings.get("audio_scan_dir", str(_AUDIO_CACHE_DIR))
        scan_path = st.text_input("音频文件夹路径", value=audio_scan_dir, key="pure_scan_path")
        if st.button("🔍 扫描此文件夹", use_container_width=True):
            p = Path(scan_path)
            if p.exists() and p.is_dir():
                found_files = sorted(p.glob("*.mp3"))
                st.session_state.pure_listen_files = found_files
                check_dict = {i: True for i in range(len(found_files))}
                st.session_state.pure_listen_check = check_dict
                st.session_state.pure_listen_index = 0
                st.session_state.pure_listen_playing = False
                st.session_state.pure_listen_finished = False
                st.rerun()
            else:
                st.error("文件夹路径不存在或无效")
        files = st.session_state.get("pure_listen_files", [])
        st.info(f"已扫描到 **{len(files)}** 个本地音频文件")
        if files:
            with st.expander("选择要播放的音频（勾选）"):
                check_dict = st.session_state.get("pure_listen_check", {})
                for i, f in enumerate(files):
                    if i not in check_dict:
                        check_dict[i] = True
                    checked = st.checkbox(f.name, value=check_dict[i], key=f"pure_check_{i}")
                    check_dict[i] = checked
                st.session_state.pure_listen_check = check_dict
        if not st.session_state.get("pure_listen_playing", False) and not st.session_state.get("pure_listen_finished", False):
            col_interval, col_times = st.columns(2)
            with col_interval:
                interval = st.number_input("播放间隔（秒）", min_value=1, max_value=30, value=3)
            with col_times:
                play_times = st.number_input("播放次数（0=无限）", min_value=0, max_value=100, value=1)
        else:
            interval = st.session_state.get("pure_listen_interval", 3)
            play_times = st.session_state.get("pure_listen_play_times", 1)
        if st.session_state.get("pure_listen_finished", False):
            st.success("🎉 播放完毕！")
            col_replay, col_close = st.columns(2)
            with col_replay:
                if st.button("🔄 重新播放", type="primary", use_container_width=True):
                    st.session_state.pure_listen_finished = False
                    st.session_state.pure_listen_playing = True
                    st.session_state.pure_listen_index = 0
                    st.session_state.pure_listen_counter = 0
                    st.session_state.pure_listen_remain_times = st.session_state.get("pure_listen_play_times", 1)
                    if st.session_state.pure_listen_remain_times == 0:
                        st.session_state.pure_listen_remain_times = 9999
                    st.rerun()
            with col_close:
                if st.button("✖ 关闭面板", use_container_width=True):
                    st.session_state.pure_listen_dialog_open = False
                    st.session_state.pure_listen_finished = False
                    st.rerun()
        if not st.session_state.get("pure_listen_playing", False) and not st.session_state.get("pure_listen_finished", False):
            col_start, col_stop = st.columns(2)
            with col_start:
                if st.button("▶ 开始播放", type="primary", use_container_width=True):
                    if not files:
                        st.warning("请先扫描音频文件")
                    else:
                        check_dict = st.session_state.get("pure_listen_check", {})
                        selected_indices = [i for i in range(len(files)) if check_dict.get(i, True)]
                        if not selected_indices:
                            selected_indices = list(range(len(files)))
                        selected_files = [files[i] for i in selected_indices]
                        st.session_state.pure_listen_playlist = selected_files
                        st.session_state.pure_listen_interval = interval
                        st.session_state.pure_listen_play_times = play_times
                        st.session_state.pure_listen_remain_times = play_times if play_times > 0 else 9999
                        st.session_state.pure_listen_playing = True
                        st.session_state.pure_listen_index = 0
                        st.session_state.pure_listen_counter = 0
                        st.session_state.pure_listen_finished = False
                        st.rerun()
            with col_stop:
                if st.button("✖ 关闭面板", use_container_width=True):
                    st.session_state.pure_listen_dialog_open = False
                    st.rerun()
        if st.session_state.get("pure_listen_playing", False):
            if st.button("⏹ 停止播放", use_container_width=True):
                st.session_state.pure_listen_playing = False
                st.session_state.pure_listen_finished = False
                st.rerun()
        if st.session_state.get("pure_listen_playing", False):
            playlist = st.session_state.get("pure_listen_playlist", [])
            idx = st.session_state.get("pure_listen_index", 0)
            remain = st.session_state.get("pure_listen_remain_times", 0)
            interval_val = st.session_state.get("pure_listen_interval", 3)
            counter = st.session_state.get("pure_listen_counter", 0)
            if idx < len(playlist):
                audio_file = playlist[idx]
                with open(audio_file, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                player_html = f"""
                <div style="display:flex;align-items:center;gap:10px;">
                    <audio autoplay controls style="height:30px;">
                        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
                    </audio>
                    <span style="color:#94a3b8;font-size:0.85rem;">
                        正在播放：{audio_file.name}（{idx+1}/{len(playlist)}）| 剩余轮次：{remain}
                    </span>
                </div>
                """
                components.html(player_html, height=60)
                time.sleep(interval_val)
                st.session_state.pure_listen_index = idx + 1
                st.session_state.pure_listen_counter = counter + 1
                if st.session_state.pure_listen_index >= len(playlist):
                    st.session_state.pure_listen_remain_times -= 1
                    if st.session_state.pure_listen_remain_times <= 0:
                        st.session_state.pure_listen_playing = False
                        st.session_state.pure_listen_finished = True
                    else:
                        st.session_state.pure_listen_index = 0
                st.rerun()
            else:
                st.session_state.pure_listen_playing = False
                st.session_state.pure_listen_finished = True
                st.rerun()
    pure_listen_dialog()
