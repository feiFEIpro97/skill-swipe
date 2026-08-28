-- D1 schema for SkillSwipe stats
-- 用法: wrangler d1 execute skillswipe --file=worker/schema.sql

CREATE TABLE IF NOT EXISTS swipes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  action TEXT NOT NULL,           -- like | skip
  ts INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skill ON swipes(skill_id);
CREATE INDEX IF NOT EXISTS idx_client ON swipes(client_id, ts);
