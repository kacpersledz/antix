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

    def test_group_boundary_stops_before_activation(self):
        self.mock('id', 'case "$1" in -u) echo 1000 ;; -un) echo droid ;; -nG) echo droid ;; esac')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('membership is not active', result.stderr)
        self.assertNotIn('activation', self.log.read_text())
        self.assertEqual((self.home/'.config/nix/antix.conf').read_text(), SETTINGS)

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

    def test_rebuild_uses_runtime_identity_and_direct_activation(self):
        activation = self.root/'activation'
        activation.mkdir()
        script = activation/'activate'
        script.write_text('#!/bin/sh\nprintf "activated\\n" >> "$CALLS"\n')
        script.chmod(0o755)
        self.mock('nix', 'printf "%s|%s|%s\\n" "$ANTIX_USER" "$ANTIX_HOME" "$*" >> "$CALLS"\nprintf "%s\\n" "'+str(activation)+'"')
        result = subprocess.run(['bash', str(REPO/'commands/antix-rebuild.sh')], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text()
        self.assertIn('droid|'+str(self.home), calls)
        self.assertIn('--impure --no-update-lock-file --no-link --print-out-paths', calls)
        self.assertIn('homeConfigurations.antix.activationPackage', calls)
        self.assertIn('activated', calls)
