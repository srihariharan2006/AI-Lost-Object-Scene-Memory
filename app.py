"""
app.py
------
AI Lost-Object & Scene Memory  —  Streamlit front-end.

Pages
-----
1. 🏠 Dashboard     — summary stats and top-detected objects.
2. 📸 Add Scene     — upload image, detect objects, save to DB.
3. 🔍 Search        — find which room an object was last seen in.
4. 📋 History       — browse / delete saved scenes.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import os
import json
from io import BytesIO
from typing import List, Dict, Any, Optional

import streamlit as st
from PIL import Image
import pandas as pd

# Local modules
import database as db
import detector as det

# ---------------------------------------------------------------------------
# Page configuration (must be the very first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Lost-Object & Scene Memory",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — modern dark-accent palette
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* ══════════════════════════════════════════════
       CYBERPUNK NEON THEME — AI Scene Memory
    ══════════════════════════════════════════════ */

    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Rajdhani', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        letter-spacing: 0.02em;
    }

    /* ── Main App Background (Clean, layered, no pseudo overlays) ── */
    .stApp {
        background-color: #070514;
        background-image:
            radial-gradient(ellipse at 15% 25%, rgba(120, 0, 255, 0.18) 0%, transparent 55%),
            radial-gradient(ellipse at 85% 15%, rgba(0, 255, 255, 0.14) 0%, transparent 45%),
            radial-gradient(ellipse at 65% 85%, rgba(255, 0, 180, 0.12) 0%, transparent 50%),
            linear-gradient(rgba(140, 0, 255, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(140, 0, 255, 0.08) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px;
        color: #e0d6ff;
    }

    /* ── Ensure main container is visible and raised ── */
    .main, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        visibility: visible !important;
        opacity: 1 !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #07050f 0%, #0d0820 60%, #100a25 100%);
        border-right: 1px solid rgba(180,0,255,0.4);
        box-shadow: 4px 0 30px rgba(140,0,255,0.15);
    }
    [data-testid="stSidebar"] .stRadio label {
        color: #c9b8ff !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        transition: color 0.2s, text-shadow 0.2s;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        color: #ff00ff !important;
        text-shadow: 0 0 8px #ff00ff;
    }

    /* ── Metric cards ── */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #0d0820, #130d2e);
        border: 1px solid rgba(180,0,255,0.5);
        border-radius: 12px;
        padding: 1.2rem !important;
        box-shadow: 0 0 20px rgba(140,0,255,0.2),
                    inset 0 0 20px rgba(100,0,200,0.05);
        position: relative;
        overflow: hidden;
    }
    [data-testid="metric-container"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, #bf00ff, #00ffff, transparent);
    }
    [data-testid="metric-container"] label {
        color: #9d7dff !important;
        font-size: 0.78rem !important;
        font-family: 'Orbitron', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #00ffff !important;
        font-size: 2.2rem !important;
        font-weight: 700;
        font-family: 'Orbitron', sans-serif !important;
        text-shadow: 0 0 15px rgba(0,255,255,0.7), 0 0 30px rgba(0,255,255,0.3);
    }

    /* ── Primary buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #4a00a0, #7b00ff);
        color: #e0d6ff !important;
        border: 1px solid rgba(200,0,255,0.6) !important;
        border-radius: 6px;
        padding: 0.55rem 1.6rem;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 600;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        transition: all 0.25s ease;
        box-shadow: 0 0 15px rgba(140,0,255,0.4),
                    inset 0 0 10px rgba(200,0,255,0.1);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #7b00ff, #ff00ff);
        box-shadow: 0 0 30px rgba(255,0,255,0.5),
                    0 0 60px rgba(200,0,255,0.25);
        transform: translateY(-2px);
        color: #ffffff !important;
    }

    /* ── Delete/danger button ── */
    .delete-btn > button {
        background: linear-gradient(135deg, #400020, #8b0040) !important;
        border-color: rgba(255,0,100,0.6) !important;
        box-shadow: 0 0 15px rgba(255,0,100,0.3) !important;
    }
    .delete-btn > button:hover {
        background: linear-gradient(135deg, #8b0040, #ff0066) !important;
        box-shadow: 0 0 30px rgba(255,0,100,0.5) !important;
    }

    /* ── Scene / result cards ── */
    .scene-card {
        background: linear-gradient(135deg, #0a0618, #0f0824);
        border: 1px solid rgba(140,0,255,0.35);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.9rem;
        box-shadow: 0 0 15px rgba(100,0,200,0.12),
                    inset 0 0 15px rgba(80,0,180,0.04);
        transition: box-shadow 0.25s ease, border-color 0.25s ease;
        position: relative;
        overflow: hidden;
    }
    .scene-card::after {
        content: '';
        position: absolute;
        top: 0; left: -100%;
        width: 60%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,255,255,0.4), transparent);
        transition: left 0.4s ease;
    }
    .scene-card:hover {
        border-color: rgba(200,0,255,0.6);
        box-shadow: 0 0 30px rgba(160,0,255,0.2),
                    0 0 60px rgba(0,255,255,0.06);
    }
    .scene-card:hover::after {
        left: 150%;
    }

    /* ── Section titles ── */
    .section-title {
        font-family: 'Orbitron', sans-serif !important;
        color: #bf00ff;
        font-size: 1.4rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
        text-shadow: 0 0 15px rgba(200,0,255,0.6), 0 0 30px rgba(180,0,255,0.3);
        border-bottom: 1px solid rgba(180,0,255,0.3);
        padding-bottom: 0.4rem;
    }

    /* ── Object tags ── */
    .obj-tag {
        display: inline-block;
        background: rgba(100,0,200,0.2);
        color: #00ffff;
        border: 1px solid rgba(0,255,255,0.4);
        border-radius: 4px;
        padding: 2px 10px;
        font-size: 0.76rem;
        margin: 2px 3px;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-shadow: 0 0 6px rgba(0,255,255,0.5);
    }

    /* ── Hero banner ── */
    .hero-banner {
        background: linear-gradient(135deg, #07040f 0%, #110830 50%, #0a0520 100%);
        border: 1px solid rgba(160,0,255,0.5);
        border-radius: 16px;
        padding: 2.2rem 2.5rem;
        margin-bottom: 1.8rem;
        text-align: center;
        position: relative;
        overflow: hidden;
        box-shadow: 0 0 40px rgba(120,0,255,0.15),
                    inset 0 0 40px rgba(80,0,200,0.05);
    }
    .hero-banner::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, #bf00ff, #00ffff, #ff00ff, transparent);
        animation: scanline 3s linear infinite;
    }
    @keyframes scanline {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .hero-banner h1 {
        font-family: 'Orbitron', sans-serif !important;
        color: #ffffff;
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0 0 0.6rem 0;
        text-shadow: 0 0 20px #bf00ff, 0 0 40px rgba(180,0,255,0.5), 0 0 80px rgba(140,0,255,0.25);
    }
    .hero-banner p {
        color: #9d7dff;
        font-size: 1rem;
        margin: 0;
        font-family: 'Rajdhani', sans-serif;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    /* ── Search result header ── */
    .result-header {
        color: #00ffaa;
        font-size: 1.05rem;
        font-weight: 600;
        font-family: 'Orbitron', sans-serif;
        text-shadow: 0 0 10px rgba(0,255,170,0.5);
        letter-spacing: 0.04em;
    }

    /* ── Dividers ── */
    hr { border-color: rgba(140,0,255,0.3); }

    /* ── Text inputs ── */
    .stTextInput input,
    .stTextArea textarea {
        background: rgba(10,5,25,0.8) !important;
        color: #e0d6ff !important;
        border: 1px solid rgba(140,0,255,0.5) !important;
        border-radius: 6px !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 1rem !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: rgba(200,0,255,0.8) !important;
        box-shadow: 0 0 15px rgba(180,0,255,0.3) !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        background: rgba(10,5,25,0.6);
        border: 1px dashed rgba(140,0,255,0.5);
        border-radius: 10px;
        padding: 0.5rem;
    }

    /* ── Expander ── */
    details {
        background: rgba(10,5,20,0.5);
        border: 1px solid rgba(120,0,255,0.3);
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    details summary {
        color: #bf00ff !important;
        font-family: 'Orbitron', sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.06em;
        text-shadow: 0 0 8px rgba(200,0,255,0.4);
        padding: 0.5rem 0.8rem;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border: 1px solid rgba(120,0,255,0.3);
        border-radius: 8px;
    }

    /* ── Alert / info / success / warning boxes ── */
    [data-testid="stAlert"] {
        border-radius: 8px;
        border-left-width: 3px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.95rem;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #050510; }
    ::-webkit-scrollbar-thumb {
        background: rgba(140,0,255,0.5);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(200,0,255,0.8);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Initialise DB and directories once per session
# ---------------------------------------------------------------------------

db.init_db()
det.ensure_dirs()

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding: 1rem 0 1.2rem 0;'>
            <div style='font-size:2.8rem; filter: drop-shadow(0 0 12px #00ffff);'>🔮</div>
            <div style='color:#00ffff; font-family:"Orbitron", sans-serif; font-weight:900; font-size:1.15rem;
                        letter-spacing:0.08em; text-shadow: 0 0 15px rgba(0,255,255,0.7);'>
                AI SCENE MEMORY
            </div>
            <div style='color:#ff00ff; font-family:"Rajdhani", sans-serif; font-weight:600; font-size:0.85rem;
                        letter-spacing:0.12em; text-transform:uppercase;'>
                Neural Object Tracker
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio(
        "Navigate",
        options=[
            "🏠 Dashboard",
            "📸 Add Scene",
            "🔍 Search Objects",
            "📋 Scene History",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown(
        "<div style='color:#8c75b8; font-size:0.75rem; text-align:center; font-family:Rajdhani, sans-serif; letter-spacing:0.05em;'>"
        "POWERED BY <b style='color:#00ffff;'>YOLOv8n</b> · <b style='color:#ff00ff;'>SQLite</b> · <b style='color:#bf00ff;'>Streamlit</b>"
        "</div>",
        unsafe_allow_html=True,
    )

# ===========================================================================
# Helpers
# ===========================================================================

def _pil_from_path(path: str) -> Optional[Image.Image]:
    """Load a PIL image from *path*; return None if missing."""
    if path and os.path.isfile(path):
        try:
            return Image.open(path)
        except Exception:
            return None
    return None


def _tags_html(detections: List[Dict[str, Any]]) -> str:
    """Render detection dicts as coloured HTML tag spans."""
    if not detections:
        return "<span style='color:#6b8cae;'>None detected</span>"
    tags = [
        f"<span class='obj-tag'>{d['label']} "
        f"<span style='opacity:.7'>{d['confidence']:.0%}</span></span>"
        for d in detections
    ]
    return "".join(tags)


# ===========================================================================
# Page 1 — Dashboard
# ===========================================================================

def page_dashboard() -> None:
    st.markdown(
        """
        <div class='hero-banner'>
            <h1>🔍 AI Lost-Object & Scene Memory</h1>
            <p>Upload room photos · Detect objects · Find where you last saw your stuff</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stats = db.get_stats()

    # --- KPI row ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📸 Saved Scenes", stats["total_scenes"])
    with col2:
        st.metric("🎯 Total Detections", stats["total_detections"])
    with col3:
        unique_labels = len(stats["label_counts"])
        st.metric("🏷️ Unique Object Types", unique_labels)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Top detected objects chart ---
    if stats["top_objects"]:
        st.markdown("<div class='section-title'>📊 Most Frequently Detected Objects</div>",
                    unsafe_allow_html=True)

        top_n = stats["top_objects"][:15]
        labels_list  = [item[0] for item in top_n]
        counts_list  = [item[1] for item in top_n]

        chart_df = pd.DataFrame({"Object": labels_list, "Count": counts_list})
        chart_df = chart_df.set_index("Object")
        st.bar_chart(chart_df, height=340, use_container_width=True)

        # Tabular breakdown
        st.markdown("<br>", unsafe_allow_html=True)
        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.markdown("<div class='section-title' style='font-size:1rem;'>🏷️ Top 10 Objects</div>",
                        unsafe_allow_html=True)
            top_df = pd.DataFrame(top_n[:10], columns=["Object", "Times Detected"])
            st.dataframe(top_df, use_container_width=True, hide_index=True)

        with col_b:
            # Recent scenes mini-list
            st.markdown("<div class='section-title' style='font-size:1rem;'>🕐 Recent Scenes</div>",
                        unsafe_allow_html=True)
            recent = db.get_all_scenes(limit=5)
            if recent:
                for s in recent:
                    labels_str = ", ".join(det.get_unique_labels(s["detected_objects"])) or "—"
                    st.markdown(
                        f"<div class='scene-card'>"
                        f"<b style='color:#00ffff; font-family:Orbitron, sans-serif; font-size:0.95rem;'>📍 {s['room_name']}</b>"
                        f"<span style='color:#bf00ff; float:right; font-size:0.8rem; font-family:Rajdhani, sans-serif;'>"
                        f"🕐 {s['timestamp']}</span><br>"
                        f"<span style='color:#c9b8ff; font-size:0.86rem;'>🏷️ {labels_str}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No scenes saved yet. Go to **Add Scene** to get started!")

    else:
        st.info("📭 No data yet. Upload a photo on the **Add Scene** page to get started!")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>🚀 Quick Start Guide</div>", unsafe_allow_html=True)
        steps = [
            ("📸", "Go to <b>Add Scene</b> in the sidebar."),
            ("🖼️", "Upload a photo of any room, desk, or space."),
            ("🏷️", "Enter the room name and click <b>Detect & Save</b>."),
            ("🔍", "Use <b>Search Objects</b> to find where you last saw something."),
            ("📋", "Browse <b>Scene History</b> to review all saved snapshots."),
        ]
        for icon, text in steps:
            st.markdown(
                f"<div class='scene-card'><span style='font-size:1.3rem; margin-right:8px;'>{icon}</span> "
                f"<span style='color:#e0d6ff; font-size:0.95rem;'>{text}</span></div>",
                unsafe_allow_html=True,
            )


# ===========================================================================
# Page 2 — Add Scene
# ===========================================================================

def page_add_scene() -> None:
    st.markdown("<div class='section-title'>📸 Add a New Scene</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#7fa8d4;'>"
        "Upload a photo and let the AI detect objects. "
        "The annotated photo is saved so you can search for objects later."
        "</p>",
        unsafe_allow_html=True,
    )

    # ----- Upload & metadata form -----
    with st.form("add_scene_form", clear_on_submit=False):
        uploaded_file = st.file_uploader(
            "📂 Upload a room / scene photo",
            type=["jpg", "jpeg", "png"],
            help="Supported formats: JPG, JPEG, PNG",
        )

        col1, col2 = st.columns([1, 2])
        with col1:
            room_name = st.text_input(
                "🏷️ Room / Location Name",
                placeholder="e.g. Bedroom, Office, College Lab",
            )
        with col2:
            description = st.text_area(
                "📝 Optional Description",
                placeholder="e.g. Desk near the window. My blue backpack is on the chair.",
                height=90,
            )

        submit_btn = st.form_submit_button(
            "🚀 Detect Objects & Save Scene",
            use_container_width=True,
        )

    # ----- Processing -----
    if submit_btn:
        # --- Validation ---
        if uploaded_file is None:
            st.warning("⚠️ Please upload an image first.")
            return

        if not room_name or not room_name.strip():
            st.warning("⚠️ Please enter a room / location name.")
            return

        room_name = room_name.strip()

        # --- Load image ---
        try:
            image = Image.open(BytesIO(uploaded_file.read()))
        except Exception:
            st.error("❌ Could not open the uploaded file. Please upload a valid JPG or PNG image.")
            return

        # --- Load model ---
        model = det.load_model()
        if model is None:
            st.error(
                "❌ AI model could not be loaded. "
                "Ensure `ultralytics` and `torch` are installed correctly."
            )
            return

        # --- Run detection ---
        with st.spinner("🤖 Detecting objects …"):
            detections, annotated_img = det.detect_objects(image, model)

        # --- Save images ---
        original_path  = det.save_uploaded_image(image, prefix="orig")
        if annotated_img is not None:
            annotated_path = det.save_annotated_image(annotated_img, prefix="ann")
        else:
            annotated_path = original_path

        # --- Save to DB ---
        scene_id = db.save_scene(
            room_name=room_name,
            description=description.strip(),
            original_path=original_path,
            annotated_path=annotated_path,
            detected_objects=detections,
        )

        # --- Display results ---
        st.success(f"✅ Scene saved successfully! (ID: {scene_id})")

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**Original Image**")
            st.image(image, use_container_width=True)
        with col_right:
            st.markdown("**AI Annotated Image**")
            if annotated_img is not None:
                st.image(annotated_img, use_container_width=True)
            else:
                st.image(image, use_container_width=True)

        # Detection summary
        st.markdown("<br>", unsafe_allow_html=True)
        if detections:
            st.markdown(f"### 🎯 Detected {len(detections)} Object(s)")
            # Table
            det_df = pd.DataFrame(detections)
            det_df.columns = ["Object", "Confidence"]
            det_df["Confidence"] = det_df["Confidence"].apply(lambda x: f"{x:.1%}")
            st.dataframe(det_df, use_container_width=True, hide_index=True)
        else:
            st.info(
                "🤷 No objects were detected in this image. "
                "Try a clearer photo or one with more distinct objects."
            )

        # Tags
        st.markdown("<br>**Detected Tags:**", unsafe_allow_html=True)
        st.markdown(_tags_html(detections), unsafe_allow_html=True)


# ===========================================================================
# Page 3 — Search Objects
# ===========================================================================

def page_search() -> None:
    st.markdown("<div class='section-title'>🔍 Search for an Object</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#c9b8ff; font-size:1rem;'>"
        "Enter an object name to find which room it was last detected in. "
        "Results show the <b style='color:#00ffff;'>last recorded sighting</b> — not the object's guaranteed current location."
        "</p>",
        unsafe_allow_html=True,
    )

    query = st.text_input(
        "🔎 Object to find",
        placeholder="e.g. backpack, laptop, bottle, chair, person …",
        key="search_input",
    )

    search_btn = st.button("Search", key="search_btn")

    if search_btn or query:
        if not query.strip():
            st.warning("⚠️ Please type an object name to search.")
            return

        results = db.search_objects(query.strip())

        if not results:
            st.markdown(
                f"<div class='scene-card' style='border-color:rgba(255,0,100,0.6); box-shadow:0 0 15px rgba(255,0,100,0.2);'>"
                f"😕 No records found for <b style='color:#ff007f;'>\"{query}\"</b>. "
                f"Try a different keyword or add more scenes!"
                f"</div>",
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            f"<div class='result-header'>"
            f"✅ Found <b>{len(results)}</b> scene(s) containing "
            f"<b style='color:#00ffff;'>\"{query}\"</b>"
            f"</div><br>",
            unsafe_allow_html=True,
        )

        for scene in results:
            # Highlight the matching detections
            matched = [
                d for d in scene["detected_objects"]
                if query.strip().lower() in d["label"].lower()
            ]
            others  = [
                d for d in scene["detected_objects"]
                if query.strip().lower() not in d["label"].lower()
            ]

            with st.container():
                st.markdown(
                    f"<div class='scene-card'>",
                    unsafe_allow_html=True,
                )

                col_img, col_info = st.columns([1, 2])

                with col_img:
                    img = _pil_from_path(scene["annotated_path"])
                    if img:
                        st.image(img, use_container_width=True)
                    else:
                        st.markdown(
                            "<div style='height:130px; background:#0e0824; border:1px solid rgba(140,0,255,0.3); "
                            "border-radius:8px; display:flex; align-items:center; "
                            "justify-content:center; color:#8c75b8;'>No image</div>",
                            unsafe_allow_html=True,
                        )

                with col_info:
                    st.markdown(
                        f"<b style='font-size:1.2rem; color:#00ffff; font-family:Orbitron, sans-serif; "
                        f"text-shadow:0 0 10px rgba(0,255,255,0.5);'>"
                        f"📍 {scene['room_name']}</b>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<span style='color:#bf00ff; font-size:0.85rem; font-family:Rajdhani, sans-serif; font-weight:600;'>"
                        f"🕐 Last seen: {scene['timestamp']}</span>",
                        unsafe_allow_html=True,
                    )
                    if scene.get("description"):
                        st.markdown(
                            f"<span style='color:#e0d6ff; font-size:0.92rem; display:block; margin:4px 0;'>"
                            f"📝 {scene['description']}</span>",
                            unsafe_allow_html=True,
                        )
                    st.markdown("<br>", unsafe_allow_html=True)
                    if matched:
                        st.markdown(
                            "<span style='color:#00ffaa; font-size:0.85rem;"
                            " font-weight:700; font-family:Orbitron, sans-serif;'>🎯 Matched target:</span> "
                            + "".join(
                                f"<span class='obj-tag' style='background:rgba(0,255,170,0.15); "
                                f"border:1px solid #00ffaa; color:#00ffaa; box-shadow:0 0 10px rgba(0,255,170,0.4);'>"
                                f"{d['label']} {d['confidence']:.0%}</span>"
                                for d in matched
                            ),
                            unsafe_allow_html=True,
                        )
                    if others:
                        st.markdown(
                            "<span style='color:#9d7dff; font-size:0.85rem; font-family:Rajdhani, sans-serif;'>"
                            "Other objects detected:</span> "
                            + _tags_html(others),
                            unsafe_allow_html=True,
                        )

                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")

        st.info(
            "💡 These results show the **last recorded sighting** of the object. "
            "The object may have moved since this photo was taken."
        )


# ===========================================================================
# Page 4 — Scene History
# ===========================================================================

def page_history() -> None:
    st.markdown("<div class='section-title'>📋 Scene History</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#c9b8ff; font-size:1rem;'>Browse all saved scenes. "
        "Click <b style='color:#ff007f;'>Delete</b> to permanently remove a scene and its saved image assets.</p>",
        unsafe_allow_html=True,
    )

    scenes = db.get_all_scenes()

    if not scenes:
        st.info("📭 No scenes saved yet. Go to **Add Scene** to get started!")
        return

    st.markdown(f"<span style='color:#00ffff; font-family:Orbitron, sans-serif; font-size:0.95rem; font-weight:700;'>💾 {len(scenes)} SCENE(S) STORED IN MEMORY</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Track which scene to delete (avoid mutating list mid-loop) ---
    delete_id: Optional[int] = None

    for scene in scenes:
        with st.expander(
            f"📍 {scene['room_name']}  |  🕐 {scene['timestamp']}  "
            f"|  ID #{scene['id']}",
            expanded=False,
        ):
            col_img, col_info = st.columns([1, 2])

            with col_img:
                ann_img = _pil_from_path(scene["annotated_path"])
                if ann_img:
                    st.image(ann_img, caption="Annotated", use_container_width=True)
                else:
                    orig_img = _pil_from_path(scene["original_path"])
                    if orig_img:
                        st.image(orig_img, caption="Original (annotated missing)",
                                 use_container_width=True)
                    else:
                        st.markdown(
                            "<div style='background:#0e0824; border:1px solid rgba(140,0,255,0.3); border-radius:8px; "
                            "padding:2rem; text-align:center; color:#8c75b8;'>Image file not found</div>",
                            unsafe_allow_html=True,
                        )

            with col_info:
                st.markdown(
                    f"<b style='color:#00ffff; font-family:Orbitron, sans-serif; font-size:1.15rem; "
                    f"text-shadow:0 0 10px rgba(0,255,255,0.5);'>"
                    f"🏠 {scene['room_name']}</b>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<span style='color:#bf00ff; font-family:Rajdhani, sans-serif; font-weight:600;'>🕐 {scene['timestamp']}</span>",
                    unsafe_allow_html=True,
                )
                if scene.get("description"):
                    st.markdown(
                        f"<blockquote style='border-left:3px solid #ff00ff; background:rgba(255,0,255,0.06); "
                        f"padding:0.6rem 0.8rem; border-radius:4px; color:#e0d6ff; margin:0.5rem 0; font-size:0.95rem;'>"
                        f"{scene['description']}</blockquote>",
                        unsafe_allow_html=True,
                    )

                # Detected objects
                objs = scene["detected_objects"]
                st.markdown("<br>**Detected objects:**", unsafe_allow_html=True)
                st.markdown(_tags_html(objs), unsafe_allow_html=True)

                if objs:
                    # Mini table
                    det_df = pd.DataFrame(objs)
                    det_df.columns = ["Object", "Confidence"]
                    det_df["Confidence"] = det_df["Confidence"].apply(
                        lambda x: f"{x:.1%}"
                    )
                    st.dataframe(det_df, use_container_width=True, hide_index=True)

                # Delete button
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(
                    f"🗑️ Delete Scene #{scene['id']}",
                    key=f"del_{scene['id']}",
                    type="secondary",
                ):
                    delete_id = scene["id"]

    # Handle deletion outside the loop
    if delete_id is not None:
        success = db.delete_scene(delete_id)
        if success:
            st.success(f"✅ Scene #{delete_id} deleted successfully.")
        else:
            st.error(f"❌ Could not delete scene #{delete_id}.")
        st.rerun()


# ===========================================================================
# Router
# ===========================================================================

if page == "🏠 Dashboard":
    page_dashboard()
elif page == "📸 Add Scene":
    page_add_scene()
elif page == "🔍 Search Objects":
    page_search()
elif page == "📋 Scene History":
    page_history()
