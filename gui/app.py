"""
longtext2md Streamlit 界面 —— 文件上传、任务管理、结果预览。
"""
import streamlit as st
import asyncio, threading, os, subprocess, sys
from datetime import datetime
from src.task.task_store import create_task, get_task, list_tasks, delete_task
from src.task.task_manager import run_task
from src.kb.kb_manager import create_kb, list_kbs, delete_kb

# 课件文件扩展名
COURSEWARE_EXTS = {".pdf", ".md", ".docx", ".pptx", ".txt"}
# 代码文件扩展名
CODE_EXTS = {".py", ".java", ".js", ".ts", ".go", ".rs", ".kt", ".swift",
             ".xml", ".yaml", ".yml", ".properties", ".json", ".sql", ".c", ".cpp", ".h", ".hpp"}
ALL_EXTS = sorted(COURSEWARE_EXTS | CODE_EXTS)

# 文件夹选择器脚本
PICKER_SCRIPT = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
folder = filedialog.askdirectory(title="选择文件夹")
if folder:
    print(folder)
root.destroy()
"""

def pick_folder() -> str | None:
    """弹出系统文件夹选择对话框。"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", PICKER_SCRIPT],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None

# 页面配置
st.set_page_config(page_title="longtext2md 逐字稿转笔记", layout="wide")
st.title("longtext2md — 网课逐字稿转 Markdown 笔记")

# 状态初始化
if "show_detail" not in st.session_state:
    st.session_state.show_detail = None
if "picked_folder" not in st.session_state:
    st.session_state.picked_folder = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

# ---- 侧边栏：新建任务 ----
with st.sidebar:
    st.header("新建任务")
    task_name = st.text_input("任务名称（可选）", placeholder="自动提取")
    transcript_file = st.file_uploader("上传逐字稿（拖拽到此处）", type=["txt", "md"])
    transcript_text = st.text_area("或直接粘贴逐字稿", height=150)
    all_files = st.file_uploader(
        "上传参考资料（拖拽到此处）",
        type=ALL_EXTS,
        accept_multiple_files=True,
        key="ref_uploader",
        help="自动分类：.pdf/.docx/.pptx/.md/.txt 归为课件；其余归为代码",
    )
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        code_dir = st.text_input(
            "或选择文件夹",
            value=st.session_state.picked_folder or "",
            placeholder="选择文件夹或拖拽文件...",
            key="folder_input",
        )
    with col_f2:
        if st.button(chr(0x1F4C1), help="打开文件夹选择器", use_container_width=True):
            folder = pick_folder()
            if folder:
                st.session_state.picked_folder = folder
                st.rerun()

    # 知识库选择
    kbs = list_kbs()
    kb_names = ["（不选，实时构建）"] + [k["name"] for k in kbs if k.get("valid")]
    selected_kb = st.selectbox("知识库", kb_names, help="选择已有知识库可复用索引")
    selected_kb = None if selected_kb == "（不选，实时构建）" else selected_kb

    mindmap_enabled = st.checkbox("生成思维导图", value=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("创建并开始", use_container_width=True):
            text = transcript_text
            if transcript_file and not text:
                try:
                    text = transcript_file.getvalue().decode("utf-8")
                except (UnicodeDecodeError, AttributeError):
                    text = transcript_file.getvalue().decode("gbk")
            if text:
                tid = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                name = task_name or f"任务 {tid[-6:]}"
                upload_dir = f"output/{tid}/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                saved_code_dir = ""
                saved_cw_dir = ""
                if all_files:
                    saved_code_dir = os.path.join(upload_dir, "code")
                    saved_cw_dir = os.path.join(upload_dir, "courseware")
                    for f in all_files:
                        ext = os.path.splitext(f.name)[1].lower()
                        if ext in COURSEWARE_EXTS:
                            os.makedirs(saved_cw_dir, exist_ok=True)
                            with open(os.path.join(saved_cw_dir, f.name), "wb") as out:
                                out.write(f.getvalue())
                        else:
                            os.makedirs(saved_code_dir, exist_ok=True)
                            with open(os.path.join(saved_code_dir, f.name), "wb") as out:
                                out.write(f.getvalue())
                final_code_dir = saved_code_dir or code_dir or None
                final_cw_dir = saved_cw_dir or None
                create_task(tid, name, {
                    "transcript_text": text,
                    "code_dir": final_code_dir,
                    "courseware_dir": final_cw_dir,
                    "mindmap_enabled": mindmap_enabled,
                    "kb_name": selected_kb,
                })
                threading.Thread(target=lambda: asyncio.run(run_task(tid)), daemon=True).start()
                st.session_state.picked_folder = None
                st.session_state.auto_refresh = True
                st.rerun()
            else:
                st.error("请提供逐字稿文本")

    # ---- 知识库管理 ----
    st.divider()
    st.subheader("知识库管理")
    st.caption("知识库可跨任务复用，关闭应用后自动清理")

    kb_name = st.text_input("新建知识库名称", placeholder="例如: spring-boot", key="kb_name_input")
    kb_btn1, kb_btn2 = st.columns(2)
    with kb_btn1:
        if st.button("从上传文件创建", use_container_width=True, key="kb_from_upload"):
            kb_name_val = kb_name.strip()
            if not kb_name_val:
                st.error("请输入知识库名称")
            elif not all_files:
                st.error("请先在上方上传参考文件")
            else:
                with st.spinner("正在构建知识库..."):
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmpdir:
                        kb_code = os.path.join(tmpdir, "code")
                        kb_cw = os.path.join(tmpdir, "courseware")
                        has_code = False
                        has_cw = False
                        for f in all_files:
                            ext = os.path.splitext(f.name)[1].lower()
                            if ext in COURSEWARE_EXTS:
                                os.makedirs(kb_cw, exist_ok=True)
                                with open(os.path.join(kb_cw, f.name), "wb") as out:
                                    out.write(f.getvalue())
                                has_cw = True
                            else:
                                os.makedirs(kb_code, exist_ok=True)
                                with open(os.path.join(kb_code, f.name), "wb") as out:
                                    out.write(f.getvalue())
                                has_code = True
                        try:
                            meta = create_kb(
                                kb_name_val,
                                code_dir=kb_code if has_code else None,
                                courseware_dir=kb_cw if has_cw else None,
                            )
                            st.success(f"知识库 [{kb_name_val}] 创建完成 ({meta['slice_count']} 切片)")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
    with kb_btn2:
        if st.button("从文件夹创建", use_container_width=True, key="kb_from_folder"):
            folder = pick_folder()
            kb_name_val = kb_name.strip()
            if folder and kb_name_val:
                with st.spinner("正在构建知识库..."):
                    try:
                        meta = create_kb(kb_name_val, code_dir=folder, courseware_dir=folder)
                        st.success(f"知识库 [{kb_name_val}] 创建完成 ({meta['slice_count']} 切片)")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    # 已有知识库列表
    kbs = list_kbs()
    if kbs:
        st.caption(f"已有 {len(kbs)} 个知识库")
        for kb in kbs:
            col_a, col_b = st.columns([4, 1])
            col_a.write(f"{chr(0x1F4DA)} **{kb['name']}** ({kb.get('slice_count', 0)} 切片)")
            if col_b.button("删除", key=f"del_kb_{kb['name']}", use_container_width=True):
                delete_kb(kb["name"])
                st.rerun()

# ---- 主区域：任务列表 ----
st.subheader("任务列表")
tasks = list_tasks()
if not tasks:
    st.caption("暂无任务，从侧边栏创建一个吧！")
for task in tasks:
    cols = st.columns([3, 2, 1, 1, 1])
    icon = {"pending": chr(0x26AA), "running": chr(0x1F535), "completed": chr(0x1F7E2), "failed": chr(0x1F534)}.get(task["status"], chr(0x26AA))
    cols[0].write(f"{icon} **{task['name']}**")
    status_text = {"pending": "等待中", "running": "运行中", "completed": "已完成", "failed": "失败"}.get(task["status"], task["status"])
    cols[1].write(status_text)
    if cols[2].button("详情", key=f"d_{task['id']}"):
        st.session_state.show_detail = task["id"]; st.rerun()
    if task["status"] == "completed":
        out = f"output/{task['id']}/07_final.md"
        if os.path.exists(out):
            with open(out, "r", encoding="utf-8") as f:
                cols[3].download_button("下载", f.read(), file_name=f"{task['name']}.md")
    if cols[4].button("删除", key=f"del_{task['id']}"):
        delete_task(task["id"]); st.rerun()

# ---- 任务详情 ----
if st.session_state.show_detail:
    task = get_task(st.session_state.show_detail)
    if task:
        st.divider()
        icon_map = {"pending": chr(0x26AA), "running": chr(0x1F535), "completed": chr(0x1F7E2), "failed": chr(0x1F534)}
        icon = icon_map.get(task["status"], "")
        st.subheader(f"{icon} {task['name']} — 流水线详情")
        inputs = task.get("inputs", {})
        m1, m2, m3 = st.columns(3)
        m1.metric("逐字稿字数", f"{len(inputs.get('transcript_text', '')):,}")
        m2.metric("代码目录", inputs.get("code_dir") or "无")
        m3.metric("课件目录", inputs.get("courseware_dir") or "无")
        st.caption(f"创建时间: {task.get('created_at', '')}")
        if task.get("completed_at"):
            st.caption(f"完成时间: {task['completed_at']}")
        if task.get("error"):
            st.error(f"错误: {task['error']}")
        stage_names = [
            ("0.0", "噪音清洗"), ("0.2", "错别字纠正"),
            ("0.3", "全局摘要"), ("0.4", "边界检测"),
            ("1", "并行润色"), ("2", "结构化 + 代码注入"),
        ]
        for sid, sname in stage_names:
            st.write(f"{chr(0x26AA)} {sid} {sname}")
        if task["status"] == "completed":
            out = f"output/{task['id']}/07_final.md"
            if os.path.exists(out):
                with st.expander("查看笔记预览", expanded=False):
                    with open(out, "r", encoding="utf-8") as pf:
                        preview = pf.read()[:5000]
                    st.markdown(preview)
        if st.button("返回列表"):
            st.session_state.show_detail = None; st.rerun()

st.divider()
col_foot1, col_foot2 = st.columns(2)
col_foot1.caption("并行限制: 3  |  LLM: DeepSeek API")
col_foot2.caption(f"共 {len(tasks)} 个任务")