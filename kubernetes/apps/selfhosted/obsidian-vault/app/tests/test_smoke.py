"""Run every job script the way its CronJob does: `python3 -I /scripts/<name>.py <vault>`.

Isolated mode (-I) leaves the script's own folder off sys.path, so a script that imports
vaultlib without first inserting its folder dies with ModuleNotFoundError in the pod while
working fine in a plain local run. To match the pod, the scripts run from a copy of what
the ConfigMap holds (only the files kustomization.yaml lists), from another working
directory, with an empty environment and an empty vault folder.

With no .stfolder marker in the vault and no service URLs or keys set, every script prints
a line and returns before doing any work, so nothing here reaches the network. As a second
guard the proxy variables point at a closed local port: a request would fail at once
instead of leaving the machine.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import APP_DIR, RESOURCES

LISTED = re.findall(r"^\s*-\s+\./resources/(\S+?)\s*$", (APP_DIR / "kustomization.yaml").read_text(), re.M)
RUN_BY_JOBS = sorted(set(re.findall(r"python3 -I /scripts/([\w.-]+\.py)", (APP_DIR / "helmrelease.yaml").read_text())))
ENV = {"PATH": "/usr/bin:/bin", "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9"}
BROKEN = re.compile(r"Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|SyntaxError")


class ConfigMap(unittest.TestCase):
    def test_every_script_is_in_the_configmap(self):
        on_disk = sorted(p.name for p in RESOURCES.glob("*.py"))
        self.assertTrue(on_disk)
        self.assertEqual([n for n in on_disk if n not in LISTED], [],
                         "in resources/ but not in kustomization.yaml's configMapGenerator: never reaches the pod")

    def test_every_configmap_file_exists(self):
        self.assertEqual([n for n in LISTED if not (RESOURCES / n).is_file()], [])
        self.assertEqual(len(LISTED), len(set(LISTED)))

    def test_every_script_a_job_runs_is_in_the_configmap(self):
        self.assertTrue(RUN_BY_JOBS, "found no `python3 -I /scripts/<name>.py` in helmrelease.yaml")
        self.assertEqual([n for n in RUN_BY_JOBS if n not in LISTED], [])


class IsolatedMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.scripts, cls.vault, cls.cwd = root / "scripts", root / "vault", root / "cwd"
        for d in (cls.scripts, cls.vault, cls.cwd):
            d.mkdir()
        for name in LISTED:
            if (RESOURCES / name).is_file():
                shutil.copy(RESOURCES / name, cls.scripts / name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_python(self, *args):
        return subprocess.run([sys.executable, "-I", *args], cwd=self.cwd, env=ENV, timeout=60,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)

    def check(self, name, proc):
        out = proc.stdout + proc.stderr
        self.assertNotRegex(out, BROKEN, f"{name} does not start under `python3 -I`:\n{out}")
        self.assertEqual(proc.returncode, 0, f"{name} exited {proc.returncode} on an empty vault:\n{out}")

    def test_job_scripts_start_under_python_I(self):
        for name in RUN_BY_JOBS:
            with self.subTest(script=name):
                self.check(name, self.run_python(str(self.scripts / name), str(self.vault)))
        self.assertEqual(list(self.vault.iterdir()), [], "a script wrote to a vault with no .stfolder marker")

    def test_helper_modules_import_under_python_I(self):
        # vaultlib, librarian and processor are not run by a job: a job script imports them
        # after putting /scripts on sys.path, so import them the same way.
        helpers = [n for n in LISTED if n.endswith(".py") and n not in RUN_BY_JOBS]
        for name in helpers:
            with self.subTest(module=name):
                self.assertTrue(name[:-3].isidentifier(), f"{name} is not run by any job and cannot be imported")
                code = f"import sys; sys.path.insert(0, {str(self.scripts)!r}); import {name[:-3]}"
                self.check(name, self.run_python("-c", code))


if __name__ == "__main__":
    unittest.main()
