from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bootstrap_sync.bootstrap_sync import (
    BootstrapError,
    build_plan,
    load_manifest,
    main,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "bootstrap_sync" / "manifest.json"


class BootstrapSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST_PATH)

    def test_manifest_locks_seven(self) -> None:
        self.assertFalse(self.manifest["roles"]["seven"]["migration_enabled"])
        self.assertIn("seven", self.manifest["policy"]["protected_agents"])

    def test_legacy_agent_is_ready_only_for_dry_run(self) -> None:
        with TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "skills" / "sample").mkdir(parents=True)
            (home / "skills" / "sample" / "SKILL.md").write_text(
                "# sample\n", encoding="utf-8"
            )
            plan = build_plan(self.manifest, "jendral", home)
            self.assertEqual(plan["status"], "READY_DRY_RUN")
            self.assertEqual(plan["inventory"]["skill_count"], 1)
            self.assertFalse(plan["writes_performed"])

    def test_seven_is_blocked_even_when_not_running(self) -> None:
        with TemporaryDirectory() as temp:
            plan = build_plan(self.manifest, "SEVEN", Path(temp))
            self.assertEqual(plan["status"], "BLOCKED_PROTECTED_AGENT")
            self.assertEqual(plan["planned_actions"], [])

    def test_running_legacy_agent_is_blocked(self) -> None:
        with TemporaryDirectory() as temp:
            home = Path(temp)
            (home / "runtime.pid").write_text(str(os.getpid()), encoding="ascii")
            plan = build_plan(self.manifest, "kapten", home)
            self.assertEqual(plan["status"], "BLOCKED_AGENT_RUNNING")

    def test_sensitive_values_are_not_emitted(self) -> None:
        secret = "DO_NOT_PRINT_THIS_SECRET"
        with TemporaryDirectory() as temp:
            home = Path(temp)
            (home / ".env").write_text(f"TOKEN={secret}\n", encoding="utf-8")
            serialized = json.dumps(build_plan(self.manifest, "brigadir", home))
            self.assertNotIn(secret, serialized)
            self.assertIn(".env", serialized)

    def test_apply_fails_closed(self) -> None:
        with TemporaryDirectory() as temp:
            code = main(
                [
                    "--manifest",
                    str(MANIFEST_PATH),
                    "--agent-id",
                    "jendral",
                    "--agent-home",
                    temp,
                    "--apply",
                ]
            )
            self.assertEqual(code, 3)

    def test_invalid_manifest_is_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text('{"schema": "wrong"}', encoding="utf-8")
            with self.assertRaises(BootstrapError):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
