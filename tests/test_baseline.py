"""Exercise bootstrap boundaries without apt, daemon, secrets or real activation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SETTINGS = '''experimental-features = nix-command flakes
max-jobs = 1
cores = 1
'''


class Baseline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root/'home'
        self.home.mkdir()
        self.bin = self.root/'bin'
        self.bin.mkdir()
        self.repo = self.root/'repo'
        (self.repo/'commands').mkdir(parents=True)
        (self.repo/'commands/common.sh').write_text((REPO/'commands/common.sh').read_text())
        (self.repo/'commands/zsh-checks.sh').write_text((REPO/'commands/zsh-checks.sh').read_text())
        self.log = self.root/'calls'
        self.env = dict(os.environ, HOME=str(self.home), ANTIX_PATH=str(self.repo),
                        PATH=str(self.bin)+':'+os.environ['PATH'], CALLS=str(self.log))
        self.mock('id', 'case "$1" in -u) echo 1000 ;; -un) echo droid ;; -nG) echo "droid nix-users" ;; esac')
        self.mock('uname', 'case "$1" in -s) echo Linux ;; -m) echo aarch64 ;; esac')
        self.mock('sudo', 'printf "sudo %s\\n" "$*" >> "$CALLS"')
        self.mock('dpkg-query', 'echo "install ok installed"')
        self.mock('getent', 'exit 0')
        self.mock('nix', 'exit 0')
        (self.repo/'commands/antix-rebuild.sh').write_text('printf "activation\\n" >> "$CALLS"\n')
        # Any accidental secret or SSH call fails visibly, even with enrolled material.
        (self.repo/'secrets').mkdir()
        (self.repo/'secrets/github-ssh-key.yaml').write_text('encrypted test fixture')
        (self.repo/'commands/antix-secrets-bootstrap.sh').write_text('exit 99\n')
        self.mock('ssh', 'exit 99')
        self.mock('age-keygen', 'exit 99')

    def tearDown(self):
        self.tmp.cleanup()

    def mock(self, name, body):
        path = self.bin/name
        path.write_text('#!/bin/sh\n'+body+'\n')
        path.chmod(0o755)

    def run_bootstrap(self):
        return subprocess.run(['bash', str(REPO/'commands/antix-bootstrap.sh')],
                              env=self.env, text=True, capture_output=True)

    def test_minimal_activation_and_config_idempotency(self):
        config = self.home/'.config/nix'
        config.mkdir(parents=True)
        (config/'nix.conf').write_text('keep-outputs = true\n')
        (config/'antix.conf').write_text('experimental-features = nix-command flakes\n')
        for _ in range(2):
            result = self.run_bootstrap()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((config/'antix.conf').read_text(), SETTINGS)
        self.assertEqual((config/'nix.conf').read_text().count('!include antix.conf'), 1)
        self.assertIn('keep-outputs = true', (config/'nix.conf').read_text())
        calls = self.log.read_text()
        self.assertEqual(calls.count('activation'), 2)
        self.assertNotIn('apt-get install -y age', calls)
        self.assertNotIn('Bitwarden', result.stdout+result.stderr)

    def test_shell_hooks_idempotent_and_preserve_existing_bash_files(self):
        (self.home/'.profile').write_text('export EXISTING_PROFILE=1\n')
        (self.home/'.bashrc').write_text('export EXISTING_BASHRC=1\n')
        for _ in range(2):
            result = self.run_bootstrap()
            self.assertEqual(result.returncode, 0, result.stderr)
        for name, original in (('.profile', 'EXISTING_PROFILE'), ('.bashrc', 'EXISTING_BASHRC')):
            content = (self.home/name).read_text()
            self.assertIn(original, content)
            self.assertEqual(content.count('# >>> antix-shell-init >>>'), 1)
            self.assertEqual(content.count('antix-shell-init.sh'), 1)

    def test_bash_login_priority_and_symlink_safety(self):
        (self.home/'.bash_profile').write_text('export PRIORITY=1\n')
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('antix-shell-init.sh', (self.home/'.bash_profile').read_text())
        self.assertFalse((self.home/'.profile').exists())
        target = self.root/'existing-config'
        target.write_text('unchanged\n')
        (self.home/'.bashrc').unlink()
        (self.home/'.bashrc').symlink_to(target)
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Refusing non-regular or symlinked', result.stderr)
        self.assertEqual(target.read_text(), 'unchanged\n')

    def test_shell_init_skips_noninteractive_bash(self):
        result = subprocess.run(['bash', '-c', '. "$1"; printf "continued\\n"',
                                 '_', str(REPO/'commands/antix-shell-init.sh')],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'continued\n')

    def test_socket_activation_only(self):
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text()
        self.assertIn('systemctl disable nix-daemon.service', calls)
        self.assertIn('systemctl enable --now nix-daemon.socket', calls)
        self.assertIn('nix --extra-experimental-features nix-command store ping --store daemon', calls)
        self.assertIn('systemctl is-active --quiet nix-daemon.socket', calls)
        self.assertNotIn('enable --now nix-daemon.socket nix-daemon.service', calls)

    def test_active_service_inactive_socket_recovered_and_idempotent(self):
        # Reproduce Android Debian's post-install race, including systemd's
        # refusal to listen while the target service is already running.
        self.mock('sudo', """printf 'sudo %s\\n' "$*" >> "$CALLS"
state="${CALLS}.state"
[ -e "$state" ] || printf 'service\\n' > "$state"
current=$(cat "$state")
case "$*" in
  *'daemon-reload'*|*'disable nix-daemon.service'*) exit 0 ;;
  *'is-active --quiet nix-daemon.socket'*) [ "$current" = socket ] ;;
  *'is-active --quiet nix-daemon.service'*) [ "$current" = service ] ;;
  *'stop nix-daemon.service'*) printf 'stopped\\n' > "$state" ;;
  *'enable --now nix-daemon.socket'*|*'start nix-daemon.socket'*)
    [ "$current" != service ] || exit 1
    printf 'socket\\n' > "$state" ;;
  *'nix --extra-experimental-features nix-command store ping --store daemon'*)
    [ "$current" = socket ] ;;
  *) exit 0 ;;
esac""")
        for _ in range(2):
            result = self.run_bootstrap()
            self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text().splitlines()
        self.assertEqual(calls.count('sudo systemctl stop nix-daemon.service'), 1)
        self.assertEqual(calls.count('sudo systemctl disable nix-daemon.service'), 2)
        self.assertEqual(calls.count('sudo nix --extra-experimental-features nix-command store ping --store daemon'), 2)
        self.assertEqual(calls.count('activation'), 2)
        self.assertLess(calls.index('sudo systemctl stop nix-daemon.service'),
                        calls.index('sudo systemctl enable --now nix-daemon.socket'))

    def test_failed_daemon_ping_blocks_activation(self):
        self.mock('sudo', """printf 'sudo %s\\n' "$*" >> "$CALLS"
case "$*" in
  *'nix --extra-experimental-features nix-command store ping --store daemon'*) exit 1 ;;
  *) exit 0 ;;
esac""")
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Nix daemon connection failed', result.stderr)
        self.assertNotIn('activation', self.log.read_text())

    def test_nonzero_start_when_socket_is_active(self):
        self.mock('sudo', """printf 'sudo %s\\n' "$*" >> "$CALLS"
case "$*" in
  *'enable --now nix-daemon.socket'*) exit 1 ;;
  *) exit 0 ;;
esac""")
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('activation', self.log.read_text())

    def test_inactive_socket_retries_then_reports_diagnostics(self):
        self.mock('sudo', """printf 'sudo %s\\n' "$*" >> "$CALLS"
case "$*" in
  *'is-active --quiet nix-daemon.socket'*) exit 3 ;;
  *) exit 0 ;;
esac""")
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        calls = self.log.read_text()
        self.assertIn('systemctl start nix-daemon.socket', calls)
        self.assertIn('journalctl -b -u nix-daemon.socket', calls)
        self.assertNotIn('activation', calls)
        self.assertIn('Nix socket startup failed', result.stderr)

    def test_minimal_config_migration(self):
        config = self.home/'.config/nix'
        config.mkdir(parents=True)
        (config/'antix.conf').write_text(SETTINGS + 'max-substitution-jobs = 2\nhttp-connections = 4\n')
        for _ in range(2):
            result = self.run_bootstrap()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((config/'antix.conf').read_text(), SETTINGS)

    def test_wrappers_disabled_and_deferred_inputs_absent(self):
        self.assertIn('{ ... }: { }', (REPO/'commands/default.nix').read_text())
        active = (REPO/'flake.nix').read_text() + (REPO/'home/default.nix').read_text()
        for forbidden in ('sops-nix', 'unstable', 'shpool', 'codex', 'openssh'):
            self.assertNotIn(forbidden, active)
        self.assertIn('programs.zsh.envExtra', active)
        self.assertNotIn('.codex', active)

    def test_first_run_activates_group_without_relogin(self):
        self.mock('id', 'case "$1" in -u) echo 1000 ;; -un) echo droid ;; -nG) echo droid ;; esac')
        self.mock('sg', """printf 'sg %s\\n' "$*" >> "$CALLS"
[ "$1" = nix-users ] && [ "$2" = -c ] || exit 22
ANTIX_PATH="$ANTIX_PATH" bash "$ANTIX_PATH/commands/antix-rebuild.sh" """)
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text()
        self.assertIn("sg nix-users -c exec bash", calls)
        self.assertIn('activation', calls)
        self.assertEqual((self.home/'.config/nix/antix.conf').read_text(), SETTINGS)

    def test_first_run_group_switch_failure_stops_activation(self):
        self.mock('id', 'case "$1" in -u) echo 1000 ;; -un) echo droid ;; -nG) echo droid ;; esac')
        self.mock('sg', 'exit 31')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Could not rebuild as nix-users', result.stderr)
        self.assertNotIn('activation', self.log.read_text())

    def test_existing_membership_does_not_use_sg(self):
        self.mock('sg', 'exit 31')
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('activation', self.log.read_text())

    def test_root_and_wrong_architecture_refused(self):
        for name, body, message in [('id', 'echo 0', 'normal non-root'),
                                    ('uname', 'echo x86_64', 'aarch64 Linux')]:
            with self.subTest(name=name):
                self.setUpMockIdentity()
                self.mock(name, body)
                result = self.run_bootstrap()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.log.exists())

    def setUpMockIdentity(self):
        self.mock('id', 'case "$1" in -u) echo 1000 ;; -un) echo droid ;; -nG) echo "droid nix-users" ;; esac')

    def test_config_symlinks_and_unexpected_content_refused(self):
        config = self.home/'.config/nix'
        config.mkdir(parents=True)
        target = self.root/'target'
        target.write_text('do not overwrite\n')
        for name in ('nix.conf', 'antix.conf'):
            with self.subTest(name=name):
                path = config/name
                path.symlink_to(target)
                result = self.run_bootstrap()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_text(), 'do not overwrite\n')
                path.unlink()
        before = (config/'nix.conf').read_text() if (config/'nix.conf').exists() else None
        (config/'antix.conf').write_text('unexpected = true\n')
        self.assertNotEqual(self.run_bootstrap().returncode, 0)
        self.assertEqual((config/'antix.conf').read_text(), 'unexpected = true\n')
        after = (config/'nix.conf').read_text() if (config/'nix.conf').exists() else None
        self.assertEqual(before, after)
        self.assertNotIn('activation', self.log.read_text())
