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

CREATE INDEX idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX idx_conversations_model ON conversations(model_name);
CREATE INDEX idx_conversations_agent ON conversations(agent_id);

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

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_sequence ON messages(conversation_id, sequence_number);

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

CREATE INDEX idx_responses_conversation ON responses(conversation_id);

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

CREATE INDEX idx_chunks_response ON stream_chunks(response_id, chunk_index);

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
