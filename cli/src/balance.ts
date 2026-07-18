import { BASE_SEPOLIA_RPC, BASE_SEPOLIA_USDC, loadWallet } from "./config"

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

export async function balance() {
  const wallet = await loadWallet()
  if (!wallet) {
    console.error("No seller wallet found. Run `bun index.ts register` first.")
    process.exit(1)
  }

  const atomic = await fetchUsdcBalance(wallet.address)
  const usdc = (Number(atomic) / 1e6).toFixed(6)

  console.log(`Seller wallet: ${wallet.address}`)
  console.log(`Network:       Base Sepolia (${wallet.network})`)
  console.log(`USDC balance:  ${usdc} USDC`)
}
