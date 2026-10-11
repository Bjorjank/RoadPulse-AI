import asyncio
import multiprocessing
import re
import shutil
import threading
import uuid
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from typing import Annotated

import cv2
import onnxruntime as ort
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

from roadpulse.config import DATA, MAX_UPLOAD, MODEL
from roadpulse.jobs.schemas import Health, Job, Results, StartRequest, System
from roadpulse.jobs.store import Store
from roadpulse.video.engine import process_job


class UploadLimitMiddleware:
    """Bound raw multipart input before UploadFile spools it to disk."""

    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/jobs":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        length = headers.get(b"content-length")
        if length:
            try:
                oversized = int(length) > self.limit
            except ValueError:
                oversized = True
            if oversized:
                from starlette.responses import JSONResponse

                return await JSONResponse({"detail": "Upload exceeds 1 GiB limit"}, status_code=413)(
                    scope, receive, send
                )
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                raise HTTPException(413, "Upload exceeds 1 GiB limit")
            return message

        await self.app(scope, limited_receive, send)


ARTIFACTS = {"annotated.mp4": "video/mp4", "events.csv": "text/csv", "summary.json": "application/json"}


def create_app(root=DATA, enable_worker=True):
    store = Store(root)
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        # Incomplete jobs from an interrupted previous process cannot resume silently.
        for job in store.all():
            if job["status"] in {"RUNNING", "QUEUED"}:
                store.update(
                    job["id"], status="FAILED", error="Application interrupted; upload and restart analysis"
                )
        app.state.pool = (
            ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
            if enable_worker
            else None
        )
        app.state.futures = {}
        yield
        for job in store.all():
            if job["status"] in {"RUNNING", "QUEUED"}:
                store.update(job["id"], status="CANCELLED")
        if app.state.pool:
            app.state.pool.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="RoadPulse AI", lifespan=lifespan)
    app.state.store = store
    app.add_middleware(UploadLimitMiddleware, limit=MAX_UPLOAD + 1024 * 1024)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def local_origin(request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in {
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        }:
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Only local application origins are allowed"}, status_code=403)
        return await call_next(request)

    def get_job(job_id):
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise HTTPException(404, "Unknown job")
        try:
            return store.get(job_id)
        except KeyError:
            raise HTTPException(404, "Unknown job") from None

    @app.get("/api/health", response_model=Health)
    def health():
        return Health()

    @app.get("/api/system", response_model=System)
    def system():
        return System(
            model="YOLOX-Tiny",
            model_ready=MODEL.exists() and MODEL.with_suffix(".json").exists(),
            available_providers=ort.get_available_providers(),
            profile="Balanced / 416 x 416",
        )

    @app.post("/api/jobs", response_model=Job, status_code=201)
    async def upload(file: Annotated[UploadFile, File()]):
        filename = file.filename or ""
        if (
            not filename.lower().endswith(".mp4")
            or any(c in filename for c in ("/", "\\", "\x00"))
            or len(filename) > 180
        ):
            raise HTTPException(400, "Upload an MP4 with a simple filename")
        job_id = uuid.uuid4().hex
        folder = store.root / job_id
        folder.mkdir()
        try:
            size = 0
            with (folder / "input.mp4").open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, "Maximum upload size is 1 GiB")
                    await asyncio.to_thread(output.write, chunk)

            def inspect():
                cap = cv2.VideoCapture(str(folder / "input.mp4"))
                try:
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    ok, frame = cap.read()
                    if not ok or not 0 < fps <= 240 or count <= 0:
                        raise ValueError("Invalid or unreadable MP4")
                    h, w = frame.shape[:2]
                    if w * h > 3840 * 2160:
                        raise ValueError("V1 supports videos up to 4K")
                    cv2.imwrite(str(folder / "preview.jpg"), frame)
                    return fps, count, h, w
                finally:
                    cap.release()

            try:
                fps, count, h, w = await asyncio.to_thread(inspect)
            except Exception as exc:
                raise HTTPException(400, str(exc)) from exc
            job = Job(
                id=job_id, filename=filename, status="CREATED", width=w, height=h, fps=fps, total_frames=count
            )
            store.create(job.model_dump(mode="json"))
            return job
        except Exception:
            shutil.rmtree(folder)
            raise
        finally:
            await file.close()

    @app.get("/api/jobs/{job_id}", response_model=Job)
    def status(job_id: str):
        return get_job(job_id)

    @app.post("/api/jobs/{job_id}/start", response_model=Job)
    def start(job_id: str, config: StartRequest):
        with lock:
            job = get_job(job_id)
            if job["status"] != "CREATED":
                raise HTTPException(409, "Only CREATED jobs may start")
            if not MODEL.exists():
                raise HTTPException(503, "Model missing. Run python scripts/prepare_model.py")
            if sum(j["status"] in {"QUEUED", "RUNNING"} for j in store.all()) >= 4:
                raise HTTPException(429, "Worker queue is full (four jobs maximum)")
            if app.state.pool is None:
                raise HTTPException(503, "Worker is disabled")
            updated = store.update(
                job_id, status="QUEUED", line=[[p.x, p.y] for p in config.line], trails=config.trails
            )
            try:
                future = app.state.pool.submit(process_job, str(store.root), job_id)
                app.state.futures[job_id] = future

                def done(task):
                    app.state.futures.pop(job_id, None)
                    if not task.cancelled() and task.exception() is not None:
                        current = store.get(job_id)
                        if current["status"] in {"QUEUED", "RUNNING"}:
                            store.update(job_id, status="FAILED", error=str(task.exception()))

                future.add_done_callback(done)
            except Exception as exc:
                store.update(job_id, status="FAILED", error=str(exc))
                raise HTTPException(503, "Worker could not start") from exc
            return updated

    @app.post("/api/jobs/{job_id}/cancel", response_model=Job)
    def cancel(job_id: str):
        with lock:
            job = get_job(job_id)
            if job["status"] in {"CREATED", "QUEUED", "RUNNING"}:
                try:
                    job = store.update(job_id, status="CANCELLED")
                except ValueError:
                    # A worker may have reached a terminal state after the read.
                    job = get_job(job_id)
            return job

    @app.get("/api/jobs/{job_id}/results", response_model=Results)
    def results(job_id: str):
        job = get_job(job_id)
        if job["status"] != "COMPLETED":
            raise HTTPException(409, "Results are available after completion")
        return job["results"]

    @app.get("/api/jobs/{job_id}/preview")
    def preview(job_id: str):
        get_job(job_id)
        return FileResponse(store.root / job_id / "preview.jpg", media_type="image/jpeg")

    @app.get("/api/jobs/{job_id}/artifacts/{artifact_name}")
    def artifact(job_id: str, artifact_name: str):
        job = get_job(job_id)
        if job["status"] != "COMPLETED" or artifact_name not in ARTIFACTS:
            raise HTTPException(404, "Artifact unavailable")
        path = store.root / job_id / artifact_name
        if not path.is_file():
            raise HTTPException(404, "Artifact missing")
        return FileResponse(path, media_type=ARTIFACTS[artifact_name], filename=artifact_name)

    return app


app = create_app()
