from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/remind.db")
IMAGE_DIR = Path("data/images")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL UNIQUE,
                mime_type TEXT NOT NULL,
                caption TEXT NOT NULL,
                ocr_text TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                image_type TEXT NOT NULL,
                scene TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_image_record(
    *,
    filename: str,
    stored_path: str,
    mime_type: str,
    metadata: dict[str, Any],
    embedding: list[float],
) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO images(
                filename, stored_path, mime_type, caption, ocr_text,
                tags_json, image_type, scene, embedding_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                stored_path,
                mime_type,
                metadata.get("caption", ""),
                metadata.get("ocr_text", ""),
                json.dumps(metadata.get("tags", []), ensure_ascii=False),
                metadata.get("image_type", "unknown"),
                metadata.get("scene", ""),
                json.dumps(embedding),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_images() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM images ORDER BY id DESC").fetchall()
    return [_deserialize(dict(r)) for r in rows]


def get_images_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM images WHERE id IN ({placeholders})", ids
        ).fetchall()
    by_id = {int(r["id"]): _deserialize(dict(r)) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def count_images() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM images").fetchone()
    return int(count)


def clear_all() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM images")
        conn.commit()
    for path in IMAGE_DIR.glob("*"):
        if path.is_file() and path.name != ".gitkeep":
            path.unlink(missing_ok=True)


def _deserialize(row: dict[str, Any]) -> dict[str, Any]:
    row["tags"] = json.loads(row.pop("tags_json") or "[]")
    row["embedding"] = json.loads(row.pop("embedding_json") or "[]")
    return row
