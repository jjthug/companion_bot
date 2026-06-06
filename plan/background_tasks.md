1. Cloud Tasks

2. Cloud Scheduler
===============
Batched Parallel + Cloud Tasks




Cloud Scheduler
      │
      ▼
   Producer
      │
      ▼
 Cloud Tasks
      │
      ▼
  Cloud Run Workers
      │
      ▼
 Database / APIs




- context management (session, daily, weekly summaries)
- user usage (cost)