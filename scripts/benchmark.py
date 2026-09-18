"""End-to-end timing through the real API: upload, queue, process, download.

Compare one node against several nodes using the same files, profiles and settings.
Wall-clock time is the headline number; it includes upload and download, not only GPU time.
"""
import argparse
import json
import time
from pathlib import Path

import httpx

TERMINAL = {"completed", "failed", "cancelled"}


def login(client: httpx.Client, email: str, password: str) -> None:
    client.get("/login/").raise_for_status()
    # Django 在 HTTPS 下會檢查 Referer,瀏覽器以外的用戶端須自行帶上
    client.headers["Referer"] = str(client.base_url)
    client.headers["X-CSRFToken"] = client.cookies["csrftoken"]
    client.post("/api/auth/login", json={"email": email, "password": password}).raise_for_status()
    client.headers["X-CSRFToken"] = client.cookies["csrftoken"]


def submit(client: httpx.Client, kind: str, name: str, paths: list[Path]) -> dict:
    files = [("files", (path.name, path.read_bytes(), "application/octet-stream")) for path in paths]
    response = client.post("/api/batches", data={"kind": kind, "name": name}, files=files, timeout=300)
    response.raise_for_status()
    return response.json()


def wait(client: httpx.Client, batch_id: str, poll_seconds: float = 2.0) -> dict:
    while True:
        response = client.get("/api/state")
        response.raise_for_status()
        state = response.json()
        batch = next((item for item in state["batches"] if item["id"] == batch_id), None)
        if batch and all(job["status"] in TERMINAL for job in batch["jobs"]):
            return batch
        time.sleep(poll_seconds)


def download(client: httpx.Client, batch_id: str, target: Path) -> int:
    response = client.get(f"/api/batches/{batch_id}/download", timeout=300)
    response.raise_for_status()
    target.write_bytes(response.content)
    return len(response.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--kind", choices=["asr", "upscale"], required=True)
    parser.add_argument("--name", default="benchmark")
    parser.add_argument("--output", type=Path, default=Path("docs/measurements"))
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with httpx.Client(base_url=args.server.rstrip("/"), follow_redirects=True, timeout=30) as client:
        login(client, args.email, args.password)
        started = time.perf_counter()
        batch = submit(client, args.kind, f"{args.name}-{stamp}", args.files)
        finished = wait(client, batch["id"])
        archive = args.output / f"{args.name}-{stamp}.zip"
        archive_bytes = download(client, batch["id"], archive)
        elapsed = time.perf_counter() - started

    result = {
        "started_at": stamp,
        "kind": args.kind,
        "files": len(args.files),
        "wall_seconds": round(elapsed, 2),
        "attempts": {job["filename"]: job["attempt_count"] for job in finished["jobs"]},
        "statuses": {job["filename"]: job["status"] for job in finished["jobs"]},
        "archive_bytes": archive_bytes,
        "timing": "wall clock including upload, queueing, processing and download",
    }
    report = args.output / f"benchmark-{stamp}.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"寫入 {report}")


if __name__ == "__main__":
    main()
