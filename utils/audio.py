# utils/audio.py
import os
import requests
import base64
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_AUDIO_CACHE_DIR = _PROJECT_DIR / "audio_cache"

def get_audio_cache_path(level: str, word: str) -> Path:
    """
    返回本地缓存路径：audio_cache/{level}/{word}.mp3
    注意：level 已经是 "Level5" 这样的字符串，不会重复拼接。
    """
    return _AUDIO_CACHE_DIR / level / f"{word}.mp3"

def ensure_audio_cache_full_path(file_path: Path) -> bool:
    """如果文件不存在，尝试从有道下载并保存到该路径"""
    if file_path.exists():
        return True
    # 从路径中提取单词：假设文件名是 {word}.mp3
    word = file_path.stem
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return download_from_youdao(word, file_path)

def download_from_youdao(word: str, save_path: Path) -> bool:
    url = f"http://dict.youdao.com/dictvoice?audio={word}&type=1"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

def get_audio_url(word: str, level: str, settings: dict) -> str:
    """
    返回可播放的音频URL（用于卡片播放）。
    优先本地缓存，其次GitHub raw，最后有道在线。
    """
    local_path = get_audio_cache_path(level, word)
    if local_path.exists():
        return str(local_path)

    raw_base = settings.get("audio_raw_base", "")
    if raw_base:
        github_url = f"{raw_base.rstrip('/')}/{level}/{word}.mp3"
        return github_url

    return f"http://dict.youdao.com/dictvoice?audio={word}&type=1"

def upload_audio_to_github(word: str, level: str, github_token: str, repo: str, branch: str = "main") -> bool:
    local_path = get_audio_cache_path(level, word)
    if not local_path.exists():
        if not download_from_youdao(word, local_path):
            return False
    if not local_path.exists():
        return False

    file_path = f"audio_cache/{level}/{word}.mp3"
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}"}

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    data = {
        "message": f"Upload audio for {word}",
        "content": content_b64,
        "branch": branch
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data["sha"] = r.json()["sha"]
    r = requests.put(url, headers=headers, json=data)
    return r.status_code in (200, 201)