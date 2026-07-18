// Verifies the CLI upload code (loadFile + ingest + pollUntilActive + seller id)
// against a stand-in that mirrors the real Data Core contract (backend/app/
// api/data_core.py + schemas.py, per plan/byeori_plan.md):
//   POST /ingest  (multipart: seller_id: UUID, original_prompt, file) -> { session_id: UUID }  [202]
//   GET  /sessions/{id}/status -> { session_id, status: pending | active }

import { test, expect, beforeAll, afterAll } from "bun:test"
import { writeFile, mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { randomUUID } from "node:crypto"
import { loadFile, ingest, pollUntilActive } from "./src/upload"
import { sellerIdFor, uuidv5 } from "./src/uuid"

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const ACTIVE_AFTER_MS = 120
const started = new Map<string, number>()

let server: ReturnType<typeof Bun.serve>
let baseUrl: string

beforeAll(() => {
  server = Bun.serve({
    port: 0,
    async fetch(req) {
      const { pathname } = new URL(req.url)
      if (req.method === "POST" && pathname === "/ingest") {
        const form = await req.formData().catch(() => null)
        const file = form?.get("file")
        const prompt = ((form?.get("original_prompt") as string | null) ?? "").trim()
        const seller = (form?.get("seller_id") as string | null) ?? ""
        if (!(file instanceof File) || !prompt) return Response.json({ detail: "missing" }, { status: 422 })
        if (!UUID_RE.test(seller)) return Response.json({ detail: "seller_id must be UUID" }, { status: 422 })
        const id = randomUUID()
        started.set(id, Date.now())
        return Response.json({ session_id: id }, { status: 202 })
      }
      const m = pathname.match(/^\/sessions\/([^/]+)\/status$/)
      if (req.method === "GET" && m) {
        const t0 = started.get(m[1]!)
        if (t0 === undefined) return Response.json({ detail: "not found" }, { status: 404 })
        const status = Date.now() - t0 >= ACTIVE_AFTER_MS ? "active" : "pending"
        return Response.json({ session_id: m[1], status })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    },
  })
  baseUrl = `http://localhost:${server.port}`
})

afterAll(() => server.stop(true))

test("sellerIdFor produces a stable, valid UUIDv5", () => {
  const a = sellerIdFor("0xAbC123")
  expect(a).toMatch(UUID_RE)
  expect(a[14]).toBe("5") // version 5
  expect(sellerIdFor("0xabc123")).toBe(a) // case-insensitive + deterministic
  expect(uuidv5("other")).not.toBe(a)
})

test("loadFile accepts .md and rejects unsupported types", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cacheapp-up-"))
  try {
    const md = join(dir, "report.md")
    await writeFile(md, "# findings\nsome deep research")
    const f = await loadFile(md)
    expect(f.name).toBe("report.md")
    expect(f.type).toBe("text/markdown")
    expect(f.bytes.length).toBeGreaterThan(0)

    const bad = join(dir, "note.docx")
    await writeFile(bad, "x")
    await expect(loadFile(bad)).rejects.toThrow(/Unsupported file type/)
    await expect(loadFile(join(dir, "missing.pdf"))).rejects.toThrow(/not found/i)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test("ingest + pollUntilActive complete the upload flow", async () => {
  const dir = await mkdtemp(join(tmpdir(), "cacheapp-up-"))
  try {
    const path = join(dir, "glp1.txt")
    await writeFile(path, "cardiovascular outcomes research")
    const file = await loadFile(path)

    const sessionId = await ingest(file, "GLP-1 CV outcomes", sellerIdFor("0xseller"), baseUrl)
    expect(sessionId).toMatch(UUID_RE)

    await pollUntilActive(sessionId, baseUrl, 25, 40)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test("ingest rejects a non-UUID seller_id (contract enforcement)", async () => {
  const file = { name: "x.txt", title: "x", bytes: new TextEncoder().encode("hi"), type: "text/plain", size: 2 }
  await expect(ingest(file, "prompt", "0xnot-a-uuid", baseUrl)).rejects.toThrow()
})
