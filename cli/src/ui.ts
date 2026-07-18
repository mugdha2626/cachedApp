import {
  createCliRenderer,
  Box,
  Text,
  TextRenderable,
  t,
  bold,
  dim,
  fg,
  type CliRenderer,
  type KeyEvent,
  type VChild,
  type StylableInput,
} from "@opentui/core"

export const theme = {
  accent: "#8BD5CA",
  text: "#E6E6E6",
  muted: "#6C7086",
  success: "#A6E3A1",
  warn: "#F9E2AF",
  error: "#F38BA8",
  border: "#45475A",
}

export interface Screen {
  renderer: CliRenderer
  /** Replace the screen contents with a centered bordered panel. */
  show(opts: { title: string; borderColor?: string }, ...children: VChild[]): void
  /**
   * Resolve with the key name once one of `keys` is pressed; any key when
   * `keys` is omitted (Ctrl+C is handled by the renderer).
   */
  waitForKey(keys?: string[]): Promise<string>
  close(): void
}

export const EXIT_KEYS = ["q", "escape", "return"]

export async function openScreen(): Promise<Screen> {
  const renderer = await createCliRenderer({ exitOnCtrlC: true, useMouse: false })

  return {
    renderer,
    show({ title, borderColor }, ...children) {
      for (const child of renderer.root.getChildren()) {
        renderer.root.remove(child)
        child.destroyRecursively()
      }
      renderer.root.add(
        Box(
          { width: "100%", height: "100%", justifyContent: "center", alignItems: "center" },
          Box(
            {
              borderStyle: "rounded",
              borderColor: borderColor ?? theme.border,
              title: ` ${title} `,
              titleAlignment: "left",
              flexDirection: "column",
              paddingTop: 1,
              paddingBottom: 1,
              paddingLeft: 2,
              paddingRight: 2,
              minWidth: 56,
            },
            ...children,
          ),
        ),
      )
    },
    waitForKey(keys) {
      return new Promise((resolve) => {
        const handler = (key: KeyEvent) => {
          if (!keys || keys.includes(key.name)) {
            renderer.keyInput.off("keypress", handler)
            resolve(key.name)
          }
        }
        renderer.keyInput.on("keypress", handler)
      })
    },
    close() {
      renderer.destroy()
    },
  }
}

/** A dim, aligned "label   value" row, with an optional extra trailing chunk. */
export function row(label: string, value: StylableInput, extra: StylableInput = "") {
  const main = typeof value === "string" ? fg(theme.text)(value) : value
  return Text({
    content: t`${dim(fg(theme.muted)(label.padEnd(10)))}${main}${extra ? " " : ""}${extra}`,
  })
}

export function blank() {
  return Text({ content: "" })
}

export function hint(content: string) {
  return Text({ content, fg: theme.muted })
}

const SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

/** Show a spinner panel while `work` runs; stops the spinner before returning. */
export async function withSpinner<T>(screen: Screen, title: string, message: string, work: Promise<T>): Promise<T> {
  // A real renderable (not a construct proxy) so content updates after mount apply.
  const spinnerText = new TextRenderable(screen.renderer, {
    content: t`${fg(theme.accent)(SPINNER_FRAMES[0]!)} ${fg(theme.text)(message)}`,
  })
  screen.show({ title }, spinnerText)

  let frame = 0
  const timer = setInterval(() => {
    frame = (frame + 1) % SPINNER_FRAMES.length
    spinnerText.content = t`${fg(theme.accent)(SPINNER_FRAMES[frame]!)} ${fg(theme.text)(message)}`
  }, 80)

  try {
    return await work
  } finally {
    clearInterval(timer)
  }
}

/**
 * Render an error panel and wait for a keypress. Standalone commands exit on
 * q/esc/enter; when embedded in the menu, any key returns to it.
 */
export async function showError(screen: Screen, title: string, standalone: boolean, ...children: VChild[]): Promise<void> {
  screen.show(
    { title, borderColor: theme.error },
    ...children,
    blank(),
    hint(standalone ? "press q to exit" : "press any key to return to the menu"),
  )
  await screen.waitForKey(standalone ? EXIT_KEYS : undefined)
}

export { t, bold, dim, fg, Box, Text }
