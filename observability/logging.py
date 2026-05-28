from __future__ import annotations

import logging

import structlog
# from opentelemetry import trace as otel_trace


# def add_otel_context(logger, method_name, event_dict):
#     span = otel_trace.get_current_span()
#     if span.is_recording():
#         ctx = span.get_span_context()
#         event_dict["trace_id"] = format(ctx.trace_id, "032x")
#         event_dict["span_id"] = format(ctx.span_id, "016x")
#         event_dict["trace_flags"] = int(ctx.trace_flags)
#     return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            # add_otel_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("companion.backend")
