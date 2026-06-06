users:
=====
id
full name
email
passwordhash
oauth_provider
oauth_id
profile: jsonb
created_at
plan_id:
plan_cycle_day:


sessions:
========
id:
user_id:
context:
summarized_context:
start_datetime:
end_datetime:
is_active:


summaries:
=========
id
user_id
summary:
start_date
end_date
period_type: [session|daily|weekly]


plans:
=====
id:
slug:[free,starter,standard,heavy]
tier:
daily_cost_limit:
monthly_cost:


usage:
===========
id
user_id
start_date
end_date
cost
period: [daily|monthly]
quota_exceeded: bool

Unique constraints: (user_id, period, start_date)