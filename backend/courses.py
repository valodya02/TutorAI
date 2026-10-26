import json
import logging
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.schemas import MAX_COURSE_BYTES, Course

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
COURSES = ROOT / "data" / "courses"
COURSES.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/courses", tags=["courses"])


def course_path(course_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}", course_id):
        raise HTTPException(404, "План не найден")
    return COURSES / f"{course_id}.json"


def read_course(course_id: str) -> dict:
    path = course_path(course_id)
    if not path.exists():
        raise HTTPException(404, "План не найден")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read course %s", path)
        raise HTTPException(500, "Не удалось прочитать план")


def write_course(data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if len(payload.encode("utf-8")) > MAX_COURSE_BYTES:
        raise HTTPException(413, "План курса слишком велик")
    course_path(data["id"]).write_text(payload, encoding="utf-8")


@router.post("")
def save_course(body: Course):
    data = {
        "id": uuid.uuid4().hex[:8],
        "created": time.strftime("%Y-%m-%d %H:%M"),
        **body.model_dump(),
    }
    write_course(data)
    return {"id": data["id"]}


@router.put("/{course_id}")
def update_course(course_id: str, body: Course):
    data = read_course(course_id)
    data.update(body.model_dump())
    write_course(data)
    return {"ok": True}


@router.get("")
def list_courses():
    files = sorted(COURSES.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append({key: data[key] for key in ("id", "goal", "level", "created")})
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Skipping unreadable course file %s", path, exc_info=True)
    return result


@router.get("/{course_id}")
def get_course(course_id: str):
    return read_course(course_id)


@router.delete("/{course_id}")
def delete_course(course_id: str):
    read_course(course_id)  # 404, если нет
    course_path(course_id).unlink()
    return {"ok": True}
