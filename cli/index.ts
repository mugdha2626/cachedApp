const command = process.argv[2]

switch (command) {
  case "register": {
    const { register } = await import("./src/register")
    await register()
    break
  }
  case "balance": {
    const { balance } = await import("./src/balance")
    await balance()
    break
  }
  case undefined: {
    const { createCliRenderer, Box, Text } = await import("@opentui/core")
    const { loadWallet } = await import("./src/config")

    const wallet = await loadWallet()
    const renderer = await createCliRenderer({ exitOnCtrlC: true })

    renderer.root.add(
      Box(
        { borderStyle: "rounded", padding: 1, flexDirection: "column", gap: 1 },
        Text({ content: "cachedApp CLI", fg: "#00FF00" }),
        Text({
          content: wallet
            ? `Seller wallet: ${wallet.address} (Base Sepolia)`
            : "Not registered as a seller yet.",
          fg: wallet ? "#FFFFFF" : "#FFFF00",
        }),
        Text({ content: "Commands:  register — create seller wallet (CDP)" }),
        Text({ content: "           balance  — show USDC balance" }),
        Text({ content: "Press Ctrl+C to exit", fg: "#888888" }),
      ),
    )
    break
  }
  default: {
    console.error(`Unknown command: ${command}`)
    console.error("Usage: bun index.ts [register | balance]")
    process.exit(1)
  }
}
