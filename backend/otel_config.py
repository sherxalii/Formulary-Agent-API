"""
Programmatic OpenTelemetry Configuration
Provides robust telemetry setup with retry mechanisms and fallback endpoints.
"""

import os
import logging
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
# HTTP instrumentors disabled to prevent external API call noise in telemetry
# from opentelemetry.instrumentation.requests import RequestsInstrumentor
# from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode
import time

logger = logging.getLogger(__name__)

class NoHeadSpanFilter:
    """Filter that excludes HEAD requests and GET requests to health endpoints, but allows other methods."""
    
    def __init__(self, exporter):
        self.exporter = exporter
    
    def export(self, spans):
        """Filter spans to exclude only HEAD requests and monitoring traffic."""
        filtered_spans = []
        health_paths = ["/health", "/ping", "/", "/formulary_agent/health", "/formulary_agent/ping"]
        for span in spans:
            http_method = None
            http_route = None
            http_target = None
            
            for key, value in span.attributes.items() if span.attributes else {}:
                if key == "http.method":
                    http_method = value
                elif key == "http.route":
                    http_route = value
                elif key == "http.target":
                    http_target = value
            
            # Determine the actual path being requested
            request_path = http_route or http_target or "unknown"
            
            logger.debug(f"TRACE DEBUG: method={http_method}, path={request_path}")
            
            # Check if span should be excluded
            should_exclude = False
            
            # Exclude spans marked for dropping
            if span.attributes and span.attributes.get('otel.drop'):
                should_exclude = True
                drop_reason = span.attributes.get('otel.dropped_reason', 'filtered')
                logger.debug(f"🚫 Filtered out span: {drop_reason}")
            
            # Fallback: Exclude ALL HEAD requests if not already marked
            elif http_method == "HEAD":
                should_exclude = True
                logger.debug(f"🚫 Filtered out HEAD request to {request_path}")
            
            # Fallback: Exclude GET requests to health endpoints if not already marked
            elif http_method == "GET" and request_path in health_paths:
                should_exclude = True
                logger.debug(f"🚫 Filtered out GET request to {request_path}")
            
            # Include all other methods (GET, POST, PUT, DELETE, etc.)
            if not should_exclude:
                filtered_spans.append(span)
                if http_method:
                    logger.debug(f"✅ Including {http_method} request to {request_path}")
        
        if filtered_spans:
            return self.exporter.export(filtered_spans)
        else:
            return SpanExportResult.SUCCESS
    
    def shutdown(self):
        """Shutdown the underlying exporter."""
        if hasattr(self.exporter, 'shutdown'):
            return self.exporter.shutdown()
    
    def force_flush(self, timeout_millis: int = 30000):
        """Force flush the underlying exporter."""
        if hasattr(self.exporter, 'force_flush'):
            return self.exporter.force_flush(timeout_millis)

class ResilientOTelConfig:
    """
    Resilient OpenTelemetry configuration with multiple endpoints and retry logic.
    """
    
    def __init__(self):
        self.primary_endpoint = "http://10.20.35.23/otel"  # Changed to /otel endpoint
        self.fallback_endpoints = [
            "http://10.20.35.23:4318",  # Direct collector as fallback
            "http://10.20.35.23:4317"   # gRPC as fallback
        ]
        self.service_name = "formulary-agent-api"
        self.service_version = "1.0.0"
        
    def setup_telemetry(self, app=None):
        """
        Set up OpenTelemetry with resilient configuration.
        
        Args:
            app: FastAPI application instance (optional)
        """
        try:
            # Create resource
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": self.service_version,
                "service.instance.id": f"{self.service_name}-{int(time.time())}",
                "deployment.environment": os.getenv("ENVIRONMENT", "production")
            })
            
            # Setup tracing
            self._setup_tracing(resource)
            
            # Setup metrics (commented out until /otel/v1/metrics endpoint is available)
            # self._setup_metrics(resource)
            
            # Instrument FastAPI and HTTP libraries
            self._setup_instrumentation(app)
            
            logger.info("✅ OpenTelemetry configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to configure OpenTelemetry: {str(e)}")
            # Fall back to console exporters for debugging
            self._setup_console_fallback(resource)
            return False
    
    def _setup_tracing(self, resource):
        """Setup trace provider with multiple exporters."""
        trace_provider = TracerProvider(resource=resource)
        
        # Primary OTLP exporter with HEAD request filter
        try:
            logger.info(f"🔗 Attempting to connect to: {self.primary_endpoint}/v1/traces")
            otlp_exporter = OTLPSpanExporter(
                endpoint=f"{self.primary_endpoint}/v1/traces",
                timeout=10,  # Reduced timeout
                headers={
                    "Content-Type": "application/x-protobuf"  # Back to protobuf
                },
                # Add additional configuration for better compatibility
                compression=None,  # Disable compression initially
            )
            
            # Wrap exporter with HEAD-filtering filter
            filtered_exporter = NoHeadSpanFilter(otlp_exporter)
            
            batch_processor = BatchSpanProcessor(
                filtered_exporter,
                max_export_batch_size=50,  # Smaller batch size
                export_timeout_millis=10000,  # Shorter timeout
                schedule_delay_millis=1000,  # More frequent exports
                max_queue_size=1000  # Limit queue size
            )
            trace_provider.add_span_processor(batch_processor)
            logger.info(f"📡 Trace exporter configured for: {self.primary_endpoint} (HEAD requests filtered out)")
            
        except Exception as e:
            logger.warning(f"⚠️ Primary trace exporter failed: {str(e)}")
            # Try HTTP/JSON fallback with POST filter
            try:
                logger.info("🔄 Trying HTTP/JSON fallback exporter...")
                fallback_exporter = OTLPSpanExporter(
                    endpoint=f"{self.primary_endpoint}/v1/traces",
                    timeout=10,
                    headers={
                        "Content-Type": "application/json"
                    },
                    compression=None
                )
                # Wrap fallback exporter with HEAD request filter
                filtered_fallback_exporter = NoHeadSpanFilter(fallback_exporter)
                
                fallback_processor = BatchSpanProcessor(
                    filtered_fallback_exporter,
                    max_export_batch_size=10,  # Very small batches
                    export_timeout_millis=5000,
                    schedule_delay_millis=2000
                )
                trace_provider.add_span_processor(fallback_processor)
                logger.info("✅ HTTP/JSON fallback exporter configured (HEAD requests filtered out)")
            except Exception as fallback_error:
                logger.warning(f"⚠️ Fallback exporter also failed: {str(fallback_error)}")
                # Add console exporter as final fallback
                console_processor = BatchSpanProcessor(ConsoleSpanExporter())
                trace_provider.add_span_processor(console_processor)
        
        trace.set_tracer_provider(trace_provider)
    
    def _setup_metrics(self, resource):
        """
        Setup metrics provider with OTLP exporter.
        
        🚀 TO ENABLE METRICS IN FUTURE:
        1. Uncomment the code block below
        2. Uncomment the self._setup_metrics(resource) call in setup_telemetry()
        3. Uncomment the metrics creation in api_server.py
        4. Verify that 10.20.35.23/otel/v1/metrics endpoint is available
        """
        # COMMENTED OUT: Uncomment when DevOps team sets up /otel/v1/metrics endpoint
        """
        try:
            # Since /otel/v1/metrics returns 404, try fallback endpoints for metrics
            otlp_metric_exporter = OTLPMetricExporter(
                endpoint=f"{self.primary_endpoint}/v1/metrics",  # Use primary endpoint for metrics
                timeout=30,
                headers={
                    "Content-Type": "application/json"
                }
            )
            
            metric_reader = PeriodicExportingMetricReader(
                exporter=otlp_metric_exporter,
                export_interval_millis=30000
            )
            
            metric_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            )
            metrics.set_meter_provider(metric_provider)
            logger.info(f"📊 Metrics exporter configured for: {self.primary_endpoint}")
            
        except Exception as e:
            logger.warning(f"⚠️ Metrics exporter failed: {str(e)}")
            # Fallback to console metrics
            console_reader = PeriodicExportingMetricReader(
                exporter=ConsoleMetricExporter(),
                export_interval_millis=60000
            )
            fallback_provider = MeterProvider(
                resource=resource,
                metric_readers=[console_reader]
            )
            metrics.set_meter_provider(fallback_provider)
        """
        logger.info("📊 Metrics collection disabled - uncomment _setup_metrics() to enable")
    
    def _setup_instrumentation(self, app=None):
        """Setup automatic instrumentation for FastAPI with request filtering."""
        try:
            # DISABLE HTTP libraries instrumentation to prevent RxNorm API calls from appearing in telemetry
            # RequestsInstrumentor().instrument()  # DISABLED - causes RxNorm API noise
            # URLLib3Instrumentor().instrument()   # DISABLED - causes external HTTP noise

            health_paths = ['/health', '/ping', '/', '/formulary_agent/health', '/formulary_agent/ping']

            # FastAPI/ASGI server_request_hook — runs when a span is created for a request
            def server_request_hook(span, scope):
                if span is None or not span.is_recording():
                    return
                try:
                    method = scope.get('method', '')
                    path = scope.get('path', '')
                    headers = dict(scope.get('headers', []))

                    logger.debug(f"TRACE DEBUG: method={method}, path={path}")

                    # Mark HEAD requests / health endpoints for filtering
                    if method == 'HEAD':
                        span.set_attribute('otel.drop', True)
                        span.set_attribute('otel.dropped_reason', 'HEAD request filtered')
                        return

                    if method == 'GET' and path in health_paths:
                        span.set_attribute('otel.drop', True)
                        span.set_attribute('otel.dropped_reason', f'GET {path} filtered')
                        return

                    # 1. Client IP
                    client_ip = (
                        headers.get(b'x-forwarded-for', b'').decode().split(',')[0].strip() or
                        headers.get(b'x-real-ip', b'').decode().strip() or
                        (scope.get('client') or ['unknown'])[0]
                    )
                    span.set_attribute('client.ip_address', str(client_ip))

                    # 2. User-Agent
                    user_agent = headers.get(b'user-agent', b'unknown').decode()
                    span.set_attribute('http.user_agent', user_agent)

                    # 3. Timestamp
                    span.set_attribute('request.timestamp', int(time.time()))

                    # 4. Business context
                    span.set_attribute('business.service', 'formulary_search')
                    if path == '/api/search':
                        span.set_attribute('business.operation', 'drug_search')

                    logger.debug(f"✅ Captured request data: IP={client_ip}, method={method}, path={path}")

                except Exception as e:
                    logger.warning(f"⚠️ Error in server_request_hook: {e}")

            # FastAPI/ASGI client_response_hook — runs when the response is sent
            def client_response_hook(span, scope, message):
                if span is None or not span.is_recording():
                    return
                try:
                    status_code = message.get('status', 0)
                    span.set_attribute('http.response.status_code', status_code)
                    span.set_attribute('response.success', status_code < 400)

                    # Capture response headers
                    for header_name, header_value in message.get('headers', []):
                        name = header_name.decode().lower()
                        if name in ['content-type', 'content-length']:
                            span.set_attribute(f'http.response.header.{name}', header_value.decode())

                    # Try to capture response data from thread-local storage
                    import threading
                    current_thread = threading.current_thread()
                    if hasattr(current_thread, 'otel_response_data'):
                        response_data = current_thread.otel_response_data
                        if isinstance(response_data, dict):
                            if 'alternatives' in response_data:
                                span.set_attribute('response.alternatives_count', len(response_data['alternatives']))
                            if 'response_time_ms' in response_data:
                                span.set_attribute('response.processing_time_ms', response_data['response_time_ms'])
                            if 'success' in response_data:
                                span.set_attribute('response.api_success', response_data['success'])
                            if 'rxnorm_validation' in response_data:
                                span.set_attribute('response.rxnorm_validated', response_data['rxnorm_validation'])
                            response_str = str(response_data)
                            span.set_attribute('response.payload', response_str[:1000] + ('...' if len(response_str) > 1000 else ''))
                        delattr(current_thread, 'otel_response_data')

                    span.set_attribute('trace.complete', True)
                    span.set_attribute('span.type', 'api_request_complete')

                except Exception as e:
                    logger.warning(f"⚠️ Error in client_response_hook: {e}")

            # Instrument FastAPI with comprehensive hooks
            if app:
                FastAPIInstrumentor.instrument_app(
                    app,
                    server_request_hook=server_request_hook,
                    client_response_hook=client_response_hook,
                )
                logger.info("🔧 FastAPI instrumentation enabled with comprehensive data capture")
                logger.info("📊 All mandatory data (IP, payload, response, user ID) captured in HTTP span")

            logger.info("🔧 Single-span tracing configured - cleaner traces with all data!")

        except Exception as e:
            logger.warning(f"⚠️ Instrumentation setup failed: {str(e)}")
            # Fallback to basic instrumentation without filtering
            if app:
                FastAPIInstrumentor.instrument_app(app)
                logger.info("🔧 Basic FastAPI instrumentation enabled (fallback mode)")
    
    def _setup_console_fallback(self, resource):
        """Setup console exporters as fallback when OTLP fails."""
        try:
            # Console trace exporter
            trace_provider = TracerProvider(resource=resource)
            console_processor = BatchSpanProcessor(ConsoleSpanExporter())
            trace_provider.add_span_processor(console_processor)
            trace.set_tracer_provider(trace_provider)
            
            # Console metrics exporter (commented out)
            # console_reader = PeriodicExportingMetricReader(
            #     exporter=ConsoleMetricExporter(),
            #     export_interval_millis=60000
            # )
            # metric_provider = MeterProvider(
            #     resource=resource,
            #     metric_readers=[console_reader]
            # )
            # metrics.set_meter_provider(metric_provider)
            
            logger.info("📝 Console exporters configured as fallback")
            
        except Exception as e:
            logger.error(f"❌ Even console fallback failed: {str(e)}")
    
    def create_custom_tracer(self, name: str):
        """
        Create a custom tracer for manual instrumentation.
        
        Args:
            name: Name of the tracer
            
        Returns:
            Tracer instance
        """
        return trace.get_tracer(name, schema_url="https://opentelemetry.io/schemas/1.21.0")
    
    def create_custom_meter(self, name: str):
        """
        Create a custom meter for manual metrics.
        
        Args:
            name: Name of the meter
            
        Returns:
            Meter instance
        """
        return metrics.get_meter(name)

# Global instance
otel_config = ResilientOTelConfig()

def init_telemetry(app=None):
    """
    Initialize telemetry configuration.
    
    Args:
        app: FastAPI application instance (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Check if telemetry is disabled via environment variable
    if os.getenv('OTEL_SDK_DISABLED', 'false').lower() in ('true', '1', 'yes'):
        print("📊 OpenTelemetry DISABLED via OTEL_SDK_DISABLED environment variable")
        return False  # Return False to indicate telemetry is disabled
    return otel_config.setup_telemetry(app)

def get_tracer(name: str):
    """Get a tracer for manual instrumentation."""
    return otel_config.create_custom_tracer(name)

def get_meter(name: str):
    """Get a meter for manual metrics."""
    return otel_config.create_custom_meter(name)