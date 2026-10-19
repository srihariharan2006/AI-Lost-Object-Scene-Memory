"""
database.py
-----------
Handles all SQLite operations for AI Lost-Object & Scene Memory.
Automatically creates the database and required tables on first run.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = "scene_memory.db"


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they do not already exist."""
    with _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scenes (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                room_name         TEXT    NOT NULL,
                description       TEXT    DEFAULT '',
                original_path     TEXT    NOT NULL,
                annotated_path    TEXT    NOT NULL,
                detected_objects  TEXT    NOT NULL,   -- JSON list of {label, confidence}
                timestamp         TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_scenes_room
                ON scenes(room_name);

            CREATE INDEX IF NOT EXISTS idx_scenes_timestamp
                ON scenes(timestamp);
            """
        )


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def save_scene(
    room_name: str,
    description: str,
    original_path: str,
    annotated_path: str,
    detected_objects: List[Dict[str, Any]],
) -> int:
    """
    Insert a new scene record and return the new row ID.

    Parameters
    ----------
    room_name        : Label chosen by the user (e.g. 'Bedroom').
    description      : Optional free-text note.
    original_path    : Relative path to the uploaded image.
    annotated_path   : Relative path to the YOLO-annotated image.
    detected_objects : List of dicts with keys 'label' and 'confidence'.

    Returns
    -------
    Integer primary-key of the newly inserted row.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    objects_json = json.dumps(detected_objects)

    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO scenes
                (room_name, description, original_path, annotated_path,
                 detected_objects, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (room_name, description, original_path, annotated_path,
             objects_json, timestamp),
        )
        return cur.lastrowid


def delete_scene(scene_id: int) -> bool:
    """
    Delete a scene and its image files from disk.

    Returns True when the row was found and removed, False otherwise.
    """
    scene = get_scene_by_id(scene_id)
    if scene is None:
        return False

    # Remove image files safely
    for path_key in ("original_path", "annotated_path"):
        fpath = scene[path_key]
        if fpath and os.path.isfile(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass  # Log but do not crash

    with _get_conn() as conn:
        conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))

    return True


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_scene_by_id(scene_id: int) -> Optional[Dict[str, Any]]:
    """Return a single scene dict or None."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_all_scenes(limit: int = 200) -> List[Dict[str, Any]]:
    """Return all scenes ordered by most recent first."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scenes ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_objects(query: str) -> List[Dict[str, Any]]:
    """
    Case-insensitive search across detected_objects JSON column.

    Returns scenes that contain at least one detection whose label
    matches *query* as a substring.
    """
    if not query or not query.strip():
        return []

    # SQLite LIKE is case-insensitive for ASCII by default.
    pattern = f"%{query.strip().lower()}%"

    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM scenes
            WHERE LOWER(detected_objects) LIKE ?
            ORDER BY timestamp DESC
            """,
            (pattern,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Aggregation / dashboard helpers
# ---------------------------------------------------------------------------

def get_stats() -> Dict[str, Any]:
    """Return summary statistics for the dashboard."""
    with _get_conn() as conn:
        total_scenes = conn.execute(
            "SELECT COUNT(*) FROM scenes"
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT detected_objects FROM scenes"
        ).fetchall()

    # Count individual detections and build frequency map
    label_counts: Dict[str, int] = {}
    total_detections = 0

    for row in rows:
        objects = _parse_objects(row["detected_objects"])
        for obj in objects:
            label = obj.get("label", "unknown")
            label_counts[label] = label_counts.get(label, 0) + 1
            total_detections += 1

    # Sort by frequency descending
    top_objects = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_scenes": total_scenes,
        "total_detections": total_detections,
        "top_objects": top_objects,          # list of (label, count)
        "label_counts": label_counts,        # full dict for charting
    }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_objects(json_str: str) -> List[Dict[str, Any]]:
    """Safely parse the stored JSON blob."""
    try:
        return json.loads(json_str) if json_str else []
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict, parsing the JSON objects field."""
    d = dict(row)
    d["detected_objects"] = _parse_objects(d.get("detected_objects", "[]"))
    return d
