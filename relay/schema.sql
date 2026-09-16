PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('member','admin')),
 enabled INTEGER NOT NULL DEFAULT 1, max_running INTEGER NOT NULL DEFAULT 2,
 daily_limit INTEGER NOT NULL DEFAULT 100, last_dispatch INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pairing_codes (
 code_hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), expires_at REAL NOT NULL,
 used_at REAL
);
CREATE TABLE IF NOT EXISTS nodes (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL,
 token_hash TEXT NOT NULL UNIQUE, gpu_uuid TEXT NOT NULL UNIQUE, gpu_name TEXT NOT NULL,
 memory_mb INTEGER NOT NULL, capabilities TEXT NOT NULL DEFAULT '{}', environment TEXT NOT NULL DEFAULT '{}',
 sharing INTEGER NOT NULL DEFAULT 0, local_enabled INTEGER NOT NULL DEFAULT 0,
 revoked INTEGER NOT NULL DEFAULT 0, schedule_start TEXT, schedule_end TEXT,
 utc_offset_minutes INTEGER NOT NULL DEFAULT 480, telemetry TEXT NOT NULL DEFAULT '{}',
 last_seen REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('asr','upscale')), is_demo INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id), user_id TEXT NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL, profile TEXT NOT NULL, filename TEXT NOT NULL, input_key TEXT NOT NULL,
 input_bytes INTEGER NOT NULL, params TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','loading','running','retrying','completed','failed','cancelled')),
 attempt_count INTEGER NOT NULL DEFAULT 0, active_attempt_id TEXT, stage TEXT NOT NULL DEFAULT '等待可用設備',
 progress REAL, error TEXT, created_at REAL NOT NULL, completed_at REAL
);
CREATE TABLE IF NOT EXISTS attempts (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), node_id TEXT NOT NULL REFERENCES nodes(id),
 started_at REAL NOT NULL, lease_until REAL NOT NULL, ended_at REAL, outcome TEXT, error TEXT,
 gpu_verified INTEGER NOT NULL DEFAULT 0, metrics TEXT NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_attempt_per_node ON attempts(node_id) WHERE ended_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS one_active_attempt_per_job ON attempts(job_id) WHERE ended_at IS NULL;
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), name TEXT NOT NULL,
 storage_key TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, node_owner_id TEXT, job_id TEXT, node_id TEXT,
 kind TEXT NOT NULL, message TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 key TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, window_start REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status,user_id,created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_batch ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id,created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_lease ON attempts(ended_at,lease_until);
CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_events_visibility ON events(user_id,id);
PRAGMA user_version = 1;
