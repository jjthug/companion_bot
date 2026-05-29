postgres db
==========
users:
id
email
oauth: google, facebook
info: jsonb (preferences, facts, medicines)
created_at
updated_at


episodic_memory:
id
user_id
context (summarized)
vector
date:


short term: for current session context
id
user_id
context




redis:
======
short term for user:
auth token:



during update to current session context, we update only in redis and a worker will periodically update the db with a separate worker


memory decay strategy

present day, current session: daily context full store
present day previous sessions: session summary
2-7 days: daily summary
8-90: weekly summary
90+ : monthly summary


conversation session context:

current session full context +
same day previous sessions context + 
2-7 days daily summary

100k token per hour