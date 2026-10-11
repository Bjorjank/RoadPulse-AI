import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

TRANSITIONS = {
    "CREATED": {"QUEUED", "CANCELLED"},
    "QUEUED": {"RUNNING", "CANCELLED", "FAILED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
    "FAILED": set(),
}


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "roadpulse.sqlite3"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=30)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, job):
        with self.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?, ?)", (job["id"], json.dumps(job)))

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return json.loads(row[0])

    def all(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM jobs")]

    def update(self, job_id, **changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            job = json.loads(row[0])
            if "status" in changes and changes["status"] != job["status"]:
                if changes["status"] not in TRANSITIONS[job["status"]]:
                    raise ValueError(f"Invalid transition {job['status']} -> {changes['status']}")
            job.update(changes)
            db.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps(job), job_id))
        return job
