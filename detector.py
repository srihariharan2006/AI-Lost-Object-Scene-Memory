"""
detector.py
-----------
YOLOv8n object-detection helpers for AI Lost-Object & Scene Memory.

Key design decisions
--------------------
* Model is loaded once via @st.cache_resource so it survives Streamlit reruns.
* Inference runs on CPU (device='cpu') to support laptops without a GPU.
* Bounding boxes and labels are drawn with Pillow (no OpenCV dependency).
* Returns both a list of detection dicts and a PIL annotated Image object.
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import List, Dict, Tuple, Any, Optional

from PIL import Image, ImageDraw, ImageFont
import streamlit as st

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DETECTED_DIR = "detected_images"
UPLOADS_DIR = "uploads"

# Colour palette for bounding boxes (cycles through these colours)
BOX_COLOURS = [
    "#FF4B4B",  # red
    "#2196F3",  # blue
    "#4CAF50",  # green
    "#FF9800",  # orange
    "#9C27B0",  # purple
    "#00BCD4",  # cyan
    "#FFEB3B",  # yellow
    "#F06292",  # pink
]

CONF_THRESHOLD = 0.25   # Minimum confidence to report a detection
LINE_WIDTH = 3           # Bounding-box line width in pixels


# ---------------------------------------------------------------------------
# Ensure required directories exist
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    os.makedirs(DETECTED_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Model loading (cached so it only happens once per Streamlit session)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Loading AI model (one-time download) …")
def load_model():
    """
    Load and return the YOLOv8n model.

    The model weights are downloaded automatically by Ultralytics on first
    use and cached locally (~6 MB).  Subsequent loads are instant.

    Returns
    -------
    ultralytics.YOLO instance, or None if the load fails.
    """
    try:
        from ultralytics import YOLO  # imported here so the rest of the app
                                      # can still run even without GPU/torch
        model = YOLO("yolov8n.pt")
        logger.info("YOLOv8n model loaded successfully.")
        return model
    except Exception as exc:
        logger.error("Failed to load YOLOv8n model: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core detection function
# ---------------------------------------------------------------------------

def detect_objects(
    image: Image.Image,
    model=None,
) -> Tuple[List[Dict[str, Any]], Optional[Image.Image]]:
    """
    Run YOLOv8n inference on *image* and return detections + annotated image.

    Parameters
    ----------
    image : PIL.Image.Image
        The input image (any mode; converted to RGB internally).
    model : ultralytics.YOLO, optional
        Pre-loaded model object. If None, :func:`load_model` is called.

    Returns
    -------
    detections : list of dicts
        Each dict has keys ``label`` (str) and ``confidence`` (float, 0–1).
    annotated : PIL.Image.Image or None
        Image with bounding boxes and labels drawn, or None on failure.
    """
    ensure_dirs()

    if model is None:
        model = load_model()

    if model is None:
        return [], None

    # Normalise to RGB
    img_rgb = image.convert("RGB")

    try:
        results = model.predict(
            source=img_rgb,
            conf=CONF_THRESHOLD,
            device="cpu",
            verbose=False,
        )
    except Exception as exc:
        logger.error("YOLO inference failed: %s", exc)
        return [], None

    # -----------------------------------------------------------------------
    # Parse results
    # -----------------------------------------------------------------------
    detections: List[Dict[str, Any]] = []
    annotated_img = img_rgb.copy()
    draw = ImageDraw.Draw(annotated_img)

    # Try to use a nicer font; fall back to the built-in bitmap font
    try:
        font = ImageFont.truetype("arial.ttf", size=16)
        small_font = ImageFont.truetype("arial.ttf", size=13)
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    if results and len(results) > 0:
        result = results[0]  # single-image inference → first result

        boxes  = result.boxes
        names  = result.names  # {class_id: label}

        for i, box in enumerate(boxes):
            conf       = float(box.conf[0])
            class_id   = int(box.cls[0])
            label      = names.get(class_id, f"class_{class_id}")
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            # Record detection
            detections.append({"label": label, "confidence": round(conf, 3)})

            # Choose colour
            colour = BOX_COLOURS[i % len(BOX_COLOURS)]

            # Draw bounding box
            for offset in range(LINE_WIDTH):
                draw.rectangle(
                    [x1 - offset, y1 - offset, x2 + offset, y2 + offset],
                    outline=colour,
                )

            # Label background + text
            text = f"{label} {conf:.0%}"
            try:
                bbox = draw.textbbox((x1, y1), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                tw, th = draw.textsize(text, font=font)

            padding = 3
            label_y0 = max(y1 - th - 2 * padding, 0)
            draw.rectangle(
                [x1, label_y0, x1 + tw + 2 * padding, y1],
                fill=colour,
            )
            draw.text(
                (x1 + padding, label_y0 + padding),
                text,
                fill="white",
                font=font,
            )

    return detections, annotated_img


# ---------------------------------------------------------------------------
# File-save helpers
# ---------------------------------------------------------------------------

def save_uploaded_image(image: Image.Image, prefix: str = "upload") -> str:
    """
    Save *image* to the uploads directory with a unique filename.

    Returns the relative file path (str).
    """
    ensure_dirs()
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.jpg"
    path = os.path.join(UPLOADS_DIR, filename)
    image.convert("RGB").save(path, format="JPEG", quality=90)
    return path


def save_annotated_image(image: Image.Image, prefix: str = "annotated") -> str:
    """
    Save *image* to the detected_images directory with a unique filename.

    Returns the relative file path (str).
    """
    ensure_dirs()
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.jpg"
    path = os.path.join(DETECTED_DIR, filename)
    image.convert("RGB").save(path, format="JPEG", quality=90)
    return path


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def format_detections_text(detections: List[Dict[str, Any]]) -> str:
    """Return a human-readable summary of detections."""
    if not detections:
        return "No objects detected."
    parts = [f"{d['label']} ({d['confidence']:.0%})" for d in detections]
    return ", ".join(parts)


def get_unique_labels(detections: List[Dict[str, Any]]) -> List[str]:
    """Return a deduplicated, sorted list of detected labels."""
    return sorted({d["label"] for d in detections})
