import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "lsplain"


class LsplainTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_explains_real_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            path.write_text("hello\n", encoding="utf-8")
            path.chmod(0o644)
            result = self.run_cli(str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("regular file", result.stdout)
            self.assertIn("Permissions : 0644", result.stdout)
            self.assertIn("Owner/group", result.stdout)
            self.assertIn("Type / size", result.stdout)
            self.assertIn("ACLs, macOS privacy controls and other system rules may change actual access", result.stdout)

    def test_directory_write_explanation_mentions_traverse_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shared"
            path.mkdir()
            path.chmod(0o622)  # write without execute is not enough to alter entries
            result = self.run_cli(str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("changing entries also needs traverse permission", result.stdout)

    def test_contents_view_is_compact_and_hides_dotfiles_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            root.mkdir()
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            (root / ".env").write_text("SECRET=value\n", encoding="utf-8")
            (root / "src").mkdir()
            result = self.run_cli("--contents", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("README.md", result.stdout)
            self.assertIn("src/", result.stdout)
            self.assertNotIn(".env", result.stdout)
            self.assertIn("FOR YOU", result.stdout)
            all_result = self.run_cli("--contents", "--all", str(root))
            self.assertEqual(all_result.returncode, 0, all_result.stderr)
            self.assertIn(".env", all_result.stdout)

    def test_preview_warns_if_proposed_mode_is_world_writable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            path.write_text("hello\n", encoding="utf-8")
            result = self.run_cli("chmod", "777", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("proposed mode: others have write permission", result.stdout)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_help_documents_commands_that_exist(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("lsplain --contents .", result.stdout)
        self.assertIn("lsplain chmod -R 755 ./project", result.stdout)

    def test_preview_uses_correct_grammar_for_others(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            path.write_text("hello\n", encoding="utf-8")
            path.chmod(0o644)
            result = self.run_cli("chmod", "755", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("others gain execute permission", result.stdout)
            self.assertNotIn("others gains execute permission", result.stdout)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_preview_does_not_change_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "script.sh"
            path.write_text("echo hi\n", encoding="utf-8")
            path.chmod(0o644)
            result = self.run_cli("chmod", "755", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CHMOD PREVIEW", result.stdout)
            self.assertIn("644", result.stdout)
            self.assertIn("755", result.stdout)
            self.assertIn("not executed", result.stdout)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)

    def test_recursive_preview_includes_nested_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            root.mkdir()
            nested = root / "src"
            nested.mkdir()
            file_path = nested / "main.py"
            file_path.write_text("print('hi')\n", encoding="utf-8")
            result = self.run_cli("chmod", "-R", "755", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(root), result.stdout)
            self.assertIn(str(nested), result.stdout)
            self.assertIn(str(file_path), result.stdout)
            self.assertEqual(stat.S_IMODE(file_path.stat().st_mode), 0o644)


    def test_preview_matches_real_chmod_for_a_regular_file(self):
        with tempfile.TemporaryDirectory() as folder:
            preview_path = Path(folder) / "preview.txt"
            ground_truth_path = Path(folder) / "ground-truth.txt"
            preview_path.write_text("preview\n", encoding="utf-8")
            ground_truth_path.write_text("truth\n", encoding="utf-8")
            preview_path.chmod(0o644)
            ground_truth_path.chmod(0o644)

            result = self.run_cli("chmod", "755", str(preview_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            # Actual chmod is restricted to a disposable temporary file.
            ground_truth_path.chmod(0o755)
            actual = stat.S_IMODE(ground_truth_path.stat().st_mode) & 0o777
            self.assertEqual(actual, 0o755)
            self.assertIn("644", result.stdout)
            self.assertIn("755", result.stdout)
            self.assertEqual(stat.S_IMODE(preview_path.stat().st_mode) & 0o777, 0o644)

    def test_bad_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.txt"
            path.write_text("hello\n", encoding="utf-8")
            result = self.run_cli("chmod", "888", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertIn("octal", result.stderr)

    def test_missing_path_fails_cleanly(self):
        result = self.run_cli("/this/path/should/not/exist/lsplain-test")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot inspect", result.stderr)

    def test_symlink_is_not_followed_in_recursive_preview(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder) / "project"
            root.mkdir()
            target = Path(outside) / "target.txt"
            target.write_text("keep permissions", encoding="utf-8")
            target.chmod(0o600)
            link = root / "external-link"
            link.symlink_to(target)
            result = self.run_cli("chmod", "-R", "755", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SKIP", result.stdout)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
