/**
 * CacheApp MCP server: exposes a research tool that buys the report from a
 * CacheApp seller over x402. When the agent calls the tool, we hit the paid
 * endpoint, sign the 402 payment requirements with a CDP-managed buyer
 * wallet (no raw private keys), and retry with the payment attached — the
 * seller's address in the requirements receives the USDC.
 */
import { createServer } from "node:http"
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js"
import { CdpClient } from "@coinbase/cdp-sdk"

const RESOURCE_SERVER_URL = process.env.RESOURCE_SERVER_URL ?? "http://localhost:8000"
const ENDPOINT_PATH = process.env.ENDPOINT_PATH ?? "/research"
const BUYER_ACCOUNT_NAME = process.env.BUYER_ACCOUNT_NAME ?? "cacheapp-buyer"

const cdp = new CdpClient()
const buyer = await cdp.evm.getOrCreateAccount({ name: BUYER_ACCOUNT_NAME })
// stdout is the MCP transport — all logging must go to stderr.
console.error(`CacheApp buyer wallet: ${buyer.address} (fund with USDC on Base Sepolia)`)

interface PaidResponse {
  status: number
  body: unknown
  settlement: unknown | null
}

/**
 * Fetch a resource, transparently paying if the server answers 402.
 * Works with both x402 v1 (JSON body + X-PAYMENT) and v2
 * (PAYMENT-REQUIRED / PAYMENT-SIGNATURE headers) servers.
 */
async function fetchWithPayment(url: string): Promise<PaidResponse> {
  const first = await fetch(url)
  if (first.status !== 402) {
    return { status: first.status, body: await first.json(), settlement: null }
  }

  const requiredHeader = first.headers.get("PAYMENT-REQUIRED")
  const paymentRequired = requiredHeader
    ? JSON.parse(Buffer.from(requiredHeader, "base64").toString())
    : await first.json()

  const payload = await buyer.signX402Payment(paymentRequired, 0)
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64")
  const headerName = payload.x402Version === 2 ? "PAYMENT-SIGNATURE" : "X-PAYMENT"

  const paid = await fetch(url, { headers: { [headerName]: encoded } })
  const settlementHeader = paid.headers.get("PAYMENT-RESPONSE") ?? paid.headers.get("X-PAYMENT-RESPONSE")
  return {
    status: paid.status,
    body: await paid.json(),
    settlement: settlementHeader ? JSON.parse(Buffer.from(settlementHeader, "base64").toString()) : null,
  }
}

function buildServer(): McpServer {
  const server = new McpServer({
    name: "CacheApp",
    version: "0.1.0",
  })

  server.tool(
    "fetch-research",
    "Buy a deep-research report from a CacheApp seller. Payment (USDC on Base Sepolia) " +
      "is handled automatically via x402 from the buyer's CDP wallet — no manual steps.",
    {},
    async () => {
      const result = await fetchWithPayment(`${RESOURCE_SERVER_URL}${ENDPOINT_PATH}`)
      if (result.status !== 200) {
        return {
          isError: true,
          content: [{ type: "text", text: `Purchase failed (HTTP ${result.status}): ${JSON.stringify(result.body)}` }],
        }
      }
      return {
        content: [{ type: "text", text: JSON.stringify({ ...(result.body as object), settlement: result.settlement }) }],
      }
    },
  )

  return server
}

if (process.env.MCP_TRANSPORT === "http") {
  // Remote mode for clients that only support Streamable HTTP connectors
  // (e.g. ChatGPT). Stateless: fresh server + transport per request.
  const port = Number(process.env.PORT ?? 3000)
  createServer(async (req, res) => {
    if (req.method !== "POST") {
      res.writeHead(405, { Allow: "POST" }).end()
      return
    }
    const chunks: Buffer[] = []
    for await (const chunk of req) chunks.push(chunk as Buffer)
    const body = JSON.parse(Buffer.concat(chunks).toString() || "{}")

    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined })
    res.on("close", () => transport.close())
    await buildServer().connect(transport)
    await transport.handleRequest(req, res, body)
  }).listen(port, () => {
    console.error(`CacheApp MCP server listening on http://localhost:${port}/mcp`)
  })
} else {
  await buildServer().connect(new StdioServerTransport())
}
