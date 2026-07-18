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
      { title: "Seller Registration", borderColor: theme.warn },
      Text({ content: t`${fg(theme.warn)("●")} ${bold(fg(theme.text)("Already registered as a seller"))}` }),
      blank(),
      row("Address", existing.address),
      row("Network", "Base Sepolia", fg(theme.muted)(`(${existing.network})`)),
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
      "Seller Registration",
      `Registering via backend (${BACKEND_URL})…`,
      fetch(`${BACKEND_URL}/register`, { method: "POST" }),
    )
  } catch {
    await showError(
      screen,
      "Seller Registration",
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
      "Seller Registration",
      standalone,
      Text({ content: `Registration failed (${res.status})`, fg: theme.error }),
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

  const faucetLines = wallet.faucet_tx
    ? [
        row("Faucet tx", wallet.faucet_tx),
        blank(),
        Text({
          content: t`Check ${fg(theme.accent)("balance")} in a minute to see the USDC land.`,
          fg: theme.text,
        }),
      ]
    : [
        Text({ content: "Faucet request did not complete — fund the address at", fg: theme.warn }),
        Text({ content: "https://portal.cdp.coinbase.com/products/faucet", fg: theme.accent }),
      ]

  screen.show(
    { title: "Seller Registration", borderColor: theme.success },
    Text({ content: t`${fg(theme.success)("✓")} ${bold(fg(theme.text)("Seller registered"))}` }),
    blank(),
    row("Address", wallet.address),
    row("Network", "Base Sepolia", fg(theme.muted)(`(${wallet.network})`)),
    row("Saved", WALLET_PATH),
    blank(),
    ...faucetLines,
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
