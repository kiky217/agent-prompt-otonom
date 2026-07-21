"""Read-only Bootstrap Sync planner for legacy HERMES agents.

This preview deliberately has no apply implementation. It inventories metadata,
validates the shared manifest, detects common runtime PID files, and emits a
sanitized migration plan. It never writes to an agent home.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "hermes.bootstrap-sync/v1"
EXPECTED_AGENTS = {"seven", "jendral", "kapten", "brigadir"}
PID_FILES = ("runtime.pid", "hermes-agent.pid", ".runtime.pid")
LOCAL_FILES = (
    "config.yaml",
    "config.yml",
    "SOUL.md",
    "MEMORY.md",
    "USER.md",
    ".env",
    "state.json",
)


class BootstrapError(RuntimeError):
    """Raised when the preview cannot safely produce a plan."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"manifest tidak dapat dibaca: {path}") from exc
    if not isinstance(value, dict):
        raise BootstrapError("manifest harus berupa object JSON")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_json(path)
    if manifest.get("schema") != SCHEMA:
        raise BootstrapError("schema manifest tidak didukung")

    policy = manifest.get("policy")
    roles = manifest.get("roles")
    if not isinstance(policy, dict) or not isinstance(roles, dict):
        raise BootstrapError("policy dan roles wajib tersedia")
    if policy.get("default_mode") != "dry-run":
        raise BootstrapError("mode awal wajib dry-run")
    if policy.get("runtime_mutation") is not False:
        raise BootstrapError("preview tidak boleh mengizinkan mutasi runtime")
    if policy.get("auto_update_from_main") is not False:
        raise BootstrapError("auto-update dari main harus dinonaktifkan")
    if set(roles) != EXPECTED_AGENTS:
        raise BootstrapError("manifest harus mendefinisikan empat agen resmi")

    protected = {str(v).casefold() for v in policy.get("protected_agents", [])}
    if "seven" not in protected:
        raise BootstrapError("SEVEN wajib berada dalam protected_agents")
    if roles["seven"].get("migration_enabled") is not False:
        raise BootstrapError("migrasi SEVEN wajib dinonaktifkan pada preview")
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_metadata(root: Path, files: Iterable[Path]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(files, key=lambda item: str(item).casefold()):
        try:
            if not path.is_file() or path.is_symlink():
                continue
            stat = path.stat()
            result.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": stat.st_size,
                    "sha256": _sha256(path),
                }
            )
        except (OSError, ValueError):
            continue
    return result


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _active_pid_evidence(agent_home: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for name in PID_FILES:
        path = agent_home / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            raw = path.read_text(encoding="ascii").strip()
            pid = int(raw)
        except (OSError, UnicodeError, ValueError):
            evidence.append({"path": name, "state": "UNREADABLE"})
            continue
        evidence.append(
            {
                "path": name,
                "pid": pid,
                "state": "RUNNING" if _pid_is_alive(pid) else "STALE",
            }
        )
    return evidence


def build_plan(
    manifest: dict[str, Any], agent_id: str, agent_home: Path
) -> dict[str, Any]:
    agent = agent_id.strip().casefold()
    if agent not in EXPECTED_AGENTS:
        raise BootstrapError(f"agent tidak dikenal: {agent_id}")

    root = agent_home.expanduser().resolve(strict=False)
    policy = manifest["policy"]
    role = manifest["roles"][agent]
    protected = {str(v).casefold() for v in policy["protected_agents"]}

    if not root.is_dir():
        status = "BLOCKED_HOME_NOT_FOUND"
        local_files: list[dict[str, Any]] = []
        skill_files: list[dict[str, Any]] = []
        pids: list[dict[str, Any]] = []
    else:
        local_files = _safe_metadata(
            root, (root / name for name in LOCAL_FILES)
        )
        skills_root = root / "skills"
        skill_files = (
            _safe_metadata(root, skills_root.rglob("SKILL.md"))
            if skills_root.is_dir()
            else []
        )
        pids = _active_pid_evidence(root)
        running = any(item.get("state") == "RUNNING" for item in pids)
        if agent in protected or role.get("migration_enabled") is not True:
            status = "BLOCKED_PROTECTED_AGENT"
        elif policy.get("deny_when_running") is True and running:
            status = "BLOCKED_AGENT_RUNNING"
        else:
            status = "READY_DRY_RUN"

    return {
        "schema": "hermes.bootstrap-plan/v1",
        "mode": "dry-run",
        "status": status,
        "agent_id": agent,
        "agent_home": str(root),
        "role_profile": role["profile"],
        "runtime_pid_evidence": pids,
        "inventory": {
            "local_files": local_files,
            "skill_count": len(skill_files),
            "skills": skill_files,
        },
        "preserve_local": policy["preserve_local"],
        "planned_actions": (
            [
                "backup konfigurasi terpilih",
                "validasi role profile",
                "gabungkan fondasi bersama tanpa rahasia lokal",
                "smoke test dan rollback otomatis jika gagal",
            ]
            if status == "READY_DRY_RUN"
            else []
        ),
        "writes_performed": False,
        "processes_terminated": False,
        "secrets_emitted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--agent-home", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ditolak pada preview; tersedia hanya untuk menguji fail-closed.",
    )
    args = parser.parse_args(argv)

    if args.apply:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_APPLY_NOT_IMPLEMENTED",
                    "writes_performed": False,
                    "processes_terminated": False,
                },
                indent=2,
            )
        )
        return 3

    try:
        manifest = load_manifest(args.manifest)
        plan = build_plan(manifest, args.agent_id, args.agent_home)
    except BootstrapError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, indent=2))
        return 2

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0 if plan["status"] == "READY_DRY_RUN" else 4


if __name__ == "__main__":
    raise SystemExit(main())
