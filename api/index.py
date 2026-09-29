import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

if os.environ.get("VERCEL") or not os.environ.get("HMS_DB_PATH"):
    os.environ["HMS_DB_PATH"] = "/tmp/hms.db"

from models import init_db
from app import app as flask_app

init_db(seed=True)


class VercelWSGIHandler:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        for prefix in ("/api/index.py", "/api/index"):
            if path.startswith(prefix):
                environ["PATH_INFO"] = path[len(prefix):] or "/"
                break
        return self.application(environ, start_response)


app = VercelWSGIHandler(flask_app)