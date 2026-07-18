// Deterministic seller id.
//
// The Data Core /ingest contract (plan/byeori_plan.md + backend schemas) types
// `seller_id` as a UUID, but the seller only has a wallet address (register
// returns no id). Until register hands back a canonical seller UUID, we derive a
// stable UUIDv5 from the wallet address so the same wallet always maps to the
// same seller id and the value is a valid UUID the backend can accept.

import { createHash } from "node:crypto"

// Fixed CacheApp namespace (an arbitrary constant UUID).
const NAMESPACE = "b9d5a4e2-1f3c-4d8a-9c2b-7a6e5f4d3c2b"

function parseUuid(uuid: string): Uint8Array {
  const hex = uuid.replace(/-/g, "")
  const bytes = new Uint8Array(16)
  for (let i = 0; i < 16; i++) bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16)
  return bytes
}

function formatUuid(b: Uint8Array): string {
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("")
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

/** RFC 4122 UUIDv5 (SHA-1, name-based). */
export function uuidv5(name: string, namespace: string = NAMESPACE): string {
  const ns = parseUuid(namespace)
  const nameBytes = new TextEncoder().encode(name)
  const data = new Uint8Array(ns.length + nameBytes.length)
  data.set(ns)
  data.set(nameBytes, ns.length)

  const digest = createHash("sha1").update(Buffer.from(data)).digest()
  const bytes = Uint8Array.from(digest.subarray(0, 16))
  bytes[6] = (bytes[6]! & 0x0f) | 0x50 // version 5
  bytes[8] = (bytes[8]! & 0x3f) | 0x80 // RFC 4122 variant
  return formatUuid(bytes)
}

/** Stable seller UUID for a wallet address. */
export function sellerIdFor(address: string): string {
  return uuidv5(address.toLowerCase())
}
