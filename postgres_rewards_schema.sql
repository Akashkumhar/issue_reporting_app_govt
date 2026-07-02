-- PostgreSQL schema updates for RoadSense rewards + FASTag redemption
-- This file is a deliverable for PostgreSQL environments.

-- 1) Users table updates
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS wallet_balance INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS reputation_score INTEGER NOT NULL DEFAULT 0;

-- 2) Coin transactions audit trail
CREATE TABLE IF NOT EXISTS coin_transactions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  coins_delta INTEGER NOT NULL,
  event_type VARCHAR(50) NOT NULL,
  ref_type VARCHAR(50),
  ref_id BIGINT,
  details TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coin_transactions_user_time
  ON coin_transactions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coin_transactions_event
  ON coin_transactions(event_type, created_at DESC);

-- 3) FASTag redemptions (withdrawal requests)
CREATE TABLE IF NOT EXISTS fastag_redemptions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  vehicle_number VARCHAR(50) NOT NULL,
  amount_rupees INTEGER NOT NULL,
  coins_spent INTEGER NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  transaction_ref VARCHAR(100) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fastag_redemptions_status
  ON fastag_redemptions(status, created_at DESC);

-- Optional: if you want updated_at to auto-update, use a trigger in PostgreSQL.
