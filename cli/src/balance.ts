import { BASE_SEPOLIA_RPC, BASE_SEPOLIA_USDC, loadWallet } from "./config"
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

async function fetchUsdcBalance(address: string): Promise<bigint> {
  // ERC-20 balanceOf(address) selector + 32-byte padded address
  const data = "0x70a08231" + address.slice(2).toLowerCase().padStart(64, "0")

  const res = await fetch(BASE_SEPOLIA_RPC, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "eth_call",
      params: [{ to: BASE_SEPOLIA_USDC, data }, "latest"],
    }),
  })
  if (!res.ok) throw new Error(`RPC request failed: ${res.status} ${res.statusText}`)

  const json = (await res.json()) as { result?: string; error?: { message: string } }
  if (json.error) throw new Error(`RPC error: ${json.error.message}`)
  return BigInt(json.result ?? "0x0")
}

/** Render the balance view into an existing screen. Returns false on failure. */
export async function balanceView(screen: Screen, standalone: boolean): Promise<boolean> {
  const wallet = await loadWallet()

  if (!wallet) {
    await showError(
      screen,
      "USDC Balance",
      standalone,
      Text({ content: "No seller wallet found.", fg: theme.error }),
      blank(),
      Text({ content: t`Run ${fg(theme.accent)("register")} first.`, fg: theme.text }),
    )
    return false
  }

  let atomic: bigint
  try {
    atomic = await withSpinner(screen, "USDC Balance", "Fetching balance on Base Sepolia…", fetchUsdcBalance(wallet.address))
  } catch (err) {
    await showError(
      screen,
      "USDC Balance",
      standalone,
      Text({ content: "Could not fetch balance.", fg: theme.error }),
      blank(),
      Text({ content: String(err instanceof Error ? err.message : err), fg: theme.muted }),
    )
    return false
  }

  const usdc = (Number(atomic) / 1e6).toFixed(6)

  screen.show(
    { title: "USDC Balance", borderColor: theme.accent },
    Text({ content: t`${bold(fg(theme.accent)(usdc))} ${fg(theme.muted)("USDC")}` }),
    blank(),
    row("Wallet", wallet.address),
    row("Network", "Base Sepolia", fg(theme.muted)(`(${wallet.network})`)),
    blank(),
    hint(standalone ? "press q to exit" : "press any key to return to the menu"),
  )

  await screen.waitForKey(standalone ? EXIT_KEYS : undefined)
  return true
}

export async function balance() {
  const screen = await openScreen()
  const ok = await balanceView(screen, true)
  screen.close()
  if (!ok) process.exit(1)
}
