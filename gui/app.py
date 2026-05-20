import streamlit as st
import asyncio, threading, os
from datetime import datetime
from src.task.task_store import create_task, get_task, list_tasks, update_task, delete_task
from src.task.task_manager import run_task

st.set_page_config(page_title="longtext2md", layout="wide")
st.title("longtext2md - Transcript to Markdown Notes")

if "show_detail" not in st.session_state:
    st.session_state.show_detail = None

with st.sidebar:
    st.header("+ New Task")
    task_name = st.text_input("Task name (optional)", placeholder="Auto-extracted")
    transcript_file = st.file_uploader("Transcript", type=["txt", "md"])
    transcript_text = st.text_area("Or paste transcript", height=150)
    code_dir = st.text_input("Code directory (optional)")
    mindmap_enabled = st.checkbox("Generate mindmap", value=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Create & Start", use_container_width=True):
            text = transcript_text
            if transcript_file and not text:
                text = transcript_file.getvalue().decode("utf-8")
            if text:
                tid = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                name = task_name or f"Task {tid[-6:]}"
                create_task(tid, name, {"transcript_text": text, "code_dir": code_dir, "mindmap_enabled": mindmap_enabled})
                threading.Thread(target=lambda: asyncio.run(run_task(tid)), daemon=True).start()
                st.rerun()
            else:
                st.error("Please provide a transcript")

st.subheader("Tasks")
tasks = list_tasks()
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
        st.write(f"Transcript | Code: {task['inputs'].get('code_dir', 'None')}")
        for sid, sname in [("0.0","Noise Cleaning"),("0.2","Error Correction"),("0.3","Summary"),("0.4","Boundary Detection"),("1","Parallel Polish"),("2","Structure & Code")]:
            st.write(f"{chr(0x26AA)} {sid} {sname}")
        if st.button("Back"):
            st.session_state.show_detail = None; st.rerun()

st.divider()
st.caption("Parallel limit: 3 | DeepSeek API")
