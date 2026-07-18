import { createCliRenderer, Box, Text } from "@opentui/core"

const renderer = await createCliRenderer({
  exitOnCtrlC: true,
})

renderer.root.add(
  Box(
    { borderStyle: "rounded", padding: 1, flexDirection: "column", gap: 1 },
    Text({ content: "cachedApp CLI", fg: "#00FF00" }),
    Text({ content: "Welcome! This is a basic OpenTUI app." }),
    Text({ content: "Press Ctrl+C to exit", fg: "#888888" }),
  ),
)
