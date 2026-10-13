"""Publication checks use disposable repositories and inert synthetic strings."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCANNER = Path(__file__).resolve().parents[1] / "scripts" / "check_publication.py"


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.git("init", "--quiet")
        self.git("config", "user.name", "Publication test")
        self.git("config", "user.email", "test@example.invalid")

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.repo), *arguments], check=True, capture_output=True)

    def stage(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        self.git("add", "--", path)
        return target

    def scan(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCANNER), "--repo", str(self.repo), *arguments],
            text=True, capture_output=True,
        )

    def test_safe_code_and_contract_can_be_published(self):
        self.stage("submission/solution.py", "def build(): return None\n")
        self.stage("harness/contract.py", "class Answer: pass\n")
        self.stage("docs/clean notes.md", "No network calls or external credentials are needed.\n")
        self.assertEqual(self.scan().returncode, 0)

    def test_scans_staged_content_even_when_working_file_is_clean(self):
        sensitive = "gh" + "p_" + "SYNTHETIC" * 5
        file = self.stage("config.txt", sensitive)
        file.write_text("clean working tree copy")
        result = self.scan("--index")
        self.assertEqual(result.returncode, 1)
        self.assertIn("GitHub token", result.stderr)
        self.assertNotIn(sensitive, result.stderr + result.stdout)

    def test_untracked_local_inputs_are_not_published(self):
        self.stage("README.md", "Public documentation")
        (self.repo / ".env").write_text("local-only")
        self.assertEqual(self.scan().returncode, 0)

    def test_denies_private_inputs_and_generated_artifacts(self):
        paths = (
            "snapshots/001/page.md", "snapshots_zip/input.txt", "eval/questions.json",
            "starter/solution.py", "harness/scoring.py", "results/report.json", ".env.local",
            "secrets/settings.json", "credentials.json", "private-key.txt", "id_ed25519",
            "web/node_modules/pkg/index.js", "web/dist/index.html", ".venv/bin/python",
            "__pycache__/cache.pyc", "input.zip", "docs/assignment.md", "conversation-transcript.txt",
            "data/innocent-looking.md", "local-data/page.md", ".local-data/input.json",
            ".codex/config.toml", ".agents/notes.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.stage(path, "private fixture")
                result = self.scan()
                self.assertEqual(result.returncode, 1)
                self.assertIn(path, result.stderr)
                self.git("rm", "--cached", "--", path)

    def test_detects_literal_credentials_without_echoing_values(self):
        value = "inert-synthetic-fixture"
        assignments = (
            ('API' + '_KEY', f'"{value}"'),
            ('GH' + '_TOKEN', value),
            ('AWS_SECRET' + '_ACCESS_KEY', value),
            ('DATABASE' + '_PASSWORD', f'"{value}"'),
        )
        for name, literal in assignments:
            with self.subTest(name=name):
                self.stage("config.txt", f'{name} = {literal}\n')
                result = self.scan()
                self.assertEqual(result.returncode, 1)
                self.assertIn("literal credential assignment", result.stderr)
                self.assertNotIn(value, result.stderr)

    def test_detects_embedded_url_credentials_and_private_keys(self):
        markers = (
            "https://" + "fixture:inert-value" + "@example.invalid/",
            "-----BEGIN " + "RSA PRIVATE KEY-----",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.stage("config.txt", marker)
                result = self.scan()
                self.assertEqual(result.returncode, 1)
                self.assertNotIn(marker, result.stderr)

    def test_detects_high_confidence_token_formats(self):
        markers = (
            "sk" + "-" + "SYNTHETIC" * 5,
            "github" + "_pat_" + "SYNTHETIC" * 5,
            "xox" + "b-" + "SYNTHETIC" * 5,
            "AK" + "IA" + "X" * 16,
        )
        for marker in markers:
            with self.subTest(prefix=marker[:4]):
                self.stage("config.txt", marker)
                self.assertEqual(self.scan().returncode, 1)

    def test_environment_example_accepts_only_placeholders(self):
        self.stage(".env.example", "# No credentials required\nOPTIONAL_VALUE=\nEXAMPLE=replace_me\n")
        self.assertEqual(self.scan().returncode, 0)
        self.stage(".env.example", "OPTIONAL_VALUE=inert-but-nonplaceholder\n")
        self.assertEqual(self.scan().returncode, 1)

    def test_dynamic_credential_lookup_and_query_words_are_allowed(self):
        name = "API" + "_KEY"
        self.stage("config.py", f'{name} = os.environ.get("OPTIONAL_KEY")\n')
        self.stage("README.md", "The index stores each token. Password reset instructions are searchable.\n")
        self.assertEqual(self.scan().returncode, 0)

    def test_revision_scan_reads_commit_not_working_tree(self):
        self.stage("README.md", "Safe committed documentation")
        self.git("commit", "--quiet", "-m", "test: create safe fixture")
        self.stage(".env", "local fixture")
        self.assertEqual(self.scan("--ref", "HEAD").returncode, 0)
        self.assertEqual(self.scan("--index").returncode, 1)

    def test_symlink_is_not_publishable(self):
        (self.repo / "linked-data").symlink_to("/nonexistent/private-input")
        self.git("add", "linked-data")
        self.assertIn("only regular files", self.scan().stderr)


if __name__ == "__main__":
    unittest.main()
