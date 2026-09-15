# Karaoke Song Board

Shareable song-voting board for karaoke nights. Open the link, take a 4-question
music-taste quiz, browse suggestions / playlists or search any song, add it, and
second the ones you like. The crowd's favourites rise to the top of the leaderboard.

Songs, cover art and 30s previews come from the public Deezer API (no key needed).

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Uses a local SQLite file in `data/` unless `DATABASE_URL` (Postgres) is set.

## Deploy (Vercel + Neon, both free)

1. Create a free Postgres database at https://neon.tech and copy its connection string.
2. Import this repo at https://vercel.com/new.
3. In the Vercel project settings, add an environment variable
   `DATABASE_URL` = the Neon connection string, and `ADMIN_KEY` = a secret
   only the host knows (required to create boards), then deploy.

`vercel.json` routes every request to the FastAPI app in `api/index.py`.
