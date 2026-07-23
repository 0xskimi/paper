# Paper

Turn a designed letterhead PDF into a usable Word template.

Drop in a brand page. Paper rasterizes the artwork, finds a safe typing band, and packages it as `.docx` / `.dotx` — letterhead art stays faithful, body stays empty and editable.

**Live:** [paper.tentacore.xyz](https://paper.tentacore.xyz)

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

## Note

This repo is public for portfolio purposes. All rights reserved — not licensed for reuse or redistribution.
