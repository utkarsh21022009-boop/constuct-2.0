"""HTTP REST API and static web server for FixPilot AI.
Standard library only (zero external pip dependencies required).
Multi-threaded with automatic fallback if preferred port is occupied.
"""

import http.server
import socket
import json
import os
import mimetypes
import urllib.parse
from typing import Dict, Any, Optional

from fixpilot.knowledge_base import KnowledgeBase
from fixpilot.retrieval import DocumentRetriever
from fixpilot.safety_guardrails import SafetyGuardrails
from fixpilot.reasoning_engine import ReasoningEngine
from fixpilot.review_gate import ReviewGateManager
from fixpilot.simulator import PilotBenchmarkRunner, SIMULATED_SCENARIOS
from fixpilot.models import ReviewStatus


class FixPilotApp:
    """Core application instance holding models and business logic."""
    def __init__(self, data_dir: Optional[str] = None):
        self.kb = KnowledgeBase(data_dir=data_dir)
        self.retriever = DocumentRetriever(self.kb)
        self.guardrails = SafetyGuardrails()
        self.engine = ReasoningEngine(self.retriever, self.guardrails)
        self.review_gate = ReviewGateManager()
        self.benchmark_runner = PilotBenchmarkRunner(self.engine)


# Global singleton application instance
APP_INSTANCE: Optional[FixPilotApp] = None


def get_app() -> FixPilotApp:
    global APP_INSTANCE
    if APP_INSTANCE is None:
        APP_INSTANCE = FixPilotApp()
    return APP_INSTANCE


class FixPilotRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler serving REST API and embedded web UI.
    Inherits from BaseHTTPRequestHandler for full Vercel serverless compatibility.
    """

    def __init__(self, *args, **kwargs):
        self.web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
        super().__init__(*args, **kwargs)

    def _serve_file(self, filepath: str, content_type: str):
        if not os.path.exists(filepath):
            self._send_json({"error": "File not found"}, status=404)
            return
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_json({"error": f"Error serving file: {e}"}, status=500)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_data = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw_data)
        except Exception as e:
            print(f"Error reading JSON request body: {e}")
        return None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        app = get_app()

        # 1. Static Web Files
        if path == "/" or path == "/index.html":
            self._serve_file(os.path.join(self.web_dir, "index.html"), "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._serve_file(os.path.join(self.web_dir, "styles.css"), "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_file(os.path.join(self.web_dir, "app.js"), "application/javascript; charset=utf-8")
            return

        # 2. REST API Endpoints
        if path == "/api/status":
            self._send_json({
                "status": "ONLINE",
                "app": "FixPilot AI",
                "tagline": "Evidence-Guided Copilot for Qualified Maintenance Technicians",
                "team": "Team Slither",
                "manuals_count": len(app.kb.manuals),
                "passages_indexed": len(app.kb.all_passages),
                "scenarios_available": len(SIMULATED_SCENARIOS),
                "review_gate_active": True
            })
            return

        if path == "/api/manuals":
            self._send_json(app.kb.list_manuals())
            return

        if path.startswith("/api/manuals/"):
            manual_id = path[len("/api/manuals/"):]
            manual = app.kb.get_manual(manual_id)
            if manual:
                self._send_json({
                    "manual_id": manual.manual_id,
                    "title": manual.title,
                    "machine_model": manual.machine_model,
                    "manufacturer": manual.manufacturer,
                    "version": manual.version,
                    "approval_date": manual.approval_date,
                    "total_pages": manual.total_pages,
                    "sections": [
                        {
                            "section_id": s.section_id,
                            "title": s.title,
                            "page_number": s.page_number,
                            "content": s.content,
                            "passages": [
                                {
                                    "passage_id": p.passage_id,
                                    "content": p.content,
                                    "error_codes": p.error_codes,
                                    "keywords": p.keywords,
                                    "safety_warnings": p.safety_warnings
                                }
                                for p in s.passages
                            ]
                        }
                        for s in manual.sections
                    ]
                })
            else:
                self._send_json({"error": "Manual not found"}, status=404)
            return

        if path == "/api/scenarios":
            self._send_json(app.benchmark_runner.list_scenarios())
            return

        if path == "/api/audit-log":
            trail = app.review_gate.get_audit_trail()
            stats = app.review_gate.get_stats()
            self._send_json({"audit_trail": trail, "stats": stats})
            return

        if path == "/api/benchmark":
            bench_results = app.benchmark_runner.run_benchmark()
            self._send_json(bench_results)
            return

        # Fallback 404 for unknown paths
        self._send_json({"error": f"Path not found: {path}"}, status=404)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        app = get_app()
        body = self._read_json_body() or {}

        if path == "/api/diagnose":
            query = body.get("query", "").strip()
            machine = body.get("machine_model", "").strip() or None
            if not query:
                self._send_json({"error": "Query is required"}, status=400)
                return

            plan = app.engine.diagnose(query, machine_model=machine)
            app.review_gate.register_plan(plan)
            self._send_json(plan.to_dict())
            return

        if path == "/api/review":
            plan_id = body.get("plan_id")
            if not plan_id:
                self._send_json({"error": "plan_id is required"}, status=400)
                return

            status_str = body.get("status", "APPROVED_EXECUTED")
            try:
                status = ReviewStatus(status_str)
            except ValueError:
                status = ReviewStatus.APPROVED_EXECUTED

            tech_id = body.get("technician_id", "Arjun (Lead Tech)")
            action_taken = body.get("action_taken", "Verified check per manual procedure")
            notes = body.get("notes", "")
            escalation_reason = body.get("escalation_reason")

            decision = app.review_gate.submit_decision(
                plan_id=plan_id,
                technician_id=tech_id,
                status=status,
                action_taken=action_taken,
                notes=notes,
                escalation_reason=escalation_reason
            )
            self._send_json(decision.to_dict())
            return

        if path == "/api/manuals/upload":
            if not body or "manual_id" not in body or "title" not in body:
                self._send_json({"error": "Invalid manual payload"}, status=400)
                return
            new_manual = app.kb.add_custom_manual(body)
            app.retriever = DocumentRetriever(app.kb)
            app.engine = ReasoningEngine(app.retriever, app.guardrails)
            self._send_json({
                "message": f"Manual '{new_manual.title}' indexed successfully.",
                "manual_id": new_manual.manual_id
            })
            return

        self._send_json({"error": f"Endpoint {path} not found"}, status=404)


def find_free_port(preferred_port: int, candidates=None) -> int:
    """Finds an available TCP port, starting with preferred_port."""
    if candidates is None:
        candidates = [8000, 8090, 8888, 3000, 5050, 8081, 8082, 8080]
    
    port_list = [preferred_port] + [p for p in candidates if p != preferred_port]
    for p in port_list:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', p))
            s.close()
            return p
        except OSError:
            continue
    return preferred_port


def run_server(port: int = 8000, host: str = "127.0.0.1"):
    """Starts the multi-threaded FixPilot HTTP server with automatic port detection."""
    get_app()  # Pre-warm singleton

    # Auto-detect free port if requested port is busy
    actual_port = find_free_port(port)
    if actual_port != port:
        print(f"Notice: Port {port} is occupied by another process on your machine.")
        print(f"FixPilot automatically switched to free port {actual_port}.")

    handler = FixPilotRequestHandler
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    
    with http.server.ThreadingHTTPServer((host, actual_port), handler) as httpd:
        print(f"==================================================")
        print(f" FixPilot AI · Industrial Troubleshooting Server")
        print(f" Active on: http://{host}:{actual_port}")
        print(f" Also accessible at: http://localhost:{actual_port}")
        print(f" 'When a Machine Stops, Every Minute Matters'")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down FixPilot AI Server.")
            httpd.server_close()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)
