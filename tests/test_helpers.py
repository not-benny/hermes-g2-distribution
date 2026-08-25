from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


grant = load_script("package_grant.py")
profile_secret = load_script("profile_secret.py")
toolset_policy = load_script("toolset_policy.py")
workflow_inventory = load_script("workflow_inventory.py")


class PackageGrantTests(unittest.TestCase):
    def test_digest_changes_with_authority_bearing_content(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "plugin.json").write_text("{}\n", encoding="utf-8")
            (root / "server.py").write_text("print('one')\n", encoding="utf-8")
            first = grant.canonical_digest(root)
            (root / "server.py").write_text("print('two')\n", encoding="utf-8")
            second = grant.canonical_digest(root)
            self.assertRegex(first, r"^sha256:[0-9a-f]{64}$")
            self.assertNotEqual(first, second)

    def test_generated_caches_do_not_change_digest(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "server.py").write_text("pass\n", encoding="utf-8")
            first = grant.canonical_digest(root)
            cache = root / "__pycache__"
            cache.mkdir()
            (cache / "server.pyc").write_bytes(b"generated")
            self.assertEqual(first, grant.canonical_digest(root))

    def test_expected_digest_rejects_changed_package(self):
        expected = "sha256:" + "a" * 64
        grant.verify_expected_digest(expected, expected)
        with self.assertRaisesRegex(RuntimeError, "release lock"):
            grant.verify_expected_digest("sha256:" + "b" * 64, expected)

    def test_merge_preserves_other_exact_grants_and_replaces_workflow(self):
        existing = (
            '[{"binding":"other:server","digest":"sha256:' + "a" * 64 + '"},'
            '{"binding":"hermes-g2-workflows:workflows","digest":"sha256:'
            + "b" * 64
            + '"}]'
        )
        digest = "sha256:" + "c" * 64
        merged = grant.merged_grants(existing, digest)
        self.assertEqual(merged[0]["binding"], "other:server")
        self.assertEqual(merged[1], {"binding": grant.BINDING, "digest": digest})


class ProfileSecretTests(unittest.TestCase):
    def test_atomic_secret_file_is_owner_only_and_never_returned(self):
        with tempfile.TemporaryDirectory() as raw:
            profile = Path(raw)
            token = "t" * 40
            with mock.patch.dict(os.environ, {profile_secret.KEY: token}, clear=False):
                value, generated = profile_secret._token_from_operator(True)
            self.assertEqual(value, token)
            self.assertFalse(generated)
            path = profile / ".env"
            profile_secret._atomic_write(path, profile_secret._replace_value([], value))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(
                profile_secret._current_value(profile_secret._read_lines(path)), token
            )

    def test_existing_secret_is_preserved_when_other_lines_exist(self):
        lines = ["OTHER=value", "", f"{profile_secret.KEY}=" + "x" * 40]
        self.assertEqual(profile_secret._current_value(lines), "x" * 40)
        replaced = profile_secret._replace_value(lines, "y" * 40)
        self.assertIn("OTHER=value", replaced)
        self.assertEqual(
            sum(line.startswith(profile_secret.KEY + "=") for line in replaced), 1
        )

    def test_short_token_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "at least 32"):
            profile_secret._validate_token("short")


class ToolsetPolicyTests(unittest.TestCase):
    def test_only_approved_global_blocks_are_removed(self):
        existing = '["browser","code_execution","terminal","delegation"]'
        self.assertEqual(
            toolset_policy.remove_disabled(existing, ["browser", "terminal"]),
            ["code_execution", "delegation"],
        )

    def test_invalid_disabled_toolset_shape_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "JSON list of strings"):
            toolset_policy.remove_disabled('{"browser":true}', ["browser"])

    def test_add_enabled_preserves_only_existing_and_approved_names(self):
        result = toolset_policy.add_enabled(
            '["calendar","browser","calendar"]',
            ["browser", "terminal", "file"],
        )
        self.assertEqual(result, ["calendar", "browser", "terminal", "file"])

    def test_add_enabled_rejects_invalid_platform_shape(self):
        with self.assertRaisesRegex(RuntimeError, "platform_toolsets.g2"):
            toolset_policy.add_enabled('{"browser":true}', ["browser"])


class WorkflowInventoryTests(unittest.TestCase):
    @staticmethod
    def _responses(names):
        tools = []
        for name in names:
            tool = {"name": name}
            if name == "g2_kanban_task_create":
                tool.update(
                    {
                        "description": (
                            "Create on an existing Hermes Kanban board, blocked with no assignee, "
                            "and never starts a worker. The current wearer request explicitly names "
                            "the destination. After a missing board ask in a fresh turn; never choose "
                            "a listed board yourself or substitute local Work Tasks."
                        ),
                        "inputSchema": {
                            "required": ["title", "board"],
                            "properties": {"title": {}, "board": {}, "body": {}},
                        },
                    }
                )
            if name == "g2_work_task_add":
                tool["description"] = (
                    "Add to the phone's onboard local Work Tasks board for an ordinary unqualified "
                    "or unnamed board-task request. An incomplete Kanban request must mutate neither "
                    "store. Never use Hermes Kanban."
                )
            tools.append(tool)
        return [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"serverInfo": {"name": "hermes-g2-workflows"}},
            },
            {"jsonrpc": "2.0", "id": 2, "result": {"tools": tools}},
        ]

    def test_reviewed_thirteen_tool_surface_is_accepted(self):
        self.assertEqual(len(workflow_inventory.EXPECTED_TOOLS), 13)
        workflow_inventory.validate_responses(
            self._responses(workflow_inventory.EXPECTED_TOOLS)
        )

    def test_unreviewed_tool_is_rejected(self):
        names = set(workflow_inventory.EXPECTED_TOOLS)
        names.add("g2_raw_call")
        with self.assertRaisesRegex(RuntimeError, "inventory changed"):
            workflow_inventory.validate_responses(self._responses(names))


if __name__ == "__main__":
    unittest.main()
