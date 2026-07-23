# Paper

Turn a designed letterhead PDF into a usable Word template.

Drop in a brand page. Paper rasterizes the artwork, finds a safe typing band, and packages it as `.docx` / `.dotx` — letterhead art stays faithful, body stays empty and editable.

**Live:** [paper-web-production.up.railway.app](https://paper-web-production.up.railway.app) · custom domain `paper.tentacore.xyz` pending DNS (see [DEPLOY.md](DEPLOY.md))


A side project by [Tentacore](https://tentacore.xyz).

## Develop

```bash
# Terminal 1 — Python worker
cd worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8787

# Terminal 2 — web app
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Build

```bash
npm run build
npm run preview
```

## Hosting note

Production frontend is intended for **Vercel** (`paper.tentacore.xyz`), with the Python worker on **Railway** (`api.paper.tentacore.xyz`).

If Vercel CLI auth isn’t available locally, the repo also includes a root `Dockerfile` so the static app can be served from Railway as a temporary alternative. Prefer Vercel for parity with Squeeze once logged in.

