import streamlit as st
import asyncio, threading, os, subprocess, sys, tempfile
from datetime import datetime
from src.task.task_store import create_task, get_task, list_tasks, update_task, delete_task
from src.task.task_manager import run_task

COURSEWARE_EXTS = {".pdf", ".md", ".docx", ".pptx", ".txt"}
CODE_EXTS = {".py", ".java", ".js", ".ts", ".go", ".rs", ".kt", ".swift",
             ".xml", ".yaml", ".yml", ".properties", ".json", ".sql", ".c", ".cpp", ".h", ".hpp"}
ALL_EXTS = sorted(COURSEWARE_EXTS | CODE_EXTS)

PICKER_SCRIPT = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
folder = filedialog.askdirectory(title="Select folder")
if folder:
    print(folder)
root.destroy()
"""

def pick_folder() -> str | None:
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

st.set_page_config(page_title="longtext2md", layout="wide")
st.title("longtext2md - Transcript to Markdown Notes")

if "show_detail" not in st.session_state:
    st.session_state.show_detail = None
if "picked_folder" not in st.session_state:
    st.session_state.picked_folder = None

with st.sidebar:
    st.header("+ New Task")
    task_name = st.text_input("Task name (optional)", placeholder="Auto-extracted")
    transcript_file = st.file_uploader("Transcript (drag & drop)", type=["txt", "md"])
    transcript_text = st.text_area("Or paste transcript", height=150)
    all_files = st.file_uploader(
        "Reference files (drag & drop)",
        type=ALL_EXTS,
        accept_multiple_files=True,
        key="ref_uploader",
        help="Auto-classified: .pdf/.docx/.pptx/.md/.txt -> courseware; others -> code",
    )
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        code_dir = st.text_input(
            "Or pick a folder",
            value=st.session_state.picked_folder or "",
            placeholder="Select folder or drag files above...",
            key="folder_input",
        )
    with col_f2:
        if st.button(chr(0x1F4C1), help="Open folder picker", use_container_width=True):
            folder = pick_folder()
            if folder:
                st.session_state.picked_folder = folder
                st.rerun()
    mindmap_enabled = st.checkbox("Generate mindmap", value=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create & Start", use_container_width=True):
            text = transcript_text
            if transcript_file and not text:
                try:
                    text = transcript_file.getvalue().decode("utf-8")
                except (UnicodeDecodeError, AttributeError):
                    text = transcript_file.getvalue().decode("gbk")
            if text:
                tid = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                name = task_name or f"Task {tid[-6:]}"
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
                final_cw_dir = saved_cw_dir or code_dir or None
                create_task(tid, name, {
                    "transcript_text": text,
                    "code_dir": final_code_dir,
                    "courseware_dir": final_cw_dir,
                    "mindmap_enabled": mindmap_enabled,
                })
                threading.Thread(target=lambda: asyncio.run(run_task(tid)), daemon=True).start()
                st.session_state.picked_folder = None
                st.rerun()
            else:
                st.error("Please provide a transcript")

st.subheader("Tasks")
tasks = list_tasks()
if not tasks:
    st.caption("No tasks yet. Create one from the sidebar!")
for task in tasks:
    cols = st.columns([3, 2, 1, 1, 1])
    icon = {"pending": chr(0x26AA), "running": chr(0x1F535), "completed": chr(0x1F7E2), "failed": chr(0x1F534)}.get(task["status"], chr(0x26AA))
    cols[0].write(f"{icon} **{task['name']}**")
    cols[1].write(f"{task['status']}")
    if cols[2].button("Detail", key=f"d_{task['id']}"):
        st.session_state.show_detail = task["id"]; st.rerun()
    if task["status"] == "completed":
        out = f"output/{task['id']}/07_final.md"
        if os.path.exists(out):
            with open(out, "r", encoding="utf-8") as f:
                cols[3].download_button("Download", f.read(), file_name=f"{task['name']}.md")
    if cols[4].button("Delete", key=f"del_{task['id']}"):
        delete_task(task["id"]); st.rerun()

if st.session_state.show_detail:
    task = get_task(st.session_state.show_detail)
    if task:
        st.divider()
        st.subheader(f"{task['name']} - Pipeline Detail")
        inputs = task.get("inputs", {})
        st.write(f"Transcript | Code: {inputs.get('code_dir', 'None')} | Courseware: {inputs.get('courseware_dir', 'None')}")
        for sid, sname in [("0.0","Noise Cleaning"),("0.2","Error Correction"),("0.3","Summary"),("0.4","Boundary Detection"),("1","Parallel Polish"),("2","Structure & Code")]:
            st.write(f"{chr(0x26AA)} {sid} {sname}")
        if st.button("Back"):
            st.session_state.show_detail = None; st.rerun()

st.divider()
st.caption("Parallel limit: 3 | DeepSeek API")