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
    const { home } = await import("./src/home")
    await home()
    break
  }
  default: {
    console.error(`Unknown command: ${command}`)
    console.error("Usage: bun index.ts [register | balance]")
    process.exit(1)
  }
}
