-- Create user_progress table
CREATE TABLE user_progress (
    id SERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    domain TEXT,
    answered_questions INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create user_responses table for Fieldworks analysis
CREATE TABLE user_responses (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    validation TEXT,
    score INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create questions table (optional, for better data management)
CREATE TABLE questions (
    id INTEGER PRIMARY KEY,
    domain TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO questions (id, domain, text) VALUES 
(1, 'kinship', 'What do you call your father''s brother?'),
(2, 'kinship', 'How do you address your mother''s sister?'),
(3, 'kinship', 'What term do you use for your grandparent''s sibling?');