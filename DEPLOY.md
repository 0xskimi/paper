# Deploy notes

## Live now

| Piece | URL |
|---|---|
| GitHub | https://github.com/0xskimi/paper |
| Frontend (Railway) | https://paper-web-production.up.railway.app |
| Worker (Railway) | https://paper-api-production-8e2c.up.railway.app |
| Side shelf | pushed on tentacore-website (`Add Paper to Side shelf`) |

Custom domains are registered on Railway and waiting on Cloudflare DNS:

- Frontend: `https://paper.tentacore.xyz`
- API: `https://api.paper.tentacore.xyz`

## Cloudflare DNS (tentacore.xyz)

Add these records (DNS only / grey cloud is fine for CNAME):

### Frontend → Railway `paper-web`

| Type | Name | Content |
|---|---|---|
| CNAME | `paper` | `6c1puzei.up.railway.app` |
| TXT | `_railway-verify.paper` | `railway-verify=6d92f7f0c666c41803743ea86771c9c9fba7fd48326eb8afffaa3c4c62b607fa` |

### API → Railway `paper-api`

| Type | Name | Content |
|---|---|---|
| CNAME | `api.paper` | `u8reqczp.up.railway.app` |
| TXT | `_railway-verify.api.paper` | `railway-verify=6041f9d5114a29aae79eca69e8faef4882130494675a24f236f06f2d80258f87` |

After DNS propagates, both custom domains should serve HTTPS automatically via Railway.

## Frontend env

The production image bakes in:

```text
VITE_API_BASE=https://api.paper.tentacore.xyz
```

Until `api.paper` DNS is live, the Railway frontend URL still expects that API host. You can redeploy with:

```bash
cd /Users/muawiya/playground/paper
railway up --service paper-web --detach
```

after changing the Dockerfile `ARG VITE_API_BASE` to the temporary `https://paper-api-production-8e2c.up.railway.app` if needed for testing.

## Optional: move frontend to Vercel (Squeeze parity)

```bash
vercel login
vercel link --yes --project paper
vercel env add VITE_API_BASE production   # https://api.paper.tentacore.xyz
vercel --prod
vercel domains add paper.tentacore.xyz
```

Then point the `paper` CNAME to `cname.vercel-dns.com` instead of Railway.
