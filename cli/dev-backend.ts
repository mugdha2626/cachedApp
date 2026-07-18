// Offline dev stand-in for the CacheApp backend — runs on Bun, no deps, no network.
// Implements the same HTTP contract as backend/app/main.py so the CLI works
// end-to-end when PyPI/uv aren't reachable. NOT for production; /register returns
// a fake wallet (no real CDP). Swap back to the real backend once uv/pip work.
//
//   bun dev-backend.ts          # http://localhost:8000

const PORT = Number(process.env.PORT ?? 8000);
const INGEST_MS = Number(process.env.DEV_INGEST_MS ?? 3000); // pending -> active

const sessions = new Map<string, { startedAt: number; prompt: string }>();

const rid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`;
const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });

const ALLOWED = [".pdf", ".txt", ".md"];

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const { pathname } = new URL(req.url);

    if (req.method === "GET" && pathname === "/health") return json({ status: "ok" });

    // Fake CDP wallet (offline). Real backend talks to Coinbase CDP.
    if (req.method === "POST" && pathname === "/register") {
      const address =
        "0x" + Array.from({ length: 40 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
      return json({ name: "x402-seller", address, network: "eip155:84532", faucet_tx: null });
    }

    if (req.method === "POST" && pathname === "/ingest") {
      const form = await req.formData().catch(() => null);
      const file = form?.get("file");
      const prompt = (form?.get("original_prompt") as string | null) ?? "";
      const seller = form?.get("seller_id");
      if (!(file instanceof File)) return json({ detail: "no file" }, 400);
      if (!prompt) return json({ detail: "original_prompt required" }, 400);
      if (!seller) return json({ detail: "seller_id required" }, 400);
      if (file.size === 0) return json({ detail: "empty file" }, 400);
      const ext = (file.name.match(/\.[^.]+$/)?.[0] ?? "").toLowerCase();
      if (!ALLOWED.includes(ext)) return json({ detail: `unsupported type ${ext}` }, 400);

      const id = rid("sess");
      sessions.set(id, { startedAt: Date.now(), prompt });
      console.log(`[ingest] ${file.name} (${file.size}b) seller=${seller} -> ${id}`);
      return json({ session_id: id });
    }

    const m = pathname.match(/^\/sessions\/([^/]+)\/status$/);
    if (req.method === "GET" && m) {
      const s = sessions.get(m[1]!);
      if (!s) return json({ detail: "not found" }, 404);
      const status = Date.now() - s.startedAt >= INGEST_MS ? "active" : "pending";
      return json({ status, title: s.prompt });
    }

    return json({ detail: "not found" }, 404);
  },
});

console.log(`CacheApp DEV backend (offline stand-in) on http://localhost:${server.port}`);
