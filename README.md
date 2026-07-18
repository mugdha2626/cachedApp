These are the diagrams of our data core: the part of CacheApp that turns an uploaded deep-research session into something **searchable and payable**, answers buyer queries with a real *"no confident match"* option, and records **who is owed what** on a served match.

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
