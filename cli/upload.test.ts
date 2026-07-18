// Verifies the CLI upload code (loadFile + ingest + pollUntilActive) against a
// stand-in that mirrors the real backend contract (backend/app/main.py):
//   POST /ingest (multipart: file, original_prompt, seller_id) -> { session_id }
//   GET  /sessions/{id}/status -> { status: pending | active }

import { test, expect, beforeAll, afterAll } from "bun:test"
import { writeFile, mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { loadFile, ingest, pollUntilActive } from "./src/upload"

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
        const prompt = form?.get("original_prompt")
        const seller = form?.get("seller_id")
        if (!(file instanceof File) || !prompt || !seller) {
          return Response.json({ detail: "missing fields" }, { status: 400 })
        }
        const id = "sess_" + Math.random().toString(36).slice(2, 8)
        started.set(id, Date.now())
        return Response.json({ session_id: id })
      }
      const m = pathname.match(/^\/sessions\/([^/]+)\/status$/)
      if (req.method === "GET" && m) {
        const t0 = started.get(m[1]!)
        if (t0 === undefined) return Response.json({ detail: "not found" }, { status: 404 })
        const status = Date.now() - t0 >= ACTIVE_AFTER_MS ? "active" : "pending"
        return Response.json({ status })
      }
      return Response.json({ detail: "not found" }, { status: 404 })
    },
  })
  baseUrl = `http://localhost:${server.port}`
})

afterAll(() => server.stop(true))

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

    const sessionId = await ingest(file, "GLP-1 CV outcomes", "0xseller", baseUrl)
    expect(sessionId).toMatch(/^sess_/)

    // resolves once the stand-in flips to active
    await pollUntilActive(sessionId, baseUrl, 25, 40)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test("ingest surfaces backend errors", async () => {
  const empty = { name: "x.txt", title: "x", bytes: new Uint8Array(), type: "text/plain", size: 0 }
  // seller_id present but the stand-in requires all fields; force a 400 by omitting prompt
  const form = { ...empty }
  // call with empty prompt/seller to trigger 400
  await expect(ingest(form as any, "", "", baseUrl)).rejects.toThrow()
})
