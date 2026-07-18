import { join } from "path"

export const WALLET_PATH = join(import.meta.dir, "..", "wallet.json")

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
  if (!(await file.exists())) return null
  return (await file.json()) as WalletConfig
}

export async function saveWallet(config: WalletConfig): Promise<void> {
  await Bun.write(WALLET_PATH, JSON.stringify(config, null, 2) + "\n")
}
