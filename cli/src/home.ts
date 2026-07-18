import { Select, SelectRenderableEvents, type KeyEvent, type SelectOption } from "@opentui/core"
import { balanceView } from "./balance"
import { loadWallet } from "./config"
import { registerView } from "./register"
import { uploadView } from "./upload"
import { openScreen, row, blank, hint, theme, t, bold, fg, Text, type Screen } from "./ui"

type MenuChoice = "register" | "upload" | "balance" | "quit"

async function showMenu(screen: Screen): Promise<MenuChoice> {
  const wallet = await loadWallet()

  const menu = Select({
    height: 8,
    options: [
      { name: "Become a Seller", description: "start making money on CacheApp", value: "register" },
      { name: "Upload Research", description: "sell a deep-research .pdf/.txt/.md", value: "upload" },
      { name: "Balance", description: "show your USD balance", value: "balance" },
      { name: "Quit", description: "exit CacheApp", value: "quit" },
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
      { title: "CacheApp", borderColor: theme.success },
      Text({ content: t`${bold(fg(theme.success)("$$ CacheApp $$"))} ${fg(theme.muted)("— make money from your deep research")}` }),
      blank(),
      wallet
        ? row("Wallet", wallet.address)
        : Text({ content: t`${fg(theme.warn)("●")} ${fg(theme.text)("You're not a seller yet.")}` }),
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
    else if (choice === "upload") await uploadView(screen, false)
    else await balanceView(screen, false)
  }

  screen.close()
}
