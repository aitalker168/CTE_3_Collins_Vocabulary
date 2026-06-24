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

# ---------- 样式 ----------
st.markdown("""
<style>
.vocab-card { background-color: #1a1f33; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem; border: 1px solid #2a2f44; }
.main-word { font-size: 1.5rem; font-weight: bold; color: #ffffff; text-shadow: 0 0 8px rgba(255,255,255,0.3); }
.pos-tag { background-color: #2563eb; color: white; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem; }
.syn-word { color: #93c5fd; }
</style>
""", unsafe_allow_html=True)

# 页头
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

# ---------- 词汇卡片列表 ----------
for word in page_words:
    word_id = word["word_id"]
    # 从数据库获取同义词（如果数据库有则优先使用）
    db_syns = db.get_synonyms(word_id)
    # 判断是否已有AI生成的同义词（存在session_state中）
    session_syn_key = f"ai_synonyms_{word_id}"
    if st.session_state.get(session_syn_key) is not None:
        syns = st.session_state[session_syn_key][:2]  # 最多2个
    elif db_syns:
        syns = db_syns[:2]  # 使用数据库中的
    else:
        syns = []  # 空，等待生成

    note = db.get_note(word_id)
    with st.container():
        st.markdown(f'<div class="vocab-card">', unsafe_allow_html=True)
        cols1 = st.columns([0.3, 1.8, 0.5, 0.7, 0.3, 0.3, 0.3, 0.3, 0.3])
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
            if st.button("📥", key=f"dl_{word_id}", help="下载MP3到本地"):
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
        with cols1[8]:
            gh_token = settings.get("github_token", "")
            gh_repo = settings.get("github_repo", "")
            if gh_token and gh_repo:
                if st.button("☁️", key=f"upload_{word_id}", help="上传音频到GitHub"):
                    success = au.upload_audio_to_github(word['word'], word['level'], gh_token, gh_repo)
                    if success:
                        st.success(f"已上传 {word['word']}.mp3 到 GitHub")
                    else:
                        st.error("上传失败，请检查网络或Token权限")
            else:
                st.button("☁️", disabled=True, help="请先在设置中配置GitHub Token和仓库")

        # ---------- 笔记区域 ----------
        if st.session_state.get(f"expand_note_{word_id}", False):
            st.markdown("---")
            note_content = note["content"] if note else ""
            st.markdown("**我的笔记**")
            new_content = st.text_area("编辑笔记", value=note_content, height=100, key=f"text_{word_id}")
            col_save, col_del, col_rec = st.columns([1, 1, 1])
            with col_save:
                if st.button("保存笔记", key=f"save_{word_id}"):
                    db.save_note(word_id, new_content)
                    gh_token = settings.get("github_token", "")
                    gh_repo = settings.get("github_repo", "")
                    if gh_token and gh_repo:
                        success, msg = db.sync_note_to_github(word_id, new_content, gh_token, gh_repo, word=word['word'])
                        if success:
                            st.success("笔记已保存并同步到GitHub")
                        else:
                            st.warning(f"笔记已本地保存，GitHub同步失败：{msg}")
                    else:
                        st.success("笔记已保存（本地）。如需同步到GitHub，请在Secrets中配置github_token和github_repo。")
            with col_del:
                if st.button("🗑️ 删除笔记", key=f"del_{word_id}"):
                    db.delete_note(word_id)
                    gh_token = settings.get("github_token", "")
                    gh_repo = settings.get("github_repo", "")
                    if gh_token and gh_repo:
                        success, msg = db.delete_note_from_github(word_id, gh_token, gh_repo, word=word['word'])
                        if success:
                            st.success("笔记已删除并同步到GitHub")
                        else:
                            st.warning(f"本地笔记已删除，但GitHub同步失败：{msg}")
                    else:
                        st.success("笔记已删除（本地）")
                    st.session_state[f"expand_note_{word_id}"] = False
                    st.rerun()
            with col_rec:
                if st.button("🎙️ 录音", key=f"rec_{word_id}"):
                    st.warning("录音功能仅在本地运行可用（云端不支持）")
            if note and note.get("recording_path"):
                rec_path = Path(note["recording_path"])
                if rec_path.exists():
                    st.audio(str(rec_path), format="audio/mp3")

        # ---------- 同义词区域（AI生成 + 数据库混合） ----------
        st.markdown("**同义词**")
        if syns:
            for idx, syn in enumerate(syns):
                # 兼容数据库格式和AI生成格式
                synonym_text = syn.get("synonym", syn.get("synonym", ""))
                phonetic_text = syn.get("phonetic", syn.get("phonetic", ""))
                pos_text = syn.get("part_of_speech", syn.get("part_of_speech", ""))
                translation_text = syn.get("translation", syn.get("translation", ""))
                syn_id = f"syn_{word_id}_{idx}"
                c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.5, 1.5, 0.5, 0.5, 0.5])
                with c1: st.markdown(f"<span class='syn-word'>{synonym_text}</span>", unsafe_allow_html=True)
                with c2: st.markdown(f"<span style='color:#94a3b8'>{phonetic_text}</span>", unsafe_allow_html=True)
                with c3: st.markdown(f"<span>{pos_text} {translation_text}</span>", unsafe_allow_html=True)
                with c4:
                    if st.button("🔊", key=f"syn_audio_{syn_id}", help="发音"):
                        audio_url = f"http://dict.youdao.com/dictvoice?audio={synonym_text}&type=1"
                        st.markdown(f'<audio src="{audio_url}" autoplay></audio>', unsafe_allow_html=True)
                with c5:
                    gh_token = settings.get("github_token", "")
                    gh_repo = settings.get("github_repo", "")
                    if gh_token and gh_repo:
                        if st.button("☁️", key=f"syn_up_{syn_id}", help="上传同义词音频到GitHub"):
                            success = au.upload_audio_to_github(synonym_text, word['level'], gh_token, gh_repo)
                            if success:
                                st.success(f"已上传 {synonym_text}.mp3")
                            else:
                                st.error("上传失败")
                    else:
                        st.button("☁️", disabled=True)
                with c6:
                    dict_url = settings.get("dict_url", "https://dict.youdao.com/result?word={word}&lang=en")
                    url = dict_url.format(word=synonym_text)
                    st.markdown(f'<a href="{url}" target="_blank">🔗</a>', unsafe_allow_html=True)
        else:
            # 没有同义词时，提供生成按钮
            st.markdown("*暂无同义词*")
            if st.button("🤖 生成同义词", key=f"gen_syn_{word_id}"):
                ai_key = settings.get("ai_github_token", "")
                if ai_key:
                    with st.spinner("正在生成同义词..."):
                        generated = ai.generate_synonyms(word['word'], word.get('translation',''), ai_key)
                        if generated:
                            st.session_state[session_syn_key] = generated
                            st.rerun()
                        else:
                            st.info("未找到合适的同义词。")
                else:
                    st.warning("请先在设置页面配置AI Token。")

        # ---------- 练习（逐题显示，5题，难度递增） ----------
        col_ex = st.columns([1])
        with col_ex[0]:
            if st.session_state.get(f"exercise_{word_id}_show", False):
                if st.button(f"✖ 关闭练习", key=f"ex_close_{word_id}"):
                    st.session_state[f"exercise_{word_id}_show"] = False
                    st.session_state[f"exercise_{word_id}_done"] = False
                    if f"exercise_{word_id}_questions" in st.session_state:
                        del st.session_state[f"exercise_{word_id}_questions"]
                        del st.session_state[f"exercise_{word_id}_q_index"]
                    st.rerun()
            else:
                if st.button(f"🧠 练习 - {word['word']}", key=f"ex_{word_id}"):
                    st.session_state[f"exercise_{word_id}_show"] = True
                    st.session_state[f"exercise_{word_id}_done"] = False
                    st.session_state[f"exercise_{word_id}_q_index"] = 0
                    st.rerun()

        if st.session_state.get(f"exercise_{word_id}_show", False):
            st.markdown("---")
            if st.session_state.get(f"exercise_{word_id}_done", False) and \
               st.session_state.get(f"exercise_{word_id}_questions") is not None:
                questions = st.session_state[f"exercise_{word_id}_questions"]
                q_index = st.session_state.get(f"exercise_{word_id}_q_index", 0)
                total_q = len(questions)
                if q_index < total_q:
                    q = questions[q_index]
                    chinese = q.get("chinese_translation", "")
                    st.markdown(f"**第 {q_index+1}/{total_q} 题：{q.get('question','')}**")
                    if chinese:
                        st.markdown(f"*中文翻译：{chinese}*")
                    if q.get("type") == "choice":
                        for opt in q.get("options", []):
                            st.markdown(f"- {opt}")
                    st.info(f"答案：{q.get('answer','')}")
                    col_next_btn, _ = st.columns([1, 4])
                    with col_next_btn:
                        if q_index < total_q - 1:
                            if st.button("➡️ 下一题", key=f"ex_next_{word_id}_{q_index}"):
                                st.session_state[f"exercise_{word_id}_q_index"] = q_index + 1
                                st.rerun()
                        else:
                            st.success("🎉 已全部完成！")
                else:
                    st.success("🎉 已完成全部5道题！")
                    if st.button("🔄 重新生成", key=f"ex_redo_{word_id}"):
                        st.session_state[f"exercise_{word_id}_done"] = False
                        st.rerun()
            else:
                ai_key = settings.get("ai_github_token", "")
                if not ai_key:
                    st.warning("请先在设置页面配置 GitHub Token for AI（用于调用 GitHub Models 生成练习题）")
                else:
                    with st.spinner("生成练习题..."):
                        # 传入已有的同义词列表（用于prompt）
                        existing_syns = [s.get("synonym", "") for s in syns] if syns else []
                        questions = ai.generate_exercises(word["word"], word.get("translation", ""), existing_syns, ai_key)
                    if questions:
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
                        st.session_state[f"exercise_{word_id}_questions"] = questions
                        st.session_state[f"exercise_{word_id}_done"] = True
                        st.session_state[f"exercise_{word_id}_q_index"] = 0
                        st.success("练习题已生成并保存")
                        st.rerun()
                    else:
                        st.session_state[f"exercise_{word_id}_show"] = False
                        st.error("生成练习题失败，请检查AI Token或网络")
        st.markdown('</div>', unsafe_allow_html=True)

# ---------- 纯听模式对话框（保持不变） ----------
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
