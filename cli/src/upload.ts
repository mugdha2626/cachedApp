import { homedir } from "os"
import { extname, basename } from "path"
import { InputRenderable, type KeyEvent } from "@opentui/core"
import { loadWallet } from "./config"
import {
  openScreen,
  withSpinner,
  showError,
  row,
  blank,
  hint,
  theme,
  t,
  bold,
  fg,
  Text,
  EXIT_KEYS,
  type Screen,
} from "./ui"

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000"
const ALLOWED = [".pdf", ".txt", ".md"]
const MAX_BYTES = 25 * 1024 * 1024

interface LoadedFile {
  name: string
  title: string
  bytes: Uint8Array
  type: string
  size: number
}

const MIME: Record<string, string> = {
  ".pdf": "application/pdf",
  ".txt": "text/plain",
  ".md": "text/markdown",
}

function expandHome(p: string): string {
  if (p === "~") return homedir()
  if (p.startsWith("~/")) return homedir() + p.slice(1)
  return p
}

export async function loadFile(input: string): Promise<LoadedFile> {
  const path = expandHome(input.replace(/^["']|["']$/g, "").trim())
  const ext = extname(path).toLowerCase()
  if (!ALLOWED.includes(ext)) {
    throw new Error(`Unsupported file type "${ext || "(none)"}". Allowed: ${ALLOWED.join(", ")}.`)
  }
  const file = Bun.file(path)
  if (!(await file.exists())) throw new Error(`File not found: ${path}`)
  if (file.size === 0) throw new Error("File is empty.")
  if (file.size > MAX_BYTES) throw new Error(`File is too large (max 25 MB).`)
  const bytes = new Uint8Array(await file.arrayBuffer())
  const name = basename(path)
  return { name, title: name.replace(/\.[^.]+$/, ""), bytes, type: MIME[ext] ?? "application/octet-stream", size: file.size }
}

/** Prompt for a single line of text. Resolves to the value, or null on Esc. */
function promptInput(
  screen: Screen,
  opts: { title: string; label: string; placeholder: string; borderColor?: string },
): Promise<string | null> {
  const input = new InputRenderable(screen.renderer, {
    width: 52,
    placeholder: opts.placeholder,
    backgroundColor: "transparent",
    focusedBackgroundColor: "transparent",
    textColor: theme.text,
    placeholderColor: theme.muted,
  })
  input.focus()
  screen.show(
    { title: opts.title, borderColor: opts.borderColor ?? theme.accent },
    Text({ content: t`${fg(theme.muted)(opts.label)}` }),
    blank(),
    input,
    blank(),
    hint("enter submit · esc cancel"),
  )
  return new Promise((resolve) => {
    const handler = (key: KeyEvent) => {
      if (key.name === "return" || key.name === "enter") {
        cleanup()
        resolve(input.value.trim())
      } else if (key.name === "escape") {
        cleanup()
        resolve(null)
      }
    }
    const cleanup = () => screen.renderer.keyInput.off("keypress", handler)
    screen.renderer.keyInput.on("keypress", handler)
  })
}

export async function ingest(
  file: LoadedFile,
  prompt: string,
  sellerId: string,
  baseUrl: string = BACKEND_URL,
): Promise<string> {
  const form = new FormData()
  form.append("file", new Blob([file.bytes as unknown as BlobPart], { type: file.type }), file.name)
  form.append("original_prompt", prompt)
  form.append("seller_id", sellerId)

  const res = await fetch(`${baseUrl}/ingest`, { method: "POST", body: form })
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b: any) => b?.detail)
      .catch(() => null)
    throw new Error(String(detail ?? `${res.status} ${res.statusText}`))
  }
  const body = (await res.json()) as { session_id: string }
  return body.session_id
}

export async function pollUntilActive(
  sessionId: string,
  baseUrl: string = BACKEND_URL,
  intervalMs = 700,
  maxTries = 60,
): Promise<void> {
  for (let i = 0; i < maxTries; i++) {
    const res = await fetch(`${baseUrl}/sessions/${encodeURIComponent(sessionId)}/status`)
    if (!res.ok) throw new Error(`Status check failed: ${res.status}`)
    const body = (await res.json()) as { status: string }
    if (body.status === "active") return
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error("Timed out waiting for ingestion to finish.")
}

function clip(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…"
}

/**
 * Render the upload view into an existing screen. `presetPath`/`presetPrompt`
 * come from the argv command; in the menu they're collected interactively.
 */
export async function uploadView(
  screen: Screen,
  standalone: boolean,
  presetPath?: string,
  presetPrompt?: string,
): Promise<boolean> {
  const exitKeys = standalone ? EXIT_KEYS : undefined

  const wallet = await loadWallet()
  if (!wallet) {
    await showError(
      screen,
      "Upload Research",
      standalone,
      Text({ content: "No seller wallet found.", fg: theme.error }),
      blank(),
      Text({ content: t`Run ${fg(theme.accent)("register")} first.`, fg: theme.text }),
    )
    return false
  }

  // 1. file path — from argv, else prompt
  let path = presetPath?.trim()
  if (!path) {
    const entered = await promptInput(screen, {
      title: "Upload Research",
      label: "Upload your deep research — path to the PDF or TXT file",
      placeholder: "~/research/report.pdf",
    })
    if (entered === null || entered === "") return true // cancelled → back to menu
    path = entered
  }

  // 2. validate + read
  let file: LoadedFile
  try {
    file = await loadFile(path)
  } catch (err) {
    await showError(
      screen,
      "Upload Research",
      standalone,
      Text({ content: "Can't upload this file.", fg: theme.error }),
      blank(),
      Text({ content: String(err instanceof Error ? err.message : err), fg: theme.muted }),
    )
    return false
  }

  // 3. original research prompt — required (anchors the session embedding)
  let prompt = presetPrompt?.trim() || undefined
  while (!prompt) {
    const entered = await promptInput(screen, {
      title: "Upload Research",
      label: "What was your original prompt to the deep-research agent?",
      placeholder: "e.g. Compare GLP-1 drugs on cardiovascular outcomes",
    })
    if (entered === null) return true // cancelled → back to menu
    if (entered.trim() !== "") prompt = entered.trim()
    // empty → re-ask (this field is required)
  }

  // 4. dumb ingest + wait for async processing
  let sessionId: string
  try {
    sessionId = await withSpinner(
      screen,
      "Upload Research",
      `Uploading ${file.name}…`,
      ingest(file, prompt, wallet.address),
    )
  } catch (err) {
    await showError(
      screen,
      "Upload Research",
      standalone,
      Text({ content: "Upload failed.", fg: theme.error }),
      blank(),
      Text({ content: String(err instanceof Error ? err.message : err), fg: theme.muted }),
    )
    return false
  }

  try {
    await withSpinner(
      screen,
      "Upload Research",
      "Ingesting — parsing, summarizing, embedding…",
      pollUntilActive(sessionId),
    )
  } catch (err) {
    await showError(
      screen,
      "Upload Research",
      standalone,
      Text({ content: "Ingestion did not complete.", fg: theme.error }),
      blank(),
      Text({ content: String(err instanceof Error ? err.message : err), fg: theme.muted }),
      blank(),
      Text({ content: `Session ${sessionId} — check status later.`, fg: theme.muted }),
    )
    return false
  }

  // 5. success
  screen.show(
    { title: "Upload Research", borderColor: theme.success },
    Text({ content: t`${fg(theme.success)("✓")} ${bold(fg(theme.text)("Uploaded & indexed"))}` }),
    blank(),
    row("File", file.name),
    row("Prompt", clip(prompt, 44)),
    row("Session", sessionId),
    row("Status", "active", fg(theme.muted)("(searchable & payable)")),
    blank(),
    hint(standalone ? "press q to exit" : "press any key to return to the menu"),
  )
  await screen.waitForKey(exitKeys)
  return true
}

export async function upload() {
  const path = process.argv[3]
  const prompt = process.argv.slice(4).join(" ") || undefined
  const screen = await openScreen()
  const ok = await uploadView(screen, true, path, prompt)
  screen.close()
  if (!ok) process.exit(1)
}
