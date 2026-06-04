New session connects
       │
       ▼
Load context:
  - Factual memory (permanent facts, preferences)
  - Temporal memory (time-based events, non-expired)
  - Last session summary (until end of week)
  - Weekly summaries (last 4 weeks)
  - Auto-inject session opener
       │
       ▼
  Live conversation
  (keep adding current context in full until a limit (x tokens))
       │
       ├─ [On-demand] topic match → pull older episodic memory (semantic, time-based search)
       ▼
  Session ends (clean close)
       │
       ├─ Summarize session → store episodic
       ├─ Extract facts → deduplicate → update long term memory
       ├─ Extract temporal facts → store with expiry
       │
  [Nightly job]
       ├─ Daily summary (merge sessions from that day if last session of the day is completed/closed) [check every 1 hr]
       ├─ Weekly rollup (if week boundary crossed)
       └─ Deduplication pass on long term memory