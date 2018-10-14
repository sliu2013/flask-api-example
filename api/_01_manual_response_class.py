import json
from flask import Flask, Response, abort, request
from .utils import JSON_MIME_TYPE, search_book

from wavefront_python_sdk import WavefrontDirectClient, WavefrontProxyClient
from wavefront_opentracing_python_sdk import WavefrontTracer
from wavefront_opentracing_python_sdk.reporting import CompositeReporter, \
    WavefrontSpanReporter, ConsoleReporter
from opentracing.propagation import Format

# Report opentracing spans to Wavefront via a Wavefront Direct Ingestion.
direct_client = WavefrontDirectClient(
    server="<wavefront-server>",
    token="<token>"
)
direct_reporter = WavefrontSpanReporter(
    client=direct_client,
    source="wavefront-sky-direct"
)
# Create Wavefront Span Reporter using Wavefront Proxy Client.
proxy_client = WavefrontProxyClient(
    host="localhost",
    tracing_port=30000,
    distribution_port=40000,
    metrics_port=2878
)
proxy_reporter = WavefrontSpanReporter(proxy_client,
                                       source='wavefront-sky-proxy')
composite_reporter = CompositeReporter(direct_reporter, proxy_reporter,
                                       ConsoleReporter('wavefront-sky'))
tracer = WavefrontTracer(reporter=composite_reporter)

app = Flask(__name__)

books = [{
    'id': 33,
    'title': 'The Raven',
    'author_id': 1
}]


@app.route('/book')
def book_list():
    span = before_request(request, tracer, 'book_list')
    with tracer.scope_manager.activate(span, True) as scope:
        response = Response(
            json.dumps(books), status=200, mimetype=JSON_MIME_TYPE)
        return response


def before_request(request1, tracer1, operation_name):
    span_context = tracer1.extract(
        format=Format.HTTP_HEADERS,
        carrier=dict(request1.headers)
    )
    span = tracer1.start_span(
        operation_name=operation_name,
        child_of=span_context)
    span.set_tag('http.url', request1.base_url)
    span.set_tag('service', 'flask_api_server')
    return span


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = search_book(books, book_id)
    if book is None:
        abort(404)

    content = json.dumps(book)
    return content, 200, {'Content-Type': JSON_MIME_TYPE}


@app.errorhandler(404)
def not_found(e):
    return '', 404


