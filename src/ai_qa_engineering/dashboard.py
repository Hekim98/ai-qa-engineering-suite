"""Local-only HTTP dashboard for running and reviewing QA audits."""

from __future__ import annotations

import hmac
import json
import mimetypes
import re
import secrets
import threading
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import parse_qs, quote, unquote, urlsplit

from pydantic import ValidationError

from ai_qa_engineering.audit_models import AuditResult, AuditStatus
from ai_qa_engineering.config import ConfigError, QAConfig, load_config
from ai_qa_engineering.dashboard_models import (
    CandidateReview,
    ReviewDecision,
    ReviewDocument,
    ReviewSubmission,
)
from ai_qa_engineering.orchestration import AuditOutputs, run_audit
from ai_qa_engineering.paths import UnsafePathError, resolve_within
from ai_qa_engineering.secrets import available_secret_values, redact_text

AuditRunner = Callable[..., AuditOutputs]
_AUDIT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_MAX_REQUEST_BYTES = 64 * 1024


class EvidenceRecord(TypedDict):
    profile: str
    run_id: str
    files: list[str]


class DashboardError(ValueError):
    """Base error for safe, user-visible dashboard failures."""


class DashboardNotFoundError(DashboardError):
    """Raised when a requested local dashboard resource does not exist."""


class DashboardConflictError(DashboardError):
    """Raised when an audit cannot start because another one is active."""


@dataclass
class DashboardJob:
    job_id: str
    config_path: str
    profiles: tuple[str, ...]
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    audit_id: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "config_path": self.config_path,
            "profiles": self.profiles,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "audit_id": self.audit_id,
            "error": self.error,
        }


class DashboardService:
    """Own dashboard discovery, background execution, and human review state."""

    def __init__(
        self,
        repository_root: str | Path,
        *,
        audit_runner: AuditRunner = run_audit,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.config_root = self.repository_root / "configs"
        self._audit_runner = audit_runner
        self._jobs: dict[str, DashboardJob] = {}
        self._lock = threading.RLock()

    def _configurations(self) -> list[tuple[Path, QAConfig]]:
        configurations: list[tuple[Path, QAConfig]] = []
        if not self.config_root.is_dir():
            return configurations
        for path in sorted(self.config_root.glob("*.yaml")):
            try:
                configurations.append((path.resolve(), load_config(path)))
            except ConfigError:
                continue
        return configurations

    def list_configurations(self) -> list[dict[str, Any]]:
        return [
            {
                "path": str(path.relative_to(self.repository_root)),
                "name": config.project.name,
                "environment": config.project.environment,
                "target": str(config.project.base_url),
                "profiles": [
                    {
                        "name": name,
                        "browser": profile.engine.value,
                        "suite": profile.suite.value,
                        "mobile": profile.mobile,
                    }
                    for name, profile in config.browser.profiles.items()
                ],
                "requires_credentials": config.credentials is not None,
            }
            for path, config in self._configurations()
        ]

    def _audit_roots(self) -> tuple[Path, ...]:
        roots = {self.repository_root / "artifacts/audits"}
        for _, config in self._configurations():
            try:
                roots.add(resolve_within(self.repository_root, config.orchestration.audit_root))
            except UnsafePathError:
                continue
        return tuple(sorted(roots))

    def _find_audit_directory(self, audit_id: str) -> Path:
        if not _AUDIT_ID.fullmatch(audit_id):
            raise DashboardNotFoundError("Audit not found")
        for root in self._audit_roots():
            candidate = root / audit_id
            if (candidate / "audit.json").is_file():
                return candidate.resolve()
        raise DashboardNotFoundError(f"Audit not found: {audit_id}")

    def _load_audit(self, audit_id: str) -> tuple[Path, AuditResult]:
        directory = self._find_audit_directory(audit_id)
        try:
            audit = AuditResult.model_validate_json(
                (directory / "audit.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise DashboardError(f"Invalid audit package: {audit_id}") from exc
        if audit.audit_id != audit_id:
            raise DashboardError(f"Audit package ID does not match its directory: {audit_id}")
        return directory, audit

    @staticmethod
    def _review_path(directory: Path) -> Path:
        return directory / "review-decisions.json"

    def _load_reviews(self, directory: Path, audit_id: str) -> ReviewDocument:
        review_path = self._review_path(directory)
        if not review_path.is_file():
            return ReviewDocument(audit_id=audit_id, updated_at=datetime.now(UTC))
        try:
            document = ReviewDocument.model_validate_json(review_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DashboardError(f"Invalid review decisions for audit: {audit_id}") from exc
        if document.audit_id != audit_id:
            raise DashboardError(f"Review decisions do not match audit: {audit_id}")
        return document

    @staticmethod
    def _review_summary(audit: AuditResult, document: ReviewDocument) -> dict[str, object]:
        decisions = {review.candidate_id: review for review in document.reviews}
        candidate_ids = {candidate.id for candidate in audit.candidate_findings}
        confirmed = sum(
            decision.decision is ReviewDecision.CONFIRMED
            for candidate_id, decision in decisions.items()
            if candidate_id in candidate_ids
        )
        rejected = sum(
            decision.decision is ReviewDecision.REJECTED
            for candidate_id, decision in decisions.items()
            if candidate_id in candidate_ids
        )
        pending = max(0, len(candidate_ids) - confirmed - rejected)
        complete = pending == 0
        if audit.status is AuditStatus.INCOMPLETE:
            gate = "blocked"
            reason = "The audit is incomplete. Required checks must run before report preparation."
        elif not complete:
            gate = "blocked"
            reason = "Every candidate finding must be confirmed or rejected."
        else:
            gate = "open"
            reason = "Candidate review is complete. Verified report inputs may now be prepared."
        return {
            "total": len(candidate_ids),
            "confirmed": confirmed,
            "rejected": rejected,
            "pending": pending,
            "complete": complete,
            "report_gate": gate,
            "report_gate_reason": reason,
        }

    def _audit_summary(self, audit: AuditResult, directory: Path) -> dict[str, object]:
        reviews = self._load_reviews(directory, audit.audit_id)
        return {
            "audit_id": audit.audit_id,
            "project": audit.project,
            "environment": audit.environment,
            "status": audit.status.value,
            "tests": audit.total_tests,
            "passed": audit.passed_tests,
            "persistent_failures": audit.persistent_failures,
            "flaky_tests": audit.flaky_tests,
            "candidates": len(audit.candidate_findings),
            "review": self._review_summary(audit, reviews),
            "finished_at": audit.finished_at.isoformat(),
        }

    def list_audits(self, *, limit: int = 20) -> list[dict[str, object]]:
        discovered: list[tuple[datetime, dict[str, object]]] = []
        seen: set[str] = set()
        for root in self._audit_roots():
            if not root.is_dir():
                continue
            for path in root.glob("*/audit.json"):
                try:
                    audit = AuditResult.model_validate_json(path.read_text(encoding="utf-8"))
                    directory = path.parent.resolve()
                    if audit.audit_id in seen:
                        continue
                    discovered.append((audit.finished_at, self._audit_summary(audit, directory)))
                    seen.add(audit.audit_id)
                except (DashboardError, OSError, ValueError):
                    continue
        discovered.sort(key=lambda item: item[0], reverse=True)
        return [summary for _, summary in discovered[:limit]]

    @staticmethod
    def _load_evidence_index(directory: Path) -> list[EvidenceRecord]:
        path = directory / "evidence-index.json"
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        records: list[EvidenceRecord] = []
        for item in payload:
            if not isinstance(item, dict) or not isinstance(item.get("files"), list):
                continue
            safe_files = [value for value in item["files"] if isinstance(value, str)]
            records.append(
                {
                    "profile": str(item.get("profile", "unknown")),
                    "run_id": str(item.get("run_id", "unknown")),
                    "files": safe_files,
                }
            )
        return records

    @staticmethod
    def _evidence_kind(path: str) -> str:
        suffix = Path(path).suffix.lower()
        return {
            ".png": "screenshot",
            ".webm": "video",
            ".zip": "trace",
            ".json": "data",
            ".log": "log",
            ".html": "report",
            ".pdf": "report",
        }.get(suffix, "file")

    def audit_detail(self, audit_id: str) -> dict[str, object]:
        directory, audit = self._load_audit(audit_id)
        document = self._load_reviews(directory, audit_id)
        reviews = {review.candidate_id: review for review in document.reviews}
        evidence_records = self._load_evidence_index(directory)
        evidence = [
            {
                "profile": record["profile"],
                "run_id": record["run_id"],
                "files": [
                    {
                        "path": path,
                        "name": Path(path).name,
                        "kind": self._evidence_kind(path),
                        "url": (
                            f"/api/evidence/{quote(audit_id, safe='')}?path={quote(path, safe='')}"
                        ),
                    }
                    for path in record["files"]
                    if isinstance(path, str)
                ],
            }
            for record in evidence_records
        ]
        candidates: list[dict[str, Any]] = []
        for candidate in audit.candidate_findings:
            payload = candidate.model_dump(mode="json")
            review = reviews.get(candidate.id)
            payload["review"] = review.model_dump(mode="json") if review else None
            candidates.append(payload)
        report_files = []
        for name in ("draft-audit-report.html", "draft-audit-report.pdf"):
            relative = str((directory / "reports" / name).relative_to(self.repository_root))
            if (directory / "reports" / name).is_file():
                report_files.append(
                    {
                        "name": name,
                        "kind": "report",
                        "url": (
                            f"/api/evidence/{quote(audit_id, safe='')}"
                            f"?path={quote(relative, safe='')}"
                        ),
                    }
                )
        return {
            "audit": audit.model_dump(mode="json"),
            "profiles": [profile.model_dump(mode="json") for profile in audit.profiles],
            "candidates": candidates,
            "evidence": evidence,
            "reports": report_files,
            "review": self._review_summary(audit, document),
        }

    def save_review(self, audit_id: str, submission: ReviewSubmission) -> dict[str, object]:
        directory, audit = self._load_audit(audit_id)
        candidate_ids = {item.id for item in audit.candidate_findings}
        if submission.candidate_id not in candidate_ids:
            raise DashboardNotFoundError(
                f"Candidate not found in audit {audit_id}: {submission.candidate_id}"
            )
        now = datetime.now(UTC)
        review = CandidateReview(**submission.model_dump(), reviewed_at=now)
        with self._lock:
            current = self._load_reviews(directory, audit_id)
            updated = {
                item.candidate_id: item
                for item in current.reviews
                if item.candidate_id in candidate_ids
            }
            updated[review.candidate_id] = review
            document = ReviewDocument(
                audit_id=audit_id,
                updated_at=now,
                reviews=tuple(updated[key] for key in sorted(updated)),
            )
            destination = self._review_path(directory)
            temporary = destination.with_suffix(".json.tmp")
            temporary.write_text(document.model_dump_json(indent=2), encoding="utf-8")
            temporary.replace(destination)
        return {
            "review": review.model_dump(mode="json"),
            "summary": self._review_summary(audit, document),
        }

    def _resolve_configuration(self, relative_path: str) -> tuple[Path, QAConfig]:
        known = {
            str(path.relative_to(self.repository_root)): (path, config)
            for path, config in self._configurations()
        }
        try:
            return known[relative_path]
        except KeyError as exc:
            raise DashboardNotFoundError(f"Configuration not found: {relative_path}") from exc

    def start_audit(
        self,
        config_path: str,
        profiles: Sequence[str] | None,
    ) -> dict[str, object]:
        path, config = self._resolve_configuration(config_path)
        selected = tuple(profiles) if profiles is not None else tuple(config.browser.profiles)
        if not selected:
            raise DashboardError("Select at least one browser profile")
        unknown = sorted(set(selected) - set(config.browser.profiles))
        if unknown:
            raise DashboardError(f"Unknown browser profiles: {', '.join(unknown)}")
        if len(selected) != len(set(selected)):
            raise DashboardError("Browser profiles must be unique")

        with self._lock:
            if any(job.status in {"queued", "running"} for job in self._jobs.values()):
                raise DashboardConflictError("Another audit is already running")
            now = datetime.now(UTC)
            job = DashboardJob(
                job_id=f"job-{secrets.token_hex(6)}",
                config_path=config_path,
                profiles=selected,
                status="queued",
                created_at=now,
            )
            self._jobs[job.job_id] = job
            worker = threading.Thread(
                target=self._execute_audit,
                args=(job.job_id, path, config),
                name=f"ai-qa-dashboard-{job.job_id}",
                daemon=True,
            )
            worker.start()
            return job.as_dict()

    def _execute_audit(self, job_id: str, path: Path, config: QAConfig) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.started_at = datetime.now(UTC)
        try:
            outputs = self._audit_runner(
                path,
                profile_names=job.profiles,
                repository_root=self.repository_root,
            )
        except Exception as exc:  # noqa: BLE001 - job boundary must preserve UI availability
            secret_values = available_secret_values(
                config.credentials,
                env_file=self.repository_root / ".env",
            )
            with self._lock:
                job.status = "failed"
                job.error = redact_text(str(exc), secret_values)
                job.finished_at = datetime.now(UTC)
            return
        with self._lock:
            job.status = "completed"
            job.audit_id = outputs.audit.audit_id
            job.finished_at = datetime.now(UTC)

    def list_jobs(self) -> list[dict[str, object]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [job.as_dict() for job in jobs[:20]]

    def state(self) -> dict[str, object]:
        return {
            "configurations": self.list_configurations(),
            "audits": self.list_audits(),
            "jobs": self.list_jobs(),
        }

    def open_evidence(self, audit_id: str, requested_path: str) -> tuple[Path, str]:
        directory, _ = self._load_audit(audit_id)
        records = self._load_evidence_index(directory)
        allowed = {path for record in records for path in record["files"] if isinstance(path, str)}
        allowed.update(
            str((directory / relative).relative_to(self.repository_root))
            for relative in (
                "audit.json",
                "candidate-findings.yaml",
                "evidence-index.json",
                "review-decisions.json",
                "reports/draft-audit-report.html",
                "reports/draft-audit-report.pdf",
            )
            if (directory / relative).is_file()
        )
        if requested_path not in allowed:
            raise DashboardNotFoundError("Evidence file not found")
        try:
            path = resolve_within(self.repository_root, requested_path)
        except UnsafePathError as exc:
            raise DashboardNotFoundError("Evidence file not found") from exc
        if not path.is_file() or not path.is_relative_to(directory):
            raise DashboardNotFoundError("Evidence file not found")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".html", ".json", ".yaml", ".yml", ".log"}:
            content_type = "text/plain; charset=utf-8"
        return path, content_type


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server: DashboardHTTPServer

    def do_HEAD(self) -> None:  # noqa: N802
        if not self._local_host_allowed():
            self._error(HTTPStatus.MISDIRECTED_REQUEST, "Dashboard accepts localhost requests only")
            return
        if urlsplit(self.path).path in {"/", "/health"}:
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:  # noqa: N802
        if not self._local_host_allowed():
            self._error(HTTPStatus.MISDIRECTED_REQUEST, "Dashboard accepts localhost requests only")
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._asset("index.html", "text/html; charset=utf-8", inject_token=True)
            return
        if parsed.path == "/assets/app.css":
            self._asset("app.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/assets/app.js":
            self._asset("app.js", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/health":
            self._json({"status": "ok", "scope": "localhost"})
            return
        if parsed.path == "/api/state":
            self._json(self.server.service.state())
            return
        audit_match = re.fullmatch(r"/api/audits/([^/]+)", parsed.path)
        if audit_match:
            self._handle(lambda: self.server.service.audit_detail(unquote(audit_match.group(1))))
            return
        evidence_match = re.fullmatch(r"/api/evidence/([^/]+)", parsed.path)
        if evidence_match:
            values = parse_qs(parsed.query).get("path", [])
            if len(values) != 1:
                self._error(HTTPStatus.BAD_REQUEST, "Exactly one evidence path is required")
                return
            try:
                path, content_type = self.server.service.open_evidence(
                    unquote(evidence_match.group(1)), values[0]
                )
            except DashboardNotFoundError as exc:
                self._error(HTTPStatus.NOT_FOUND, str(exc))
                return
            self._file(path, content_type)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self._local_host_allowed():
            self._error(HTTPStatus.MISDIRECTED_REQUEST, "Dashboard accepts localhost requests only")
            return
        if not hmac.compare_digest(self.headers.get("X-AI-QA-Token", ""), self.server.csrf_token):
            self._error(HTTPStatus.FORBIDDEN, "Invalid local request token")
            return
        try:
            payload = self._request_json()
        except DashboardError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/api/audits":
            config_path = payload.get("config_path")
            profiles = payload.get("profiles")
            if (
                not isinstance(config_path, str)
                or not isinstance(profiles, list)
                or not all(isinstance(item, str) for item in profiles)
            ):
                self._error(
                    HTTPStatus.BAD_REQUEST,
                    "config_path and a list of profiles are required",
                )
                return
            try:
                job = self.server.service.start_audit(config_path, profiles)
            except DashboardConflictError as exc:
                self._error(HTTPStatus.CONFLICT, str(exc))
                return
            except DashboardNotFoundError as exc:
                self._error(HTTPStatus.NOT_FOUND, str(exc))
                return
            except DashboardError as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._json(job, HTTPStatus.ACCEPTED)
            return
        review_match = re.fullmatch(r"/api/audits/([^/]+)/reviews", parsed.path)
        if review_match:
            try:
                submission = ReviewSubmission.model_validate(payload)
                result = self.server.service.save_review(unquote(review_match.group(1)), submission)
            except ValidationError as exc:
                message = exc.errors(include_url=False)[0]["msg"]
                self._error(HTTPStatus.BAD_REQUEST, str(message))
                return
            except DashboardNotFoundError as exc:
                self._error(HTTPStatus.NOT_FOUND, str(exc))
                return
            except DashboardError as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._json(result)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _request_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", maxsplit=1)[0]
        if content_type != "application/json":
            raise DashboardError("Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise DashboardError("Invalid request length") from exc
        if length <= 0 or length > _MAX_REQUEST_BYTES:
            raise DashboardError("Request body must be between 1 byte and 64 KB")
        try:
            payload: Any = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DashboardError("Request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise DashboardError("Request body must be a JSON object")
        return payload

    def _handle(self, operation: Callable[[], object]) -> None:
        try:
            self._json(operation())
        except DashboardNotFoundError as exc:
            self._error(HTTPStatus.NOT_FOUND, str(exc))
        except DashboardError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _local_host_allowed(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "").lower() in {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
        }

    def _asset(self, name: str, content_type: str, *, inject_token: bool = False) -> None:
        body = files("ai_qa_engineering.dashboard_assets").joinpath(name).read_bytes()
        if inject_token:
            body = body.replace(b"__AI_QA_TOKEN__", self.server.csrf_token.encode())
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.send_header("Content-Security-Policy", "default-src 'none'; sandbox")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def log_message(self, format: str, *args: object) -> None:
        return


class DashboardHTTPServer(ThreadingHTTPServer):
    service: DashboardService
    csrf_token: str


def create_dashboard_server(
    repository_root: str | Path,
    *,
    port: int = 8765,
    audit_runner: AuditRunner = run_audit,
) -> DashboardHTTPServer:
    if not 0 <= port <= 65_535:
        raise ValueError("Dashboard port must be between 0 and 65535")
    server = DashboardHTTPServer(("127.0.0.1", port), DashboardRequestHandler)
    server.service = DashboardService(repository_root, audit_runner=audit_runner)
    server.csrf_token = secrets.token_urlsafe(32)
    return server


def serve_dashboard(
    repository_root: str | Path | None = None,
    *,
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Serve the dashboard on loopback until interrupted."""
    server = create_dashboard_server(repository_root or Path.cwd(), port=port)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"AI QA Control Room is available at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
