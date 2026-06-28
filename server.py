"""
EcoVision - FastAPI 服务端
垃圾分类实时识别 API + 数据统计
"""

import base64
import io
import json
import os
import time
import asyncio
import threading
import sqlite3
import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from PIL import Image

from guides_db import load_guides, get_guide, get_category_info, get_category
import guides_db

# ─── 全局 ───
_CLASSIFIER = None
_CLASSIFIER_LOCK = threading.Lock()
_PENDING_TASKS = set()

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "ecovision_stats.db"
STATIC_DIR = PROJECT_ROOT / "static"


# ═══════════════════════════════════════════
# SQLite 数据库初始化
# ═══════════════════════════════════════════

def _init_db():
    """Create tables if they don't exist."""
    with sqlite3.connect(str(DB_PATH), timeout=5) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recognition_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT NOT NULL,
                display_name TEXT NOT NULL,
                category    TEXT NOT NULL,
                confidence  REAL NOT NULL,
                inference_ms REAL NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_log_created
            ON recognition_log(created_at)
        """)
        conn.commit()


def _log_recognition(label, display_name, category, confidence, inference_ms):
    """Insert a recognition record."""
    try:
        with sqlite3.connect(str(DB_PATH), timeout=5) as conn:
            conn.execute(
                "INSERT INTO recognition_log (label, display_name, category, confidence, inference_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                (label, display_name, category, round(confidence, 2), round(inference_ms, 1)),
            )
            conn.commit()
    except Exception as e:
        print(f"[stats] 写入失败: {e}")


def _query_stats(start_date: str, end_date: str) -> dict:
    """Query statistics within a date range."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row

    # ── 总数 ──
    row = conn.execute(
        "SELECT COUNT(*) as total, AVG(confidence) as avg_conf "
        "FROM recognition_log WHERE created_at >= ? AND created_at <= ?",
        (start_date, end_date)
    ).fetchone()
    total = row["total"] or 0
    avg_conf = round((row["avg_conf"] or 0) * 100, 1)

    # ── 分类分布 ──
    rows = conn.execute(
        "SELECT category, COUNT(*) as count FROM recognition_log "
        "WHERE created_at >= ? AND created_at <= ? "
        "GROUP BY category ORDER BY count DESC",
        (start_date, end_date)
    ).fetchall()
    categories = [{"category": r["category"], "count": r["count"]} for r in rows]

    # ── 每日趋势 ──
    rows = conn.execute(
        "SELECT DATE(created_at) as day, COUNT(*) as count "
        "FROM recognition_log "
        "WHERE created_at >= ? AND created_at <= ? "
        "GROUP BY DATE(created_at) ORDER BY day",
        (start_date, end_date)
    ).fetchall()
    daily = [{"day": r["day"], "count": r["count"]} for r in rows]

    # ── 识别最多的物品 Top 20 ──
    rows = conn.execute(
        "SELECT display_name, label, category, COUNT(*) as count "
        "FROM recognition_log "
        "WHERE created_at >= ? AND created_at <= ? "
        "GROUP BY label ORDER BY count DESC LIMIT 20",
        (start_date, end_date)
    ).fetchall()
    top_items = [
        {"display_name": r["display_name"], "label": r["label"],
         "category": r["category"], "count": r["count"]}
        for r in rows
    ]

    conn.close()
    return {
        "total": total,
        "avg_confidence": avg_conf,
        "categories": categories,
        "daily": daily,
        "top_items": top_items,
    }


def _get_stats_date_range(days: int) -> tuple[str, str]:
    """计算统计查询的起止时间范围。"""
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if days == 1:
        start_dt = today_start
    else:
        start_dt = (now - datetime.timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_dt.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════
# 分类器
# ═══════════════════════════════════════════

def get_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is None:
        with _CLASSIFIER_LOCK:
            if _CLASSIFIER is None:
                try:
                    from classifier import GarbageClassifier
                    _CLASSIFIER = GarbageClassifier()
                except Exception as e:
                    print(f"[server] 分类器初始化失败: {e}")
                    _CLASSIFIER = None
    return _CLASSIFIER


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    load_guides(str(PROJECT_ROOT / "guides.json"))
    clf = get_classifier()
    if clf:
        try:
            clf.ensure_loaded()
        except Exception:
            pass
    print("[server] 启动完成")
    yield
    print("[server] 关闭")


app = FastAPI(title="EcoVision 环保之眼", version="2.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ═══════════════════════════════════════════
# API 模型
# ═══════════════════════════════════════════

class PredictRequest(BaseModel):
    image: str

    @field_validator("image")
    @classmethod
    def validate_base64_size(cls, v):
        if len(v) > 10 * 1024 * 1024:
            raise ValueError("图像数据过大，最大允许 10MB")
        return v


class PredictResponse(BaseModel):
    success: bool
    label: str = ""
    display_name: str = ""
    category: str = ""
    category_info: dict = {}
    confidence: float = 0
    top_predictions: list = []
    guide: dict = {}
    inference_ms: float = 0
    message: str = ""


# ═══════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/stats")
async def stats_page():
    return FileResponse(str(STATIC_DIR / "stats.html"))


@app.post("/api/predict", response_model=PredictResponse)
async def predict(data: PredictRequest):
    """接收 base64 图像，返回分类结果 + 指南"""
    start = time.time()

    try:
        raw = base64.b64decode(data.image)
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片解码失败: {e}")

    classifier = get_classifier()
    if classifier is None:
        return PredictResponse(
            success=False,
            message="模型未加载。请运行: pip install modelscope datasets mmcv",
            inference_ms=0,
        )

    results = await asyncio.to_thread(classifier.predict, image)
    infer_ms = (time.time() - start) * 1000

    if not results:
        return PredictResponse(success=False, inference_ms=round(infer_ms, 1))

    top = results[0]
    label = top["label"]
    score = top["score"]
    category = get_category(label)
    info = get_category_info(category)
    guide = get_guide(label)

    top_predictions = [
        {
            "label": r["label"],
            "display_name": get_guide(r["label"]).get("display_name", r["label"]),
            "score": round(r["score"] * 100, 1),
        }
        for r in results
    ]

    # 写入统计日志（异步）— 仅置信度 >= 5% 计入（过滤背景噪声）
    if score >= 0.50:
        async def _safe_log_recognition():
            try:
                await asyncio.to_thread(
                    _log_recognition,
                    label,
                    guide.get("display_name", label),
                    category,
                    score,
                    infer_ms,
                )
            except Exception as e:
                print(f"[stats] 异步写入失败: {e}")
        _task = asyncio.create_task(_safe_log_recognition())
        _PENDING_TASKS.add(_task)
        _task.add_done_callback(_PENDING_TASKS.discard)

    return PredictResponse(
        success=True,
        label=label,
        display_name=guide.get("display_name", label),
        category=category,
        category_info=info,
        confidence=round(score * 100, 1),
        top_predictions=top_predictions,
        guide=guide,
        inference_ms=round(infer_ms, 1),
    )


@app.get("/api/labels")
async def get_all_labels():
    guide_path = PROJECT_ROOT / "guides.json"
    if guide_path.exists():
        with open(guide_path, "r", encoding="utf-8") as f:
            guides = json.load(f)
        return {"count": len(guides), "labels": list(guides.keys())}
    return {"count": 0, "labels": []}


@app.get("/api/health")
async def health():
    c = get_classifier()
    guide_count = len(guides_db._GUIDES)
    return {
        "status": "ok",
        "classifier_loaded": c is not None and c.pipeline is not None,
        "device": c.device if c else "n/a",
        "mps_active": getattr(c, "pipeline", None) is not None
                      and next(c.pipeline.model.parameters()).device.type == "mps"
                      if c else False,
        "guide_count": guide_count,
        "stats_db_size": os.path.getsize(DB_PATH) if DB_PATH.exists() else 0,
    }


# ── 统计 API ──

class StatsParams(BaseModel):
    days: int = 7


@app.get("/api/stats")
async def get_stats(days: int = Query(7, ge=1, le=365, description="查询天数范围")):
    """获取指定天数内的识别统计汇总。"""
    start, end = _get_stats_date_range(days)
    data = await asyncio.to_thread(_query_stats, start, end)
    data["range_days"] = days
    data["start_date"] = start
    data["end_date"] = end
    # 补充分类信息
    cat_info = {}
    for c in data["categories"]:
        info = get_category_info(c["category"])
        c["color"] = info.get("color", "#6B7280")
        c["icon"] = info.get("icon", "🗑️")
        cat_info[c["category"]] = info
    data["category_info"] = cat_info
    return data


@app.get("/api/stats/export")
async def export_stats(days: int = Query(7, ge=1, le=365)):
    """导出识别记录为 JSON 列表。"""
    start, end = _get_stats_date_range(days)
    rows = await asyncio.to_thread(_export_stats_query, start, end)
    return rows

def _export_stats_query(start: str, end: str) -> list:
    """在后台线程执行 SQLite 查询，避免阻塞事件循环。"""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM recognition_log WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC LIMIT 10000",
        (start, end)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
