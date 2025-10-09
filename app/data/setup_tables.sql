-- Create user_progress table
CREATE TABLE user_progress (
    id SERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    domain TEXT,
    answered_questions INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    language_code TEXT,
);

-- Create user_responses table
CREATE TABLE user_responses (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    validation TEXT,
    score INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- Add audio message handling to user_responses
ALTER TABLE user_responses ADD COLUMN IF NOT EXISTS message_type TEXT DEFAULT 'text';
ALTER TABLE user_responses ADD COLUMN IF NOT EXISTS audio_file_path TEXT;
ALTER TABLE user_responses ADD COLUMN IF NOT EXISTS transcription TEXT;
ALTER TABLE user_responses ADD COLUMN IF NOT EXISTS transcription_confidence FLOAT;

-- Create audio_files table for metadata
CREATE TABLE audio_files (
    id SERIAL PRIMARY KEY,
    whatsapp_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    file_id TEXT NOT NULL, -- WhatsApp media ID
    file_path TEXT, -- Local storage path
    file_size INTEGER,
    mime_type TEXT,
    duration_seconds INTEGER,
    transcription TEXT,
    transcription_confidence FLOAT,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX idx_audio_files_whatsapp_id ON audio_files(whatsapp_id);
CREATE INDEX idx_audio_files_user_id ON audio_files(user_id);

-- Create user_chat_sessions table to map WhatsApp users to Gloo AI chat sessions
CREATE TABLE user_chat_sessions (
    id SERIAL PRIMARY KEY,
    whatsapp_id TEXT UNIQUE NOT NULL,
    gloo_chat_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
-- Create index for faster lookups
CREATE INDEX idx_user_chat_sessions_whatsapp_id ON user_chat_sessions(whatsapp_id);

-- Create questions table
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    domain TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS question_type TEXT DEFAULT 'flex';
INSERT INTO questions (id, domain, text) VALUES 
(1, 'kinship', 'What do you call your father''s brother?'),
(2, 'kinship', 'How do you address your mother''s sister?'),
(3, 'kinship', 'What term do you use for your grandparent''s sibling?');
