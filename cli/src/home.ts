import { Select, SelectRenderableEvents, type KeyEvent, type SelectOption } from "@opentui/core"
import { balanceView } from "./balance"
import { loadWallet } from "./config"
import { registerView } from "./register"
import { openScreen, row, blank, hint, theme, t, bold, fg, Text, type Screen } from "./ui"

type MenuChoice = "register" | "balance" | "quit"

async function showMenu(screen: Screen): Promise<MenuChoice> {
  const wallet = await loadWallet()

  const menu = Select({
    height: 6,
    options: [
      { name: "Register", description: "create seller wallet (CDP)", value: "register" },
      { name: "Balance", description: "show USDC balance", value: "balance" },
      { name: "Quit", description: "exit the CLI", value: "quit" },
    ],
    backgroundColor: "transparent",
    focusedBackgroundColor: "transparent",
    textColor: theme.text,
    focusedTextColor: theme.text,
    selectedBackgroundColor: "#313244",
    selectedTextColor: theme.accent,
    descriptionColor: theme.muted,
    selectedDescriptionColor: theme.muted,
    wrapSelection: true,
  })

  return new Promise((resolve) => {
    const onKey = (key: KeyEvent) => {
      if (key.name === "q" || key.name === "escape") done("quit")
    }
    const done = (choice: MenuChoice) => {
      screen.renderer.keyInput.off("keypress", onKey)
      resolve(choice)
    }

    // Construct proxies only replay calls queued before instantiation, so the
    // event handler and focus() must be registered before show() mounts the menu.
    menu.on(SelectRenderableEvents.ITEM_SELECTED, (_index: number, option: SelectOption) => {
      done(option.value as MenuChoice)
    })
    menu.focus()

    screen.show(
      { title: "cachedApp", borderColor: theme.accent },
      Text({ content: t`${bold(fg(theme.accent)("cachedApp CLI"))}` }),
      blank(),
      wallet
        ? row("Wallet", wallet.address, fg(theme.muted)("(Base Sepolia)"))
        : Text({ content: t`${fg(theme.warn)("●")} ${fg(theme.text)("Not registered as a seller yet.")}` }),
      blank(),
      menu,
      blank(),
      hint("↑/↓ move · enter select · q quit"),
    )
    screen.renderer.keyInput.on("keypress", onKey)
  })
}

export async function home() {
  const screen = await openScreen()

  while (true) {
    const choice = await showMenu(screen)
    if (choice === "quit") break
    if (choice === "register") await registerView(screen, false)
    else await balanceView(screen, false)
  }

  screen.close()
}
