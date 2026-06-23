import streamlit as st
from pathlib import Path
import sys
import os

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils import backup as bu

st.set_page_config(page_title="备份管理", page_icon="📦")

def is_cloud():
    """检测是否运行在 Streamlit Cloud"""
    return os.environ.get("IS_STREAMLIT_CLOUD", "false") == "true" or \
           os.path.exists("/home/appuser")

st.title("📦 备份管理")

if is_cloud():
    st.warning("备份与恢复功能仅在本地运行可用（云端文件系统只读）")
    st.stop()

tab1, tab2, tab3 = st.tabs(["全局备份", "增量备份", "恢复"])

# 全局备份
with tab1:
    st.markdown("### 全局完整备份")
    st.markdown("打包数据库、音频缓存、用户录音为一个 `.zip` 文件。")
    if st.button("创建全局备份", type="primary"):
        with st.spinner("正在创建备份..."):
            try:
                zip_path = bu.perform_full_backup()
                with open(zip_path, "rb") as f:
                    st.download_button("下载备份文件", data=f, file_name=zip_path.name, mime="application/zip")
                st.success(f"全局备份已创建：{zip_path.name}")
            except Exception as e:
                st.error(f"备份失败：{str(e)}")

# 增量备份
with tab2:
    st.markdown("### 增量备份")
    st.markdown("仅备份自上次全局备份以来的变更数据（笔记修改、新增录音等）。")
    if st.button("创建增量备份"):
        with st.spinner("正在创建增量备份..."):
            try:
                zip_path = bu.perform_incremental_backup()
                with open(zip_path, "rb") as f:
                    st.download_button("下载增量备份", data=f, file_name=zip_path.name, mime="application/zip")
                st.success(f"增量备份已创建：{zip_path.name}")
            except Exception as e:
                st.error(f"增量备份失败：{str(e)}")

# 恢复
with tab3:
    st.markdown("### 恢复数据")
    st.markdown("**注意：恢复会覆盖当前数据，请谨慎操作。**")
    uploaded_file = st.file_uploader("选择备份文件（.zip）", type=["zip"])
    if uploaded_file is not None:
        tmp_zip = _project_root / "backup" / "temp_restore.zip"
        tmp_zip.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_zip, "wb") as f:
            f.write(uploaded_file.getbuffer())
        restore_type = st.radio("恢复类型", options=["完整恢复（覆盖所有数据）", "增量恢复（仅应用变更）"])
        if st.button("执行恢复"):
            with st.spinner("正在恢复..."):
                try:
                    rtype = "full" if "完整" in restore_type else "incremental"
                    bu.restore_from_backup(tmp_zip, restore_type=rtype)
                    st.success("恢复完成！建议重启程序以确保数据完整。")
                except Exception as e:
                    st.error(f"恢复失败：{str(e)}")