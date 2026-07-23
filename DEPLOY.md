# Deploy notes

## Live pieces already up

| Piece | URL |
|---|---|
| GitHub | https://github.com/0xskimi/paper |
| Worker (Railway) | https://paper-api-production-8e2c.up.railway.app |
| Custom API domain (pending DNS) | https://api.paper.tentacore.xyz |
| Side shelf | pushed to tentacore-website |

## Cloudflare DNS (tentacore.xyz)

Add these records (same pattern as Squeeze → Vercel):

### API (Railway)

| Type | Name | Content |
|---|---|---|
| CNAME | `api.paper` | `u8reqczp.up.railway.app` |
| TXT | `_railway-verify.api.paper` | `railway-verify=6041f9d5114a29aae79eca69e8faef4882130494675a24f236f06f2d80258f87` |

### Frontend (Vercel)

After linking the GitHub repo in Vercel and adding the domain:

| Type | Name | Content |
|---|---|---|
| CNAME | `paper` | `cname.vercel-dns.com` |

## Vercel frontend

```bash
cd /Users/muawiya/playground/paper
vercel login   # complete device auth in browser
vercel link --yes --project paper
vercel env add VITE_API_BASE production   # value: https://api.paper.tentacore.xyz
vercel --prod
vercel domains add paper.tentacore.xyz
```

Or import https://github.com/0xskimi/paper in the Vercel dashboard, set env `VITE_API_BASE=https://api.paper.tentacore.xyz`, add domain `paper.tentacore.xyz`.
