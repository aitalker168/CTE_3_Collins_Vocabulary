import os
import requests
import base64
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_AUDIO_CACHE_DIR = _PROJECT_DIR / "audio_cache"

def get_audio_cache_path(level: str, word: str) -> Path:
    """返回本地缓存路径：audio_cache/{level}/{word}.mp3"""
    return _AUDIO_CACHE_DIR / level / f"{word}.mp3"

def download_from_youdao(word: str, save_path: Path) -> bool:
    """从有道词典下载音频并保存到本地"""
    url = f"http://dict.youdao.com/dictvoice?audio={word}&type=1"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and len(r.content) > 1000:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

def get_audio_url(word: str, level: str, settings: dict) -> str:
    """返回可播放的音频URL（优先有道在线）"""
    return f"http://dict.youdao.com/dictvoice?audio={word}&type=1"

def upload_audio_to_github(word: str, level: str, github_token: str, repo: str, branch: str = "main") -> bool:
    """
    从有道词典获取音频数据，直接上传到 GitHub 仓库的 audio_cache/{level}/{word}.mp3。
    不依赖本地缓存，云端和本地均可使用。
    """
    # 从有道获取音频数据
    audio_url = f"http://dict.youdao.com/dictvoice?audio={word}&type=1"
    try:
        resp = requests.get(audio_url, timeout=10)
        if resp.status_code != 200 or len(resp.content) < 1000:
            return False
        audio_data = resp.content
    except Exception:
        return False

    # 准备上传到 GitHub
    file_path = f"audio_cache/{level}/{word}.mp3"
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}"}
    content_b64 = base64.b64encode(audio_data).decode()
    data = {
        "message": f"Upload audio for {word}",
        "content": content_b64,
        "branch": branch
    }

    # 检查远程文件是否存在（获取 SHA，用于更新）
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data["sha"] = r.json()["sha"]

    # 上传
    r = requests.put(url, headers=headers, json=data)
    return r.status_code in (200, 201)
