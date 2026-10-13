# Usługa demonstracyjna web

```python markpact:file path=main.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"service": "web", "status": "ok", "api_url": os.environ.get("API_URL", "")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("127.0.0.1", int(os.environ.get("MARKPACT_PORT", "8100"))), Handler).serve_forever()
```

```bash markpact:run
python main.py
```
