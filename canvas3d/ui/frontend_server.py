import http.server
import os
import socketserver
import threading

# Directory containing built front-end assets (static files)
RESOURCES_DIR = os.path.join(os.path.dirname(__file__), 'frontend')

class _FrontendRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=RESOURCES_DIR, **kwargs)

    def log_message(self, format, *args):
        # Suppress request logging
        pass

class FrontendServer:
    _server = None
    _thread = None

    @classmethod
    def start(cls, port: int):
        """Start serving the front-end UI on localhost at given port."""
        cls.stop()
        handler = _FrontendRequestHandler
        cls._server = socketserver.TCPServer(('127.0.0.1', port), handler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def stop(cls):
        """Stop the front-end server if running."""
        if cls._server:
            cls._server.shutdown()
            cls._server.server_close()
            cls._server = None
        if cls._thread:
            cls._thread.join(timeout=1)
            cls._thread = None
