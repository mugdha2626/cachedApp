import { loadWallet, saveWallet, WALLET_PATH } from "./config"

const REQUIRED_ENV = ["CDP_API_KEY_ID", "CDP_API_KEY_SECRET", "CDP_WALLET_SECRET"]
const ACCOUNT_NAME = "x402-seller"

export async function register() {
  const missing = REQUIRED_ENV.filter((key) => !process.env[key])
  if (missing.length > 0) {
    console.error("Missing environment variables:\n")
    for (const key of missing) console.error(`  ${key}`)
    console.error(
      "\nGet them from https://portal.cdp.coinbase.com — create an API key" +
        " (CDP_API_KEY_ID / CDP_API_KEY_SECRET) and a Wallet Secret" +
        " (CDP_WALLET_SECRET), then put them in cli/.env (see .env.example).",
    )
    process.exit(1)
  }

  const existing = await loadWallet()
  if (existing) {
    console.log(`Already registered as a seller.`)
    console.log(`  Address: ${existing.address}`)
    console.log(`  Network: ${existing.network}`)
    return
  }

  console.log("Registering seller wallet via CDP…")
  const { CdpClient } = await import("@coinbase/cdp-sdk")
  const cdp = new CdpClient()

  const account = await cdp.evm.getOrCreateAccount({ name: ACCOUNT_NAME })

  await saveWallet({
    name: ACCOUNT_NAME,
    address: account.address,
    network: "eip155:84532", // Base Sepolia (CAIP-2)
    createdAt: new Date().toISOString(),
  })

  console.log(`\nSeller registered!`)
  console.log(`  Address: ${account.address}`)
  console.log(`  Network: Base Sepolia (eip155:84532)`)
  console.log(`  Saved:   ${WALLET_PATH}`)

  try {
    console.log("\nRequesting testnet USDC from the CDP faucet…")
    const faucet = await cdp.evm.requestFaucet({
      address: account.address,
      network: "base-sepolia",
      token: "usdc",
    })
    console.log(`  Faucet tx: ${faucet.transactionHash}`)
    console.log("  Run `bun index.ts balance` in a minute to see it land.")
  } catch (err) {
    console.log(`  Faucet request failed (non-fatal): ${err instanceof Error ? err.message : err}`)
    console.log("  You can fund the address manually at https://portal.cdp.coinbase.com/products/faucet")
  }
}
