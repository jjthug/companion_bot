WebSocket request timeout — the big one. Cloud Run has a per-request timeout that also applies to WebSocket connections (the whole connection counts as one streamed request). The default is 300s (5 min) and the maximum is 3600s (60 min). Your handler's 600s idle timeout is longer than the default 300s, so connections would get cut by Cloud Run at 5 minutes regardless of your app logic. Set the service timeout to the max:
bashgcloud run deploy companion-backend \
    --timeout 3600 \
    ...
And know the hard ceiling: no Cloud Run WebSocket can live past 60 minutes. Your client must handle reconnection. For a voice companion that's usually fine (sessions are short), but if you expect hour-plus continuous connections, Cloud Run will sever them at 60 min no matter what.


