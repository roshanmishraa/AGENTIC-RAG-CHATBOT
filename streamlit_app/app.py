import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
print("ROOT PATH ADDED:", ROOT)

# ============================================================================
# CRITICAL FIX: Make ALL typing/pydantic imports globally available
# ============================================================================
import typing
from typing import (
    Annotated, Dict, Any, Optional, List, Union, Callable,
    get_type_hints, Tuple, Sequence, Literal, TypeVar,
    Awaitable, Coroutine, AsyncIterator, Iterator, Generator
)
from pydantic import BaseModel, Field
import builtins

# Make typing module itself available globally
builtins.typing = typing

# Explicitly set commonly used types
builtins.Annotated = Annotated
builtins.Dict = Dict
builtins.Any = Any
builtins.Optional = Optional
builtins.List = List
builtins.Union = Union
builtins.Callable = Callable
builtins.Tuple = Tuple
builtins.Sequence = Sequence
builtins.Literal = Literal
builtins.TypeVar = TypeVar
builtins.Awaitable = Awaitable
builtins.Coroutine = Coroutine
builtins.AsyncIterator = AsyncIterator
builtins.Iterator = Iterator
builtins.Generator = Generator
builtins.get_type_hints = get_type_hints

# Pydantic types
builtins.BaseModel = BaseModel
builtins.Field = Field
builtins.ArgsSchema = BaseModel

# Handle SkipValidation if it exists
try:
    from pydantic import SkipValidation
    builtins.SkipValidation = SkipValidation
except ImportError:
    builtins.SkipValidation = type('SkipValidation', (), {})
# ============================================================================

import streamlit as st
import uuid
import requests
import queue
import threading
import asyncio
from datetime import datetime

from langchain_core.messages import HumanMessage   # Required for LangGraph Direct Mode


# ----------------------------
# Configuration
# ----------------------------
USE_DIRECT_IMPORT = os.environ.get("USE_DIRECT_IMPORT", "true").lower() == "true"

try:
    BACKEND_URL = st.secrets.get("BACKEND_URL", os.environ.get("BACKEND_URL", "http://localhost:8000"))
except:
    BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

if USE_DIRECT_IMPORT:
    from app.langgraph_mcp_backend import (
        chatbot,
        retrieve_all_threads,
        submit_async_task,
        ingest_pdf,
        thread_document_metadata,
    )


st.set_page_config(page_title="Agentic RAG Chatbot", page_icon="🤖")


# ----------------------------
# Session State Initialization
# ----------------------------
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "threads" not in st.session_state:
    st.session_state["threads"] = retrieve_all_threads() if USE_DIRECT_IMPORT else []


# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("🧠 Agentic RAG Chatbot")

st.sidebar.markdown(f"**Current Thread:** `{st.session_state['thread_id']}`")

# Show ingested document metadata
meta = thread_document_metadata(st.session_state["thread_id"]) if USE_DIRECT_IMPORT else None
if meta:
    st.sidebar.info(
        f"""📄 **Document:** {meta.get('filename')}  
        🔹 Pages: {meta.get('documents')}  
        🔹 Chunks: {meta.get('chunks')}"""
    )
else:
    st.sidebar.info("No document indexed yet.")


# New Thread Button
if st.sidebar.button("➕ Start New Thread"):
    st.session_state["thread_id"] = str(uuid.uuid4())
    st.session_state["messages"] = []
    st.rerun()


# List threads
if USE_DIRECT_IMPORT and st.session_state["threads"]:
    st.sidebar.subheader("Past Threads")
    for tid in st.session_state["threads"][::-1]:
        if st.sidebar.button(tid):
            st.session_state["thread_id"] = tid
            st.session_state["messages"] = []
            st.rerun()


# ----------------------------
# PDF Upload
# ----------------------------
uploaded = st.sidebar.file_uploader("Upload PDF", type=["pdf"])

if uploaded:
    with st.sidebar.status("Indexing document..."):
        if USE_DIRECT_IMPORT:
            # ✅ Save the thread ID that has the document
            current_thread = st.session_state["thread_id"]
            ingest_pdf(uploaded.getvalue(), current_thread, uploaded.name)
            
            # ✅ Store this thread ID for queries
            st.session_state["doc_thread_id"] = current_thread
            
            # ✅ Print for debugging
            print(f"📄 Document indexed in thread: {current_thread}")
            
            st.sidebar.success("Document indexed successfully!")
        else:
            # HTTP BACKEND MODE
            url = f"{BACKEND_URL}/api/v1/upload"
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            data = {"thread_id": st.session_state["thread_id"]}
            r = requests.post(url, files=files, data=data, timeout=120)
            if r.status_code == 200:
                st.sidebar.success("Indexed!")
            else:
                st.sidebar.error(f"Failed: {r.text}")


# ----------------------------
# Chat History
# ----------------------------
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])


# ----------------------------
# Stream Handler (for HTTP backend)
# ----------------------------
def http_stream(base_url: str, payload: dict):
    from streamlit_app.utils.http_client import stream_chat
    for token in stream_chat(base_url, payload):
        yield token


user_input = st.chat_input("Ask anything or query the uploaded document…")

if user_input:
    # Record user message
    st.session_state["messages"].append({"role": "user", "text": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        container = st.empty()
        assistant_text = ""

        # ✅ Use the thread that has the document, if available
        if "doc_thread_id" in st.session_state:
            thread_id_local = st.session_state["doc_thread_id"]
            print(f"🔍 Using document thread: {thread_id_local}")
        else:
            thread_id_local = st.session_state["thread_id"]
            print(f"🔍 Using current thread: {thread_id_local}")

        # ------------------------
        # DIRECT IMPORT MODE
        # ------------------------
        if USE_DIRECT_IMPORT:
            q = queue.Queue()

            def producer(thread_id):
                # Ensure ALL typing context in thread
                import typing
                from typing import (
                    Annotated, Dict, Any, Optional, List, Union, Callable, 
                    get_type_hints, Tuple, Sequence, Literal, TypeVar,
                    Awaitable, Coroutine, AsyncIterator, Iterator, Generator
                )
                from pydantic import BaseModel, Field
                import builtins
                
                # Make typing module available
                builtins.typing = typing
                builtins.Annotated = Annotated
                builtins.Dict = Dict
                builtins.Any = Any
                builtins.Optional = Optional
                builtins.List = List
                builtins.Union = Union
                builtins.Callable = Callable
                builtins.Tuple = Tuple
                builtins.Sequence = Sequence
                builtins.Literal = Literal
                builtins.TypeVar = TypeVar
                builtins.Awaitable = Awaitable
                builtins.Coroutine = Coroutine
                builtins.AsyncIterator = AsyncIterator
                builtins.Iterator = Iterator
                builtins.Generator = Generator
                builtins.get_type_hints = get_type_hints
                builtins.BaseModel = BaseModel
                builtins.Field = Field
                builtins.ArgsSchema = BaseModel
                
                try:
                    from pydantic import SkipValidation
                    builtins.SkipValidation = SkipValidation
                except ImportError:
                    builtins.SkipValidation = type('SkipValidation', (), {})
                
                print(f"🔵 Producer started for thread: {thread_id}")
                
                async def run():
                    CONFIG = {
                        "configurable": {"thread_id": thread_id},
                        "metadata": {"thread_id": thread_id, "source": "streamlit-direct"},
                    }

                    print(f"🔵 Starting chatbot stream...")
                    
                    try:
                        async for chunk, meta in chatbot.astream(
                            {"messages": [HumanMessage(content=user_input)]},
                            config=CONFIG,
                            stream_mode="messages",
                        ):
                            print(f"🟢 Chunk received: {chunk}")
                            q.put(chunk)
                    except Exception as e:
                        print(f"🔴 ERROR in producer: {e}")
                        import traceback
                        traceback.print_exc()
                        q.put(("error", str(e)))
                    finally:
                        print(f"🔵 Producer finished")
                        q.put(None)

                asyncio.run(run())

            # Start thread AND pass thread_id safely
            threading.Thread(target=producer, args=(thread_id_local,), daemon=True).start()

            # Consume streamed chunks
            while True:
                chunk = q.get()
                if chunk is None:
                    break
                
                # Handle errors
                if isinstance(chunk, tuple) and chunk[0] == "error":
                    container.error(f"Error: {chunk[1]}")
                    break

                text = getattr(chunk, "content", None)
                assistant_text += text if isinstance(text, str) else str(chunk)

                container.markdown(assistant_text)

        # ------------------------
        # HTTP BACKEND MODE
        # ------------------------
        else:
            payload = {"thread_id": thread_id_local, "message": user_input}

            try:
                for token in http_stream(BACKEND_URL, payload):
                    assistant_text += token
                    container.markdown(assistant_text)
            except Exception as e:
                container.error(f"Error: {str(e)}")

        # Save assistant message
        st.session_state["messages"].append({"role": "assistant", "text": assistant_text})
        st.rerun()