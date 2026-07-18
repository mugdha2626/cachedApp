// Offline dev stand-in for the CacheApp backend — runs on Bun, no deps, no network.
// Mirrors the real contract (backend/app/api/data_core.py + schemas.py, per
// plan/byeori_plan.md) so the CLI works end-to-end when PyPI/uv aren't reachable
// or while the real Data Core /ingest is still a 501 stub.
//
//   bun dev-backend.ts          # http://localhost:8000
//
// NOT production. /register returns a fake wallet (no real CDP). The Data Core
// query/redeem/feedback/attribution routes are buyer/payment-side and unused by
// the seller CLI, so they are intentionally omitted here.

import { randomUUID } from "node:crypto"

const PORT = Number(process.env.PORT ?? 8000)
const INGEST_MS = Number(process.env.DEV_INGEST_MS ?? 3000) // pending -> active

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ALLOWED = [".pdf", ".txt", ".md"]

const sessions = new Map<string, { startedAt: number; prompt: string }>()

const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } })

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const { pathname } = new URL(req.url)

    if (req.method === "GET" && pathname === "/health") return json({ status: "ok" })

    // Fake CDP wallet (offline). Real backend talks to Coinbase CDP.
    if (req.method === "POST" && pathname === "/register") {
      const address =
        "0x" + Array.from({ length: 40 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("")
      return json({ name: "x402-seller", address, network: "eip155:84532", faucet_tx: null })
    }

    // POST /ingest -> IngestResponse { session_id: UUID }  (202)
    if (req.method === "POST" && pathname === "/ingest") {
      const form = await req.formData().catch(() => null)
      const file = form?.get("file")
      const prompt = ((form?.get("original_prompt") as string | null) ?? "").trim()
      const seller = (form?.get("seller_id") as string | null) ?? ""
      if (!(file instanceof File)) return json({ detail: "file required" }, 422)
      if (!prompt) return json({ detail: "original_prompt required" }, 422)
      if (!UUID_RE.test(seller)) return json({ detail: "seller_id must be a UUID" }, 422)
      if (file.size === 0) return json({ detail: "empty file" }, 400)
      const ext = (file.name.match(/\.[^.]+$/)?.[0] ?? "").toLowerCase()
      if (!ALLOWED.includes(ext)) return json({ detail: `unsupported type ${ext}` }, 400)

      const sessionId = randomUUID()
      sessions.set(sessionId, { startedAt: Date.now(), prompt })
      console.log(`[ingest] ${file.name} (${file.size}b) seller=${seller} -> ${sessionId}`)
      return json({ session_id: sessionId }, 202)
    }

    // GET /sessions/{id}/status -> SessionStatusResponse { session_id, status }
    const m = pathname.match(/^\/sessions\/([^/]+)\/status$/)
    if (req.method === "GET" && m) {
      const sessionId = m[1]!
      const s = sessions.get(sessionId)
      if (!s) return json({ detail: "not found" }, 404)
      const status = Date.now() - s.startedAt >= INGEST_MS ? "active" : "pending"
      return json({ session_id: sessionId, status })
    }

    return json({ detail: "not found" }, 404)
  },
})

console.log(`CacheApp DEV backend (offline stand-in) on http://localhost:${server.port}`)
