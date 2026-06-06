Redis key structure matters a lot here. Something like:

usage:user:{user_id}:daily:{YYYY-MM-DD} → { seconds_used, cost, sessions_count }
usage:user:{user_id}:monthly:{YYYY-MM} → { seconds_used, cost, quota_exceeded }

Keep daily and monthly as separate keys so your quota check on session start is just two GET calls.
On session start — what to pull
You said pull current day minutes and cost from DB into Redis. Also pull the monthly row at the same time — that's what you actually gate on. If the monthly key already exists in Redis (another session ran today), skip the DB pull and just read Redis. Add a TTL of ~25 hours on daily keys and ~35 days on monthly keys so stale data auto-expires.
Cost update every turn is fine, but be careful about race conditions. If a user somehow has two concurrent sessions (browser + mobile), two workers will be doing GET → modify → SET on the same Redis key. Use HINCRBY / HINCRBYFLOAT instead of read-modify-write — atomic increments on hash fields eliminate the race entirely.
HINCRBYFLOAT usage:user:{id}:daily:2026-06-05  cost      0.0023
HINCRBY      usage:user:{id}:daily:2026-06-05  seconds   12
HINCRBYFLOAT usage:user:{id}:monthly:2026-06   cost      0.0023
HINCRBY      usage:user:{id}:monthly:2026-06   seconds   12
Quota check on session start should read the monthly Redis key first, fall back to DB if missing, then write to Redis. Never skip the monthly check — a user could have used quota in a previous session earlier today whose Redis key has already been flushed.
The cron job — a few things to harden:

Use an upsert (INSERT ... ON CONFLICT (user_id, period, start_date) DO UPDATE) so the cron is idempotent and safe to re-run.
Run it more frequently than you think you need — every 1–2 minutes is fine. If the server crashes between cron runs you lose that window of usage data.
After writing to DB, don't delete the Redis key — let the TTL expire it naturally. Deleting it risks a cron running, deleting the key, and then a still-active session writing fresh increments that don't get picked up until the next cron cycle.
Log a last_synced_at timestamp per key (as a hash field) so you can detect keys that stopped updating — a sign a session crashed without closing cleanly.