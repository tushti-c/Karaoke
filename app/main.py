import random
import string
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import db, init_db
from .taste import GENRES, QUIZ, score_quiz

DEEZER = "https://api.deezer.com"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Karaoke Song Board")


init_db()

_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 600


async def deezer(path: str, **params) -> dict:
    key = path + repr(sorted(params.items()))
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{DEEZER}{path}", params=params)
    if r.status_code != 200:
        raise HTTPException(502, "Music catalogue unavailable")
    data = r.json()
    if "error" in data:
        raise HTTPException(502, data["error"].get("message", "Music catalogue error"))
    _cache[key] = (time.time() + CACHE_TTL, data)
    return data


def track_out(t: dict) -> dict:
    return {
        "deezer_id": t["id"],
        "title": t.get("title_short") or t["title"],
        "artist": t["artist"]["name"],
        "cover": (t.get("album") or {}).get("cover_medium"),
        "preview": t.get("preview"),
        "link": t.get("link"),
    }


# ---------- rooms ----------

class RoomIn(BaseModel):
    name: str = Field(default="Karaoke Night", max_length=60)


def new_code() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


@app.post("/api/rooms")
def create_room(body: RoomIn):
    with db() as conn:
        for _ in range(10):
            code = new_code()
            if not conn.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone():
                conn.execute(
                    "INSERT INTO rooms(code,name,created_at) VALUES(?,?,?)",
                    (code, body.name.strip() or "Karaoke Night", time.time()),
                )
                return {"code": code, "name": body.name}
    raise HTTPException(500, "Could not allocate room code")


@app.get("/api/rooms/{code}")
def get_room(code: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM rooms WHERE code=?", (code,)).fetchone()
    if not row:
        raise HTTPException(404, "Room not found")
    return dict(row)


# ---------- taste quiz ----------

@app.get("/api/quiz")
def quiz():
    return {"questions": QUIZ, "genres": GENRES}


class QuizAnswers(BaseModel):
    answers: list[int]


@app.post("/api/quiz")
def submit_quiz(body: QuizAnswers):
    return score_quiz(body.answers)


# ---------- catalogue ----------

@app.get("/api/suggest")
async def suggest(genre: str, limit: int = Query(30, le=100)):
    g = GENRES.get(genre)
    if not g:
        raise HTTPException(404, "Unknown genre")
    data = await deezer(f"/chart/{g['deezer_id']}/tracks", limit=limit)
    return {"genre": genre, "tracks": [track_out(t) for t in data.get("data", [])]}


@app.get("/api/search")
async def search(q: str = Query(min_length=1, max_length=100), limit: int = Query(20, le=50)):
    data = await deezer("/search", q=q, limit=limit)
    return {"tracks": [track_out(t) for t in data.get("data", [])]}


PLAYLIST_QUERIES = ["karaoke hits", "sing along anthems", "party hits", "80s hits", "90s hits", "00s hits"]
PLAYLIST_SKIP = ("lofi", "lo-fi", "sleep", "relax", "study", "piano", "instrumental", "calm", "focus", "meditat")


@app.get("/api/playlists")
async def playlists():
    found = []
    for q in PLAYLIST_QUERIES:
        found += (await deezer("/search/playlist", q=q, limit=5)).get("data", [])
    found += (await deezer("/chart/0/playlists", limit=20)).get("data", [])
    seen, out = set(), []
    for p in found:
        title = p["title"].lower()
        if p["id"] in seen or p.get("nb_tracks", 0) < 15 or any(s in title for s in PLAYLIST_SKIP):
            continue
        seen.add(p["id"])
        out.append(
            {"id": p["id"], "title": p["title"], "cover": p.get("picture_medium"), "tracks": p.get("nb_tracks")}
        )
    return {"playlists": out}


@app.get("/api/playlists/{pid}")
async def playlist_tracks(pid: int, limit: int = Query(50, le=100)):
    data = await deezer(f"/playlist/{pid}/tracks", limit=limit)
    return {"tracks": [track_out(t) for t in data.get("data", []) if t.get("artist")]}


# ---------- board ----------

class SongIn(BaseModel):
    deezer_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    cover: str | None = None
    preview: str | None = None
    genre: str | None = None
    user_id: str = Field(min_length=4, max_length=64)
    user_name: str = Field(default="", max_length=40)


def leaderboard(conn, room: str, user_id: str | None):
    rows = conn.execute(
        """
        SELECT s.*, COUNT(v.user_id) AS votes,
               SUM(CASE WHEN v.user_id=? THEN 1 ELSE 0 END) AS mine
        FROM songs s LEFT JOIN votes v ON v.song_id=s.id
        WHERE s.room=?
        GROUP BY s.id
        ORDER BY votes DESC, s.created_at ASC
        """,
        (user_id or "", room),
    ).fetchall()
    return [{**r, "mine": bool(r["mine"])} for r in rows]


@app.get("/api/rooms/{code}/songs")
def list_songs(code: str, user_id: str | None = None):
    with db() as conn:
        return {"songs": leaderboard(conn, code, user_id)}


@app.post("/api/rooms/{code}/songs")
def add_song(code: str, body: SongIn):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone():
            raise HTTPException(404, "Room not found")
        existing = None
        if body.deezer_id:
            existing = conn.execute(
                "SELECT id FROM songs WHERE room=? AND deezer_id=?", (code, body.deezer_id)
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM songs WHERE room=? AND lower(title)=lower(?) AND lower(artist)=lower(?)",
                (code, body.title.strip(), body.artist.strip()),
            ).fetchone()
        if existing:
            song_id = existing["id"]
            already = True
        else:
            song_id = conn.insert_returning_id(
                """INSERT INTO songs(room,deezer_id,title,artist,cover,preview,genre,added_by,added_by_name,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    code, body.deezer_id, body.title.strip(), body.artist.strip(), body.cover,
                    body.preview, body.genre, body.user_id, body.user_name.strip(), time.time(),
                ),
            )
            already = False
        conn.insert_ignore(
            "INSERT INTO votes(song_id,user_id,created_at) VALUES(?,?,?)",
            (song_id, body.user_id, time.time()),
        )
        return {"song_id": song_id, "already_listed": already, "songs": leaderboard(conn, code, body.user_id)}


class VoteIn(BaseModel):
    user_id: str = Field(min_length=4, max_length=64)


@app.post("/api/rooms/{code}/songs/{song_id}/vote")
def toggle_vote(code: str, song_id: int, body: VoteIn):
    with db() as conn:
        song = conn.execute("SELECT id FROM songs WHERE id=? AND room=?", (song_id, code)).fetchone()
        if not song:
            raise HTTPException(404, "Song not found")
        if conn.execute(
            "SELECT 1 FROM votes WHERE song_id=? AND user_id=?", (song_id, body.user_id)
        ).fetchone():
            conn.execute("DELETE FROM votes WHERE song_id=? AND user_id=?", (song_id, body.user_id))
            voted = False
        else:
            conn.execute(
                "INSERT INTO votes(song_id,user_id,created_at) VALUES(?,?,?)",
                (song_id, body.user_id, time.time()),
            )
            voted = True
        return {"voted": voted, "songs": leaderboard(conn, code, body.user_id)}


# ---------- pages ----------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/r/{code}")
def room_page(code: str):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone():
            return RedirectResponse("/?missing=1")
    return FileResponse(STATIC_DIR / "room.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def debug_404(request: Request, exc: StarletteHTTPException):
    detail = {"detail": exc.detail}
    if exc.status_code == 404:
        detail["debug"] = {k: str(request.scope.get(k)) for k in ("path", "root_path", "raw_path", "method")}
    return JSONResponse(detail, status_code=exc.status_code)
