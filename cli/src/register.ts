import { loadWallet, saveWallet, WALLET_PATH } from "./config"

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000"

interface RegisterResponse {
  name: string
  address: string
  network: string
  faucet_tx: string | null
}

export async function register() {
  const existing = await loadWallet()
  if (existing) {
    console.log("Already registered as a seller.")
    console.log(`  Address: ${existing.address}`)
    console.log(`  Network: ${existing.network}`)
    return
  }

  console.log(`Registering seller via backend (${BACKEND_URL})…`)

  let res: Response
  try {
    res = await fetch(`${BACKEND_URL}/register`, { method: "POST" })
  } catch {
    console.error(`Could not reach the backend at ${BACKEND_URL}.`)
    console.error("Start it with: cd backend && uv run uvicorn app.main:app")
    process.exit(1)
  }

  if (!res.ok) {
    const detail = await res
      .json()
      .then((body: any) => body?.detail)
      .catch(() => null)
    console.error(`Registration failed (${res.status}): ${detail ?? res.statusText}`)
    process.exit(1)
  }

  const wallet = (await res.json()) as RegisterResponse

  await saveWallet({
    name: wallet.name,
    address: wallet.address,
    network: wallet.network,
    createdAt: new Date().toISOString(),
  })

  console.log("\nSeller registered!")
  console.log(`  Address: ${wallet.address}`)
  console.log(`  Network: Base Sepolia (${wallet.network})`)
  console.log(`  Saved:   ${WALLET_PATH}`)

  if (wallet.faucet_tx) {
    console.log(`  Faucet tx: ${wallet.faucet_tx}`)
    console.log("  Run `bun index.ts balance` in a minute to see the USDC land.")
  } else {
    console.log("  Faucet request did not complete — fund the address at")
    console.log("  https://portal.cdp.coinbase.com/products/faucet if needed.")
  }
}
