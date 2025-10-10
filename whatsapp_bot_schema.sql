-- Core tables
-- Link to Supabase auth.users via UUID
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255),
    phone_whatsapp VARCHAR(20) UNIQUE, -- Optional: for WhatsApp users
    user_role VARCHAR(50) NOT NULL DEFAULT 'community_member', -- 'linguist', 'community_member', 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    permissions TEXT -- JSON blob of permissions
);

CREATE TABLE projects (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    ui_language VARCHAR(10) NOT NULL, -- ISO 639 code for interface language
    target_language VARCHAR(10) NOT NULL, -- ISO 639 code for language being documented
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link users to projects they're involved in
CREATE TABLE project_members (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'owner', 'linguist', 'contributor'
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, project_id)
);

-- Media file tracking (created early since many tables reference it)
CREATE TABLE media_files (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    file_url VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- 'audio', 'image', 'video'
    file_size BIGINT,
    mime_type VARCHAR(100),
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    transcription_status VARCHAR(50), -- 'pending', 'completed', 'failed'
    transcription_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Semantic domains (optional, project-specific)
CREATE TABLE domains (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    parent_domain_id BIGINT REFERENCES domains(id) ON DELETE SET NULL, -- for hierarchical domains
    description TEXT
);

-- Campaigns (focused elicitation rounds)
CREATE TABLE campaigns (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, -- "Verb morphology round 1", "Kinship terms"
    description TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Question templates and instances
CREATE TABLE question_templates (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    template_text TEXT NOT NULL, -- e.g., "What do you say when {situation}?"
    template_type VARCHAR(50) NOT NULL, -- 'situation', 'translation', 'minimal_pair', 'free_response'
    expected_response_type VARCHAR(50) NOT NULL, -- 'text', 'voice', 'either', 'both'
    follow_up_rules TEXT -- JSON: rules for when to ask follow-ups
    follow_up_prompt TEXT
);

CREATE TABLE questions (
    id BIGSERIAL PRIMARY KEY,
    input_text TEXT NOT NULL, -- actual question rendered from template
    input_language VARCHAR(10) NOT NULL, -- ISO 639 code
    output_language VARCHAR(10) NOT NULL, -- expected response language
    template_id BIGINT REFERENCES question_templates(id) ON DELETE SET NULL,
    domain_id BIGINT REFERENCES domains(id) ON DELETE SET NULL,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    media_prompt_id BIGINT REFERENCES media_files(id) ON DELETE SET NULL, -- optional image/audio prompt
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link questions to campaigns
CREATE TABLE campaign_questions (
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
    question_id BIGINT REFERENCES questions(id) ON DELETE CASCADE,
    sequence_order INTEGER, -- optional ordering for structured elicitation
    PRIMARY KEY (campaign_id, question_id)
);

-- Track which campaign each user is working on
CREATE TABLE user_campaigns (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
    current_question_index INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT false,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, campaign_id)
);

-- Session management
CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE SET NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active' -- 'active', 'paused', 'completed'
);

-- Response storage
CREATE TABLE responses (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES sessions(id) ON DELETE CASCADE,
    question_id BIGINT REFERENCES questions(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    response_type VARCHAR(50) NOT NULL, -- 'text', 'voice', 'image'
    response_text TEXT, -- for text responses
    media_file_id BIGINT REFERENCES media_files(id) ON DELETE SET NULL, -- for voice/image responses
    transcription TEXT, -- auto-transcription of voice if available
    quality_flag VARCHAR(50) DEFAULT 'unreviewed', -- 'unreviewed', 'good', 'needs_review', 'invalid'
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Follow-up questions (for exploring variations)
CREATE TABLE followup_questions (
    id BIGSERIAL PRIMARY KEY,
    parent_response_id BIGINT REFERENCES responses(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    context TEXT, -- what variation we're exploring (filled in by linguist later)
    asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE followup_responses (
    id BIGSERIAL PRIMARY KEY,
    followup_question_id BIGINT REFERENCES followup_questions(id) ON DELETE CASCADE,
    response_text TEXT,
    media_file_id BIGINT REFERENCES media_files(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Flexible tagging system for analysis
CREATE TABLE tags (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    tag_name VARCHAR(100) NOT NULL,
    tag_category VARCHAR(100), -- optional grouping like "grammar", "phonology", "domain"
    description TEXT
);

CREATE TABLE response_tags (
    response_id BIGINT REFERENCES responses(id) ON DELETE CASCADE,
    tag_id BIGINT REFERENCES tags(id) ON DELETE CASCADE,
    tagged_by UUID REFERENCES users(id) ON DELETE SET NULL,
    tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT, -- context for why this tag was applied
    PRIMARY KEY (response_id, tag_id)
);

-- Custom fields per project (linguist-defined)
CREATE TABLE project_fields (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    field_type VARCHAR(50) NOT NULL, -- 'text', 'select', 'multi_select', 'number'
    options TEXT, -- JSON array for select/multi_select
    applies_to VARCHAR(50) NOT NULL -- 'question', 'response', 'both'
);

CREATE TABLE response_field_values (
    id BIGSERIAL PRIMARY KEY,
    response_id BIGINT REFERENCES responses(id) ON DELETE CASCADE,
    field_id BIGINT REFERENCES project_fields(id) ON DELETE CASCADE,
    value TEXT
);

-- User progress tracking
CREATE TABLE user_progress (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
    questions_answered INTEGER DEFAULT 0,
    questions_total INTEGER,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation state management
CREATE TABLE conversation_states (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    current_question_id BIGINT REFERENCES questions(id) ON DELETE SET NULL,
    awaiting_response_type VARCHAR(50), -- 'answer', 'validation', 'follow_up'
    retry_count INTEGER DEFAULT 0,
    last_bot_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, project_id)
);

-- Bot configuration per project
CREATE TABLE bot_configs (
    project_id BIGINT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    greeting_message TEXT,
    max_retry_attempts INTEGER DEFAULT 3,
    follow_up_probability NUMERIC(3,2) DEFAULT 0.3, -- how often to ask follow-ups (0.00 to 1.00)
    voice_preferred BOOLEAN DEFAULT false,
    settings JSONB -- JSON for other config
);

-- Linguist sentences (for validation)
CREATE TABLE linguist_sentences (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    sentence_text TEXT NOT NULL,
    language VARCHAR(10) NOT NULL,
    context TEXT, -- explanation of what they're trying to say
    source VARCHAR(100), -- 'constructed', 'translated_from_gloss', etc.
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Community checking tables
CREATE TABLE validations (
    id BIGSERIAL PRIMARY KEY,
    validator_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    validation_type VARCHAR(50) NOT NULL, -- 'peer_check', 'linguist_check', 'naturalness'

    -- What's being validated (one of these will be populated)
    response_id BIGINT REFERENCES responses(id) ON DELETE CASCADE, -- checking another user's response
    linguist_sentence_id BIGINT REFERENCES linguist_sentences(id) ON DELETE CASCADE, -- checking linguist work

    -- Validation result
    is_valid BOOLEAN,
    confidence VARCHAR(50), -- 'certain', 'probably', 'unsure'
    comments TEXT,
    suggested_correction TEXT, -- if they think something is wrong

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- For Gloo API integration
CREATE TABLE ai_prompt_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES sessions(id) ON DELETE SET NULL,
    prompt_text TEXT NOT NULL,
    response_text TEXT,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Row Level Security (RLS) Policies
-- ============================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE domains ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE question_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE followup_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE response_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE response_field_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE linguist_sentences ENABLE ROW LEVEL SECURITY;
ALTER TABLE validations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_prompt_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to check if user is project member
CREATE OR REPLACE FUNCTION is_project_member(user_id_param UUID, project_id_param BIGINT)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM project_members
    WHERE user_id = user_id_param AND project_id = project_id_param
  );
$$ LANGUAGE SQL SECURITY DEFINER;

-- Helper function to check if user is admin
CREATE OR REPLACE FUNCTION is_admin(user_id_param UUID)
RETURNS BOOLEAN AS $$
  SELECT user_role = 'admin' FROM users WHERE id = user_id_param;
$$ LANGUAGE SQL SECURITY DEFINER;

-- Users: Can read own data, admins can read all
CREATE POLICY "Users can view own profile"
  ON users FOR SELECT
  USING (id = auth.uid());

CREATE POLICY "Admins can view all users"
  ON users FOR SELECT
  USING (is_admin(auth.uid()));

CREATE POLICY "Users can insert own profile"
  ON users FOR INSERT
  WITH CHECK (id = auth.uid());

CREATE POLICY "Users can update own profile"
  ON users FOR UPDATE
  USING (id = auth.uid());

-- Projects: Members can read, owners/linguists can update
CREATE POLICY "Project members can view projects"
  ON projects FOR SELECT
  USING (
    is_project_member(auth.uid(), id) OR is_admin(auth.uid())
  );

CREATE POLICY "Project owners can update projects"
  ON projects FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM project_members
      WHERE project_id = projects.id
      AND user_id = auth.uid()
      AND role IN ('owner', 'linguist')
    )
  );

CREATE POLICY "Users can create projects"
  ON projects FOR INSERT
  WITH CHECK (created_by = auth.uid());

-- Project Members: Can view if member, owners can manage
CREATE POLICY "Project members can view membership"
  ON project_members FOR SELECT
  USING (
    user_id = auth.uid() OR is_project_member(auth.uid(), project_id)
  );

CREATE POLICY "Project members can add members"
  ON project_members FOR INSERT
  WITH CHECK (
    -- Allow adding yourself if you're the project creator
    (user_id = auth.uid() AND EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_members.project_id
      AND p.created_by = auth.uid()
    ))
    OR
    -- Allow existing project owners/linguists to add others
    EXISTS (
      SELECT 1 FROM project_members pm
      WHERE pm.project_id = project_members.project_id
      AND pm.user_id = auth.uid()
      AND pm.role IN ('owner', 'linguist')
    )
  );

-- Responses: Users can create own, project members can read
CREATE POLICY "Users can create own responses"
  ON responses FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Project members can view responses"
  ON responses FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM sessions s
      JOIN projects p ON s.project_id = p.id
      WHERE s.id = responses.session_id
      AND is_project_member(auth.uid(), p.id)
    )
  );

CREATE POLICY "Users can view own responses"
  ON responses FOR SELECT
  USING (user_id = auth.uid());

-- Sessions: Users can manage own sessions
CREATE POLICY "Users can create own sessions"
  ON sessions FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can view own sessions"
  ON sessions FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can update own sessions"
  ON sessions FOR UPDATE
  USING (user_id = auth.uid());

-- Media Files: Project members can access
CREATE POLICY "Project members can view media"
  ON media_files FOR SELECT
  USING (is_project_member(auth.uid(), project_id));

CREATE POLICY "Project members can upload media"
  ON media_files FOR INSERT
  WITH CHECK (is_project_member(auth.uid(), project_id));

-- Conversation States: Users can manage own state
CREATE POLICY "Users can manage own conversation state"
  ON conversation_states FOR ALL
  USING (user_id = auth.uid());

-- Questions: Project members can view, owners/linguists can create
CREATE POLICY "Project members can view questions"
  ON questions FOR SELECT
  USING (is_project_member(auth.uid(), project_id));

CREATE POLICY "Project members can create questions"
  ON questions FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM project_members
      WHERE project_id = questions.project_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'linguist')
    )
  );

-- Campaign Questions: Project members can manage
CREATE POLICY "Project members can view campaign questions"
  ON campaign_questions FOR SELECT
  USING (
    EXISTS (1
      SELECT 1 FROM campaigns c
      JOIN project_members pm ON c.project_id = pm.project_id
      WHERE c.id = campaign_questions.campaign_id
      AND pm.user_id = auth.uid()
    )
  );

CREATE POLICY "Project members can add campaign questions"
  ON campaign_questions FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM campaigns c
      JOIN project_members pm ON c.project_id = pm.project_id
      WHERE c.id = campaign_questions.campaign_id
      AND pm.user_id = auth.uid()
      AND pm.role IN ('owner', 'linguist')
    )
  );

-- User Campaigns: Users can manage their own campaign progress
CREATE POLICY "Users can view user campaigns"
  ON user_campaigns FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can create user campaigns"
  ON user_campaigns FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update user campaigns"
  ON user_campaigns FOR UPDATE
  USING (user_id = auth.uid());

-- Campaigns: Project members can view, owners/linguists can create/update
CREATE POLICY "Project members can view campaigns"
  ON campaigns FOR SELECT
  USING (is_project_member(auth.uid(), project_id));

CREATE POLICY "Project members can create campaigns"
  ON campaigns FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM project_members
      WHERE project_id = campaigns.project_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'linguist')
    )
  );

CREATE POLICY "Project members can update campaigns"
  ON campaigns FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM project_members
      WHERE project_id = campaigns.project_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'linguist')
    )
  );

-- User Progress: Users can view own, project members can view all in project
CREATE POLICY "Users can view own progress"
  ON user_progress FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Project members can view project progress"
  ON user_progress FOR SELECT
  USING (is_project_member(auth.uid(), project_id));

CREATE POLICY "Users can create progress"
  ON user_progress FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update progress"
  ON user_progress FOR UPDATE
  USING (user_id = auth.uid());

-- Validations: Project members can create and view
CREATE POLICY "Project members can create validations"
  ON validations FOR INSERT
  WITH CHECK (validator_user_id = auth.uid());

CREATE POLICY "Project members can view validations"
  ON validations FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM responses r
      JOIN sessions s ON r.session_id = s.id
      WHERE r.id = validations.response_id
      AND is_project_member(auth.uid(), s.project_id)
    )
    OR EXISTS (
      SELECT 1 FROM linguist_sentences ls
      WHERE ls.id = validations.linguist_sentence_id
      AND is_project_member(auth.uid(), ls.project_id)
    )
  );
