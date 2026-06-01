from __future__ import annotations
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation
from opentelemetry.sdk.resources import Resource, SERVICE_NAME


# latency buckets tuned for sub-second voice pipeline stages (ms)
_LATENCY_BUCKETS = [10, 25, 50, 75, 100, 150, 200, 300, 400, 500,
                    750, 1000, 1500, 2000, 3000, 5000, 10000]


def setup_metrics(
    service_name: str,
    otlp_endpoint: str,
    *,
    insecure: bool = False,
) -> MeterProvider:
    resource = Resource.create({SERVICE_NAME: service_name})
    exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=insecure)
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=30_000)

    # apply latency buckets to all *_ms histograms
    latency_view = View(
        instrument_name="companion.*latency*",
        aggregation=ExplicitBucketHistogramAggregation(_LATENCY_BUCKETS),
    )
    ms_view = View(
        instrument_name="companion.*_ms",
        aggregation=ExplicitBucketHistogramAggregation(_LATENCY_BUCKETS),
    )

    provider = MeterProvider(
        resource=resource,
        metric_readers=[reader],
        views=[latency_view, ms_view],
    )
    metrics.set_meter_provider(provider)
    return provider


meter = metrics.get_meter("companion.backend")

active_sessions = meter.create_up_down_counter(
    "companion.sessions.active", unit="{session}",
    description="Currently active chat sessions")
turn_counter = meter.create_counter(
    "companion.turns.total", unit="{turn}",
    description="Total conversation turns processed")
stt_latency = meter.create_histogram(
    "companion.stt.latency_ms", unit="ms",
    description="Speech-to-text transcription latency")
llm_first_token = meter.create_histogram(
    "companion.llm.first_token_ms", unit="ms",
    description="LLM time to first token")
tts_first_chunk = meter.create_histogram(
    "companion.tts.first_chunk_ms", unit="ms",
    description="TTS time to first audio chunk")
turn_e2e_latency = meter.create_histogram(
    "companion.turn.e2e_latency_ms", unit="ms",
    description="End-to-end turn latency, user speech end to first audio out")
quota_seconds_used = meter.create_histogram(
    "companion.quota.seconds_used_daily", unit="s",
    description="Daily quota seconds consumed per user")
quota_exceeded_counter = meter.create_counter(
    "companion.quota.exceeded_total", unit="{event}",
    description="Quota-exceeded rejections")
error_counter = meter.create_counter(
    "companion.errors.total", unit="{error}",
    description="Total errors by type")
ws_connections = meter.create_up_down_counter(
    "companion.websocket.connections", unit="{connection}",
    description="Open WebSocket connections")