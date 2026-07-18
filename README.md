The backend exposes a **Data Core** contract for research ingestion, search,
paid-content redemption, feedback, and attribution. Two paths are implemented
today over Postgres/pgvector:

- **Ingestion** (`POST /ingest`, `GET /sessions/{id}/status`): upload →
  parse/normalize → split into pages (markdown headers, token-window fallback) →
  summarise each page (`gpt-4o-mini`) → rate freshness → embed
  (`text-embedding-3-small`; page = its summary, session = prompt + summaries) →
  persist → `status = active`. The pipeline runs in-process after the upload
  returns `202`; poll the status endpoint until `active`.
- **Search** (`POST /query`): preview-only cosine ranking over active sessions
  and their pages. Returns a confidence, a quoted price + transaction ID, and
  page previews (id, summary, citation) — never raw page text.
## Ingestion

```mermaid
flowchart TD
    A["Upload: file + original_prompt + seller_id"] --> B["Parse & normalize text"]
    B --> C["Split into pages (headers, fallback token window)"]
    C --> D["Summarize each page (cheap LLM, 1-3 sentences)"]
    D --> E["Rate freshness per page (latest date in content/citations)"]
    E --> F["Embed: session = prompt + summaries; page = its summary"]
    F --> G["status = active (searchable & payable)"]
```


## Retrieval & ranking

```mermaid
flowchart TD
    Q["Buyer query"] --> V["Vector search over page summaries (top ~30)"]
    V --> S["Group by session; score each session"]
    S --> T{"Best session score >= threshold?"}
    T -->|"No"| N["No confident match -> run deep research yourself"]
    T -->|"Yes"| P["Return match + price + previews + transaction_id (quoted)"]
    P --> X["x402 charges buyer"]
    X --> R["/redeem -> full pages + citations; write attributions"]
    R --> F["Async feedback -> relevance_ranking"]
    F -.-> V
```
