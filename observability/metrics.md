The points that matter most:

Custom histogram buckets are the big one. The SDK's default explicit-bucket boundaries top out and are spaced for general use; for a voice pipeline where you care about the difference between 150ms and 400ms time-to-first-token, the default buckets will be too coarse and your p50/p95/p99 will be near-useless. The View with explicit boundaries tuned to your latency range is what makes these histograms actually answer "what's my p95 time-to-first-token." Adjust the bucket list to your real targets — for first-token you might want finer granularity in the 100–800ms range.
insecure, resource, and shutdown — same as tracing. Don't hardcode insecure=True; attach the same Resource (otherwise metrics won't carry service name/version and won't join with your traces in the backend); and call provider.shutdown() in lifespan teardown so the final 30s window of metrics flushes on exit. PeriodicExportingMetricReader also supports force_flush() if you want to push before shutdown.
unit and description are not cosmetic. Backends (Cloud Monitoring, Prometheus via the collector) use the unit for axis labels and sometimes for aggregation correctness. Use UCUM-style annotations: ms, s, and {thing} for dimensionless counts. Naming a metric *_ms while declaring unit="ms" keeps it unambiguous.

Two design cautions specific to your set:

quota.seconds_used_daily as a histogram is questionable. A histogram records a distribution of independent measurements. "Seconds used daily per user" sounds like a per-user running total — if you record the cumulative value repeatedly you'll get a distorted distribution. If you want "distribution across users of how much quota they used today," record one value per user per day at reset time. If you want "is a given user near their limit," that's not a metric at all (too high cardinality for per-user) — it's application state you check against the DB. Decide which question you're answering.
Cardinality on attributes, not instrument count. Your instruments are fine. The risk is what attributes you attach when recording. Tagging error_counter with error.type (a bounded set like stt_timeout, llm_error, quota) is good. Tagging anything with user_id or session_id as a metric attribute will blow up your time-series count and cost — those identifiers belong in traces/logs (which you've already wired), never as metric labels. Keep metric attributes low-cardinality: model name, stage, error type, status.

Recording examples so the buckets/attributes are concrete:
pythonturn_counter.add(1, {"model": model_name, "status": "ok"})
llm_first_token.record(ttft_ms, {"model": model_name})
error_counter.add(1, {"error.type": "stt_timeout", "stage": "stt"})
ws_connections.add(1)      # on connect
ws_connections.add(-1)     # on disconnect (in your finally block)
That ws_connections pair maps directly onto the WS handler from before — increment after accept(), decrement in the finally. Same with active_sessions if a session is distinct from a connection.
Want me to fold metrics setup and shutdown into the consolidated startup module with the rest?