CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY,
    seller_id UUID NOT NULL,
    original_prompt TEXT NOT NULL,
    prompt_embedding vector(1536) NOT NULL,
    embedding_model_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'active')),
    price_base NUMERIC(12, 4) NOT NULL DEFAULT 0,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sessions_prompt_embedding_idx
    ON sessions USING hnsw (prompt_embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS pages (
    page_id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    citation TEXT,
    summary_embedding vector(1536) NOT NULL,
    embedding_model_version TEXT NOT NULL,
    relevance_ranking DOUBLE PRECISION NOT NULL DEFAULT 0,
    freshness DOUBLE PRECISION NOT NULL DEFAULT 0,
    UNIQUE (session_id, order_index)
);

CREATE INDEX IF NOT EXISTS pages_session_order_idx ON pages (session_id, order_index);
CREATE INDEX IF NOT EXISTS pages_summary_embedding_idx
    ON pages USING hnsw (summary_embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID PRIMARY KEY,
    buyer_id UUID NOT NULL,
    session_id UUID NOT NULL REFERENCES sessions(session_id),
    query_text TEXT NOT NULL,
    price_charged NUMERIC(12, 4) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('quoted', 'paid', 'served')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
