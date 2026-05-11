import os
import logging
import time
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.core.config import settings

logger = logging.getLogger(__name__)

class ResilientOTelConfig:
    def __init__(self):
        self.primary_endpoint = settings.OTEL_ENDPOINT
        self.service_name = "formulary-agent-fastapi"
        self.service_version = "2.0.0"

    def setup_telemetry(self, app):
        try:
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": self.service_version,
                "service.instance.id": f"{self.service_name}-{int(time.time())}",
                "deployment.environment": os.getenv("ENVIRONMENT", "production")
            })

            # Setup Tracing
            trace_provider = TracerProvider(resource=resource)
            
            # 1. Always add Console exporter in non-production for visibility and as a fallback
            if os.getenv("ENVIRONMENT") != "production":
                trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            
            # 2. Add OTLP exporter if configured
            try:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=f"{self.primary_endpoint}/v1/traces",
                    timeout=5, # Reduced timeout for faster failure
                    headers={"Content-Type": "application/x-protobuf"}
                )
                trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"📡 OTLP Trace exporter configured for: {self.primary_endpoint}")
            except Exception as e:
                logger.warning(f"⚠️ OTLP exporter initialization failed: {e}")
                if os.getenv("ENVIRONMENT") == "production":
                    # In production, if OTLP fails and we don't have console, add console as absolute fallback
                    trace_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

            trace.set_tracer_provider(trace_provider)

            # Instrument FastAPI
            FastAPIInstrumentor.instrument_app(app)
            
            logger.info("✅ OpenTelemetry configured for FastAPI successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to configure OpenTelemetry: {str(e)}")
            return False

def init_telemetry(app):
    if settings.OTEL_SDK_DISABLED:
        return False
    config = ResilientOTelConfig()
    return config.setup_telemetry(app)
