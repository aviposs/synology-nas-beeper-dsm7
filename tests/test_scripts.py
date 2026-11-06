import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scripts = self.root / "volume1/scripts/ups beeper"
        self.scripts.mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.version = self.root / "VERSION"
        self.version.write_text('majorversion="7"\n')
        self.users = self.root / "upsd.users"
        self.users.write_text("[existing]\n\tpassword = existing\n")
        self.other_users = self.root / "other-upsd.users"
        self.state = self.root / "state"
        self.state.write_text("enabled\n")
        self.log = self.root / "commands"
        self.unused_install = self.root / "legacy-install"
        self.config = self.scripts / "ups_beeper.conf"
        self.config.write_text(
            'UPSD_USER="beeper"\nUPSD_PWD="test-password"\n'
            'INSTALL_DIR="{}"\n'.format(self.unused_install)
        )

        # Redirect only DSM system files; never edit the host's UPS configuration.
        for name in ("restore.sh", "ups_beeper_control.sh", "upscmd.py"):
            text = (REPO / name).read_text()
            text = text.replace("/etc.defaults/VERSION", str(self.version))
            text = text.replace("/usr/syno/etc/ups/upsd.users", str(self.users))
            text = text.replace("/etc/ups/upsd.users", str(self.other_users))
            (self.scripts / name).write_text(text)

        self.env = os.environ.copy()
        self.env.pop("UPSD_USER", None)
        self.env.pop("UPSD_PWD", None)
        self.env.update(
            PATH=str(self.bin) + os.pathsep + self.env["PATH"],
            PYTHONPATH=str(self.bin),
            TEST_STATE=str(self.state),
            TEST_LOG=str(self.log),
        )
        self.command("id", 'echo "${TEST_UID:-0}"')
        self.command("sleep", ":")
        self.command("date", 'echo "1 12 00"')
        self.command("upsc", 'cat "$TEST_STATE"')
        self.command(
            "synosystemctl",
            'echo "synosystemctl $*" >> "$TEST_LOG"\nexit "${TEST_RESTART_EXIT:-0}"',
        )
        self.command(
            "synoservice",
            'echo "synoservice $*" >> "$TEST_LOG"\nexit "${TEST_RESTART_EXIT:-0}"',
        )
        self.command(
            "python",
            'echo "python $*" >> "$TEST_LOG"\nexec python3 "$@"',
        )
        (self.bin / "telnetlib.py").write_text(
            'import os\n'
            'class Telnet:\n'
            '    def __init__(self, host, port):\n'
            '        assert (host, port) == ("127.0.0.1", 3493)\n'
            '    def write(self, data):\n'
            '        text = data.decode("utf-8").strip()\n'
            '        with open(os.environ["TEST_LOG"], "a") as log:\n'
            '            log.write(text + "\\n")\n'
            '        if text.startswith("INSTCMD ups "):\n'
            '            path = os.environ["TEST_STATE"]\n'
            '            with open(path) as state:\n'
            '                old = state.read().strip()\n'
            '            cmd = text.split()[-1]\n'
            '            new = {"beeper.enable": "enabled", "beeper.disable": "disabled"}.get(cmd)\n'
            '            if cmd == "beeper.toggle":\n'
            '                new = "disabled" if old == "enabled" else "enabled"\n'
            '            with open(path, "w") as state:\n'
            '                state.write(new + "\\n")\n'
            '    def read_until(self, expected, timeout):\n'
            '        return b"OK\\n"\n'
            '    def read_all(self):\n'
            '        return b"OK Goodbye\\n"\n'
            '    def close(self):\n'
            '        pass\n'
        )

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o700)

    def run_script(self, name, *args, success=True):
        interpreter = "python3" if name.endswith(".py") else "bash"
        result = subprocess.run(
            [interpreter, str(self.scripts / name)] + list(args),
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_restore_runs_adjacent_scripts_without_installing_or_modifying_them(self):
        before = {path.name: path.read_bytes() for path in self.scripts.iterdir()}
        original_users = self.users.read_bytes()
        self.run_script("restore.sh", "disable")
        self.assertIn("[beeper]", self.users.read_text())
        self.assertIn("password = test-password", self.users.read_text())
        self.assertIn("beeper.toggle", self.users.read_text())
        self.assertEqual(Path(str(self.users) + ".bak").read_bytes(), original_users)
        self.assertEqual(self.state.read_text().strip(), "disabled")
        self.assertIn("synosystemctl restart ups-usb", self.log.read_text())
        self.assertIn("USERNAME beeper", self.log.read_text())
        self.assertIn("PASSWORD test-password", self.log.read_text())
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.scripts.iterdir()})
        self.assertFalse(self.unused_install.exists())

    def test_restore_is_idempotent_and_preserves_backup(self):
        self.run_script("restore.sh")
        backup = Path(str(self.users) + ".bak").read_bytes()
        self.run_script("restore.sh")
        self.assertEqual(self.users.read_text().count("[beeper]"), 1)
        self.assertEqual(self.log.read_text().count("restart ups-usb"), 1)
        self.assertEqual(Path(str(self.users) + ".bak").read_bytes(), backup)

    def test_restore_matches_username_literally(self):
        self.config.write_text('UPSD_USER="beeper.test"\nUPSD_PWD="test-password"\n')
        self.users.write_text("[beeperXtest]\n\tpassword = existing\n")
        self.run_script("restore.sh")
        self.assertIn("[beeper.test]", self.users.read_text())
        self.run_script("restore.sh")
        self.assertEqual(self.users.read_text().count("[beeper.test]"), 1)
        self.assertEqual(self.log.read_text().count("restart ups-usb"), 1)

    def test_restore_handles_alternate_users_file(self):
        self.users.rename(self.other_users)
        self.run_script("restore.sh")
        self.assertIn("[beeper]", self.other_users.read_text())

    def test_restore_updates_both_users_files(self):
        shutil.copyfile(self.users, self.other_users)
        self.run_script("restore.sh")
        self.assertIn("[beeper]", self.users.read_text())
        self.assertIn("[beeper]", self.other_users.read_text())
        self.assertEqual(self.log.read_text().count("restart ups-usb"), 1)

    def test_restore_reports_missing_users_file(self):
        self.users.unlink()
        result = self.run_script("restore.sh", success=False)
        self.assertIn("upsd.users not found", result.stdout)

    def test_restore_requires_root(self):
        self.env["TEST_UID"] = "1000"
        result = self.run_script("restore.sh", success=False)
        self.assertIn("must be run as root", result.stdout)
        self.assertNotIn("[beeper]", self.users.read_text())

    def test_restore_reports_service_restart_failure(self):
        self.env["TEST_RESTART_EXIT"] = "1"
        self.run_script("restore.sh", "disable", success=False)
        self.assertEqual(self.state.read_text().strip(), "enabled")
        self.assertNotIn("INSTCMD", self.log.read_text())

    def test_controller_runs_from_unrelated_working_directory(self):
        self.run_script("ups_beeper_control.sh", "disable")
        self.assertEqual(self.state.read_text().strip(), "disabled")
        self.assertIn("INSTCMD ups beeper.toggle", self.log.read_text())

    def test_controller_does_not_toggle_matching_or_unknown_state(self):
        self.run_script("ups_beeper_control.sh", "enable")
        self.assertFalse(self.log.exists())
        self.state.write_text("unknown\n")
        self.run_script("ups_beeper_control.sh", "disable", success=False)
        self.assertFalse(self.log.exists())

    def test_dsm6_uses_python_and_explicit_commands(self):
        self.version.write_text('majorversion="6"\n')
        self.run_script("restore.sh", "disable")
        self.assertIn("synoservice --restart ups-usb", self.log.read_text())
        self.assertIn("python " + str(self.scripts / "upscmd.py"), self.log.read_text())
        self.assertIn("INSTCMD ups beeper.disable", self.log.read_text())

    def test_curtime_and_enable(self):
        self.state.write_text("disabled\n")
        self.run_script("restore.sh", "curtime")
        self.assertEqual(self.state.read_text().strip(), "enabled")

    def test_missing_config_fails_for_both_shell_scripts(self):
        self.config.unlink()
        for name in ("restore.sh", "ups_beeper_control.sh"):
            with self.subTest(name=name):
                result = self.run_script(name, "disable", success=False)
                self.assertIn("Missing ", result.stdout)

    def test_invalid_credentials_fail_before_contacting_ups(self):
        for user in ("", "<upsd_username>", "bad user", "bad[", "bad]", "bad'", "bad\\name"):
            with self.subTest(user=user):
                quoted_user = user.replace("\\", "\\\\")
                self.config.write_text('UPSD_USER="{}"\nUPSD_PWD="test-password"\n'.format(quoted_user))
                self.run_script("restore.sh", success=False)
                self.run_script("ups_beeper_control.sh", "disable", success=False)
                self.assertFalse(self.log.exists())
                self.assertNotIn("[beeper]", self.users.read_text())

    def test_upscmd_requires_credentials_and_supports_environment(self):
        self.run_script("upscmd.py", "beeper.disable", success=False)
        self.assertFalse(self.log.exists())
        self.env.update(UPSD_USER="beeper", UPSD_PWD="test-password")
        self.run_script("upscmd.py", "beeper.disable")
        self.assertEqual(self.state.read_text().strip(), "disabled")


if __name__ == "__main__":
    unittest.main()
