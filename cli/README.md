# cachedApp CLI

A basic terminal UI built with [OpenTUI](https://opentui.com) (`@opentui/core`) running on Bun.

To install dependencies:

```bash
bun install
```

Set up CDP credentials (needed for `register`):

```bash
cp .env.example .env
# then fill in CDP_API_KEY_ID, CDP_API_KEY_SECRET, CDP_WALLET_SECRET
# from https://portal.cdp.coinbase.com
```

Commands:

```bash
bun run index.ts           # TUI: show seller status
bun run index.ts register  # create a CDP seller wallet (Base Sepolia) + faucet USDC
bun run index.ts balance   # show the wallet's USDC balance
```

`register` saves the wallet address to `cli/wallet.json` (gitignored). The wallet
itself is managed by CDP — no private keys are stored locally.

This project was created using `bun init` in bun v1.1.33. [Bun](https://bun.sh) is a fast all-in-one JavaScript runtime.
