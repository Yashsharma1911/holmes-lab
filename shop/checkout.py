"""checkout-api: tiny demo service. POST /checkout writes an order to Postgres."""
import hashlib, logging, os, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import psycopg
from psycopg_pool import ConnectionPool
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s checkout-api %(message)s")
log = logging.getLogger()
DSN = f"host={os.environ['DB_HOST']} dbname=shop user=shop password={os.environ['DB_PASSWORD']} connect_timeout=3"
LAT = Histogram("checkout_request_duration_seconds", "Checkout latency", buckets=(.025,.05,.1,.25,.5,1,2.5,5))
REQ = Counter("checkout_requests_total", "Checkout requests", ["status"])
pool = ConnectionPool(DSN, min_size=2, max_size=8, open=False)

def init_db():
    for _ in range(60):
        try:
            pool.open(wait=True, timeout=5)
            with pool.connection() as c:
                c.execute("CREATE TABLE IF NOT EXISTS orders (id uuid PRIMARY KEY, created timestamptz DEFAULT now(), payload text)")
            log.info("connected to postgres, orders table ready"); return
        except Exception as e:
            log.warning("waiting for postgres: %s", e); time.sleep(2)

def price_cart():
    # ~10ms of CPU work per order, so CPU contention shows up as latency
    h = b"cart"
    for _ in range(15000): h = hashlib.sha256(h).digest()
    return h.hex()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/metrics": return self._send(200, generate_latest(), CONTENT_TYPE_LATEST)
        if self.path == "/healthz": return self._send(200, b'{"ok":true}')
        self._send(404, b"{}")
    def do_POST(self):
        if self.path != "/checkout": return self._send(404, b"{}")
        t = time.time(); oid = uuid.uuid4()
        try:
            digest = price_cart()
            with pool.connection(timeout=5) as c:
                c.execute("INSERT INTO orders (id, payload) VALUES (%s, %s)", (oid, digest * 8))
            REQ.labels("ok").inc(); self._send(200, b'{"status":"ok"}')
        except Exception as e:
            REQ.labels("error").inc()
            log.error("checkout failed order_id=%s error=%s", oid, str(e).strip().replace("\n", " "))
            self._send(500, b'{"status":"error"}')
        finally:
            LAT.observe(time.time() - t)

if __name__ == "__main__":
    init_db()
    log.info("listening on :8080")
    ThreadingHTTPServer(("", 8080), H).serve_forever()
