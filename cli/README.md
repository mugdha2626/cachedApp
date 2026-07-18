# cachedApp CLI

A basic terminal UI built with [OpenTUI](https://opentui.com) (`@opentui/core`) running on Bun.

To install dependencies:

```bash
bun install
```

The CLI holds no CDP credentials — registration goes through the backend
(`../backend`), which must be running for `register`. Optionally set
`BACKEND_URL` in `.env` (defaults to `http://localhost:8000`).

Commands:

```bash
bun run index.ts                        # TUI menu: Register / Upload / Balance
bun run index.ts register               # register seller via backend, store wallet address
bun run index.ts balance                # show the wallet's USDC balance (Base Sepolia)
bun run index.ts upload <path> [prompt] # upload a deep-research .pdf/.txt/.md to sell
```

`upload` sends the file + your original research prompt + wallet to the backend
Data Core contract (`POST /ingest`), then polls `GET /sessions/{id}/status` until
the session is `active`. Accepts `.pdf`, `.txt`, `.md`.

For local testing without the Python backend (or while the Data Core `/ingest`
is still a 501 stub), run the offline stand-in: `bun dev-backend.ts` in another
terminal — it implements the same routes on `http://localhost:8000`.

`register` saves the wallet address to `cli/wallet.json` (gitignored). The
wallet itself is managed by CDP on the backend — the CLI only stores the
address. `balance` queries the public Base Sepolia RPC directly.

This project was created using `bun init` in bun v1.1.33. [Bun](https://bun.sh) is a fast all-in-one JavaScript runtime.
