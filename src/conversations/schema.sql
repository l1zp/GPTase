-- Main conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    model_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    agent_id TEXT,
    status TEXT NOT NULL,
    total_duration_seconds REAL,
    estimated_cost_usd REAL,
    error_message TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversations_model ON conversations(model_name);
CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversations(agent_id);

-- Messages table (input/output pairs)
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_sequence ON messages(conversation_id, sequence_number);

-- Responses table (LLM outputs with metadata)
CREATE TABLE IF NOT EXISTS responses (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    content TEXT NOT NULL,
    reasoning_content TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_seconds REAL,
    metadata TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_responses_conversation ON responses(conversation_id);

-- Streaming chunks table (for real-time replay)
CREATE TABLE IF NOT EXISTS stream_chunks (
    id TEXT PRIMARY KEY,
    response_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT,
    reasoning_content TEXT,
    is_thinking INTEGER NOT NULL,
    is_complete INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_response ON stream_chunks(response_id, chunk_index);

-- Model parameters table
CREATE TABLE IF NOT EXISTS model_parameters (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    temperature REAL,
    max_tokens INTEGER,
    top_p REAL,
    enable_thinking INTEGER,
    system_prompt TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Extraction sessions table (groups related conversations into workflows)
CREATE TABLE IF NOT EXISTS extraction_sessions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    document_path TEXT NOT NULL,
    extraction_type TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    total_llm_calls INTEGER DEFAULT 0,
    phase TEXT,
    metadata TEXT,
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON extraction_sessions(timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_document ON extraction_sessions(document_path);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON extraction_sessions(status);

-- Session steps table (tracks individual workflow phases)
CREATE TABLE IF NOT EXISTS extraction_session_steps (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_phase TEXT NOT NULL,
    conversation_id TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    step_order INTEGER NOT NULL,
    metadata TEXT,
    FOREIGN KEY (session_id) REFERENCES extraction_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_steps_session ON extraction_session_steps(session_id);
CREATE INDEX IF NOT EXISTS idx_steps_conversation ON extraction_session_steps(conversation_id);

-- Extracted results table (stores final extraction outputs)
CREATE TABLE IF NOT EXISTS extraction_results (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    result_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES extraction_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_results_session ON extraction_results(session_id);
