"""
Serveur Flask — multi-candidats en parallèle.
Stats persistantes : calculées depuis sent_applications.json + état sur disque.
"""

import asyncio
import json
import queue
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from automation import CITIES_DEFAULT, extract_cv_info

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
CONFIG_FILE = Path("config.json")
STATE_FILE = Path("candidates_state.json")
SENT_FILE = Path("sent_applications.json")
ALL_CITY_NAMES = [c["name"] for c in CITIES_DEFAULT]

# ---------------------------------------------------------------------------
# État global multi-candidats
# ---------------------------------------------------------------------------

log_queue: queue.Queue = queue.Queue(maxsize=1000)

candidates: dict[str, dict] = {}
candidates_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Config / state helpers
# ---------------------------------------------------------------------------


def get_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"candidates": []}


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_state() -> dict:
    """Charge l'état persistant des candidats (paused_until, last_city, etc.)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_sent() -> list:
    if SENT_FILE.exists():
        try:
            return json.loads(SENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def count_sent_for_candidate(cid: str) -> int:
    """Compte les candidatures envoyées pour un candidat."""
    return sum(1 for s in load_sent() if s.get("candidate_id") == cid)


def count_sent_today_for_candidate(cid: str) -> int:
    """Compte les candidatures envoyées AUJOURD'HUI pour un candidat."""
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(
        1 for s in load_sent()
        if s.get("candidate_id") == cid and s.get("date") == today
    )


def build_stats_for_candidate(cid: str) -> dict:
    """Construit les stats persistantes d'un candidat."""
    state = load_state().get(cid, {})
    return {
        "status": state.get("status", "stopped"),
        "sent_total": count_sent_for_candidate(cid),
        "sent_today": count_sent_today_for_candidate(cid),
        "skipped": state.get("skipped", 0),
        "errors": state.get("errors", 0),
        "current_city": state.get("current_city", ""),
        "current_job": state.get("current_job", ""),
        "current_company": state.get("current_company", ""),
        "paused_until": state.get("paused_until"),
        "last_city_index": state.get("last_city_index", 0),
        "last_job_index": state.get("last_job_index", 0),
    }


# ---------------------------------------------------------------------------
# Callbacks (appelés par automation.py)
# ---------------------------------------------------------------------------


def add_log(entry: dict) -> None:
    try:
        log_queue.put_nowait(entry)
    except queue.Full:
        try:
            log_queue.get_nowait()
            log_queue.put_nowait(entry)
        except Exception:
            pass


def update_candidate_status(candidate_id: str, stats: dict) -> None:
    """Mise à jour en mémoire + persistance sur disque."""
    with candidates_lock:
        if candidate_id in candidates:
            candidates[candidate_id]["stats"] = stats

    # Persiste les champs importants
    state = load_state()
    state[candidate_id] = {
        "status": stats.get("status", "stopped"),
        "skipped": stats.get("skipped", 0),
        "errors": stats.get("errors", 0),
        "current_city": stats.get("current_city", ""),
        "current_job": stats.get("current_job", ""),
        "current_company": stats.get("current_company", ""),
        "paused_until": stats.get("paused_until"),
        "last_city_index": stats.get("last_city_index", 0),
        "last_job_index": stats.get("last_job_index", 0),
    }
    save_state(state)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        cities_json=json.dumps(ALL_CITY_NAMES, ensure_ascii=False),
    )


@app.get("/api/config")
def api_get_config():
    return jsonify(get_config())


@app.post("/api/config")
def api_save_config():
    cfg = request.get_json(force=True)
    save_config(cfg)
    return jsonify({"ok": True})


# ── Candidate management ─────────────────────────────────────────────────────

@app.get("/api/candidates")
def api_list_candidates():
    cfg = get_config()
    result = []
    for c in cfg.get("candidates", []):
        cid = c.get("id", "")
        # Mémoire d'abord (si en cours d'exécution)
        with candidates_lock:
            runtime = candidates.get(cid, {})
        if runtime.get("stats"):
            stats = runtime["stats"].copy()
            # Toujours recalculer sent depuis le fichier
            stats["sent_total"] = count_sent_for_candidate(cid)
            stats["sent_today"] = count_sent_today_for_candidate(cid)
        else:
            stats = build_stats_for_candidate(cid)
        result.append({**c, "status": stats.get("status", "stopped"), "stats": stats})
    return jsonify(result)


@app.post("/api/candidates")
def api_add_candidate():
    data = request.get_json(force=True)
    cid = data.get("id") or str(uuid.uuid4())[:8]
    data["id"] = cid
    cfg = get_config()
    cfg.setdefault("candidates", []).append(data)
    save_config(cfg)
    return jsonify({"ok": True, "id": cid})


@app.put("/api/candidates/<cid>")
def api_update_candidate(cid):
    data = request.get_json(force=True)
    data["id"] = cid
    cfg = get_config()
    found = False
    for i, c in enumerate(cfg.get("candidates", [])):
        if c.get("id") == cid:
            cfg["candidates"][i] = data
            found = True
            break
    if not found:
        return jsonify({"error": "Candidat introuvable"}), 404
    save_config(cfg)
    return jsonify({"ok": True})


@app.delete("/api/candidates/<cid>")
def api_delete_candidate(cid):
    _stop_candidate(cid)
    cfg = get_config()
    cfg["candidates"] = [c for c in cfg.get("candidates", []) if c.get("id") != cid]
    save_config(cfg)
    # Nettoyer l'état persistant
    state = load_state()
    state.pop(cid, None)
    save_state(state)
    return jsonify({"ok": True})


# ── CV upload + extraction ───────────────────────────────────────────────────

@app.post("/api/upload/cv")
def api_upload_cv():
    cid = request.form.get("candidate_id", "default")
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "Aucun fichier sélectionné"}), 400
    if not f.filename.lower().endswith((".pdf", ".docx")):
        return jsonify({"error": "Seuls les fichiers PDF/DOCX sont acceptés"}), 400

    f.read(5)
    f.seek(0)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(f.filename).suffix.lower()
    dest = (UPLOADS_DIR / f"cv_{cid}{ext}").resolve()
    f.save(dest)

    extracted = {}
    if ext == ".pdf":
        extracted = extract_cv_info(str(dest))

    return jsonify({
        "ok": True,
        "cv_path": str(dest),
        "original_name": f.filename,
        "extracted": extracted,
    })


# ── Start / Stop / Status ───────────────────────────────────────────────────

@app.post("/api/start/<cid>")
def api_start_candidate(cid):
    with candidates_lock:
        if cid in candidates and candidates[cid].get("stats", {}).get("status") == "running":
            return jsonify({"error": "Déjà en cours"}), 400

    cfg = get_config()
    candidate_cfg = None
    for c in cfg.get("candidates", []):
        if c.get("id") == cid:
            candidate_cfg = c
            break
    if not candidate_cfg:
        return jsonify({"error": "Candidat introuvable"}), 404

    stop_event = threading.Event()
    pause_event = threading.Event()

    # Charger l'état persistant pour reprise
    saved_state = load_state().get(cid, {})

    # Si en pause, pré-configurer le pause_event
    if saved_state.get("paused_until"):
        pause_event.set()

    # Stats initiales depuis le disque
    initial_stats = build_stats_for_candidate(cid)
    initial_stats["status"] = "running"

    def _run():
        from automation import LBAAutomation

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        auto = LBAAutomation(
            candidate_id=cid,
            config=candidate_cfg,
            stop_event=stop_event,
            pause_event=pause_event,
            callbacks={"log": add_log, "status": update_candidate_status},
            resume_state=saved_state,
        )
        try:
            loop.run_until_complete(auto.run())
        except Exception as exc:
            add_log({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"[{candidate_cfg.get('firstname', '?')} {candidate_cfg.get('lastname', '?')}] Erreur critique: {exc}",
                "level": "error",
                "candidate_id": cid,
            })
        finally:
            loop.close()
            with candidates_lock:
                if cid in candidates:
                    candidates[cid]["stats"]["status"] = "stopped"
            # Persiste l'arrêt
            state = load_state()
            if cid in state:
                state[cid]["status"] = "stopped"
                save_state(state)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    with candidates_lock:
        candidates[cid] = {
            "config": candidate_cfg,
            "thread": t,
            "stop_event": stop_event,
            "pause_event": pause_event,
            "stats": initial_stats,
        }

    return jsonify({"ok": True})


@app.post("/api/stop/<cid>")
def api_stop_candidate(cid):
    _stop_candidate(cid)
    return jsonify({"ok": True})


def _stop_candidate(cid: str):
    with candidates_lock:
        if cid in candidates:
            candidates[cid]["stop_event"].set()
            candidates[cid]["stats"]["status"] = "stopping"
    state = load_state()
    if cid in state:
        state[cid]["status"] = "stopped"
        save_state(state)


@app.post("/api/start-all")
def api_start_all():
    cfg = get_config()
    started = []
    for c in cfg.get("candidates", []):
        cid = c.get("id", "")
        with candidates_lock:
            already = cid in candidates and candidates[cid].get("stats", {}).get("status") == "running"
        if not already:
            with app.test_request_context(json={}):
                api_start_candidate(cid)
            started.append(cid)
    return jsonify({"ok": True, "started": started})


@app.post("/api/stop-all")
def api_stop_all():
    with candidates_lock:
        for cid in list(candidates.keys()):
            candidates[cid]["stop_event"].set()
            candidates[cid]["stats"]["status"] = "stopping"
    state = load_state()
    for cid in state:
        state[cid]["status"] = "stopped"
    save_state(state)
    return jsonify({"ok": True})


@app.get("/api/status")
def api_status():
    cfg = get_config()
    result = {}
    for c in cfg.get("candidates", []):
        cid = c.get("id", "")
        with candidates_lock:
            runtime = candidates.get(cid, {})
        if runtime.get("stats"):
            stats = runtime["stats"].copy()
            stats["sent_total"] = count_sent_for_candidate(cid)
            stats["sent_today"] = count_sent_today_for_candidate(cid)
        else:
            stats = build_stats_for_candidate(cid)
        result[cid] = stats
    return jsonify(result)


@app.get("/api/status/<cid>")
def api_status_candidate(cid):
    with candidates_lock:
        runtime = candidates.get(cid, {})
    if runtime.get("stats"):
        stats = runtime["stats"].copy()
        stats["sent_total"] = count_sent_for_candidate(cid)
        stats["sent_today"] = count_sent_today_for_candidate(cid)
        return jsonify(stats)
    return jsonify(build_stats_for_candidate(cid))


# ── Logs SSE ─────────────────────────────────────────────────────────────────

@app.get("/api/logs/stream")
def api_logs_stream():
    def _generate():
        while True:
            try:
                entry = log_queue.get(timeout=2.0)
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── History ──────────────────────────────────────────────────────────────────

@app.get("/api/sent")
def api_sent():
    data = load_sent()
    return jsonify(data)


# ── Cities list ──────────────────────────────────────────────────────────────

@app.get("/api/cities")
def api_cities():
    return jsonify(ALL_CITY_NAMES)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)

