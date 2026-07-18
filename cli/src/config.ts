import { homedir } from "os"
import { join } from "path"

export const WALLET_PATH = join(homedir(), ".cacheapp", "wallet.json")

// Pre-move location (inside the repo); migrated to WALLET_PATH on first load.
const LEGACY_WALLET_PATH = join(import.meta.dir, "..", "wallet.json")

export const BASE_SEPOLIA_RPC = "https://sepolia.base.org"
export const BASE_SEPOLIA_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

export interface WalletConfig {
  name: string
  address: string
  network: string
  createdAt: string
}

export async function loadWallet(): Promise<WalletConfig | null> {
  const file = Bun.file(WALLET_PATH)
  if (await file.exists()) return (await file.json()) as WalletConfig

  const legacy = Bun.file(LEGACY_WALLET_PATH)
  if (await legacy.exists()) {
    const config = (await legacy.json()) as WalletConfig
    await saveWallet(config)
    await legacy.delete()
    return config
  }

  return null
}

export async function saveWallet(config: WalletConfig): Promise<void> {
  await Bun.write(WALLET_PATH, JSON.stringify(config, null, 2) + "\n", { createPath: true })
}
