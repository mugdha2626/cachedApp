import { loadWallet, saveWallet, WALLET_PATH } from "./config"
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

interface RegisterResponse {
  name: string
  address: string
  network: string
  faucet_tx: string | null
}

/** Render the registration view into an existing screen. Returns false on failure. */
export async function registerView(screen: Screen, standalone: boolean): Promise<boolean> {
  const exitHint = hint(standalone ? "press q to exit" : "press any key to return to the menu")
  const exitKeys = standalone ? EXIT_KEYS : undefined

  const existing = await loadWallet()
  if (existing) {
    screen.show(
      { title: "Become a Seller", borderColor: theme.warn },
      Text({ content: t`${fg(theme.warn)("●")} ${bold(fg(theme.text)("You're already a seller"))}` }),
      blank(),
      row("Wallet", existing.address),
      blank(),
      exitHint,
    )
    await screen.waitForKey(exitKeys)
    return true
  }

  let res: Response
  try {
    res = await withSpinner(
      screen,
      "Become a Seller",
      "Setting up your seller account…",
      fetch(`${BACKEND_URL}/register`, { method: "POST" }),
    )
  } catch {
    await showError(
      screen,
      "Become a Seller",
      standalone,
      Text({ content: t`Could not reach the backend at ${fg(theme.accent)(BACKEND_URL)}.`, fg: theme.error }),
      blank(),
      Text({ content: t`Start it with: ${fg(theme.accent)("cd backend && uv run uvicorn app.main:app")}`, fg: theme.text }),
    )
    return false
  }

  if (!res.ok) {
    const detail = await res
      .json()
      .then((body: any) => body?.detail)
      .catch(() => null)
    await showError(
      screen,
      "Become a Seller",
      standalone,
      Text({ content: `Sign-up failed (${res.status})`, fg: theme.error }),
      blank(),
      Text({ content: String(detail ?? res.statusText), fg: theme.muted }),
    )
    return false
  }

  const wallet = (await res.json()) as RegisterResponse

  await saveWallet({
    name: wallet.name,
    address: wallet.address,
    network: wallet.network,
    createdAt: new Date().toISOString(),
  })

  const fundingLines = wallet.faucet_tx
    ? [
        Text({
          content: t`Check ${fg(theme.accent)("Balance")} in a minute to see your starter funds land. ${fg(theme.success)("$$")}`,
          fg: theme.text,
        }),
      ]
    : [Text({ content: "Starter funds didn't come through yet — check back later.", fg: theme.warn })]

  screen.show(
    { title: "Become a Seller", borderColor: theme.success },
    Text({ content: t`${fg(theme.success)("✓")} ${bold(fg(theme.text)("You're a seller — time to make some $$"))}` }),
    blank(),
    row("Wallet", wallet.address),
    row("Saved", WALLET_PATH),
    blank(),
    ...fundingLines,
    blank(),
    exitHint,
  )

  await screen.waitForKey(exitKeys)
  return true
}

export async function register() {
  const screen = await openScreen()
  const ok = await registerView(screen, true)
  screen.close()
  if (!ok) process.exit(1)
}
