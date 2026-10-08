"""Mock Nix only; never mutate the real store. Exercise real interactive Zsh."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class ZshIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root/'home'
        self.home.mkdir()
        self.bin = self.root/'bin'
        self.bin.mkdir()
        self.activation = self.root/'activation'
        self.files = self.activation/'home-files'
        self.files.mkdir(parents=True)
        self.repo = self.root/'repo'
        (self.repo/'commands').mkdir(parents=True)
        for name in ('common.sh', 'zsh-checks.sh'):
            shutil.copy(REPO/'commands'/name, self.repo/'commands'/name)
        self.calls = self.root/'calls'
        self.marker = self.root/'bad-hash'
        self.omz = self.root/'oh-my-zsh'
        self.omz.mkdir()
        (self.omz/'oh-my-zsh.sh').write_text('function omz() { :; }; function git_prompt_info() { :; }\n')
        self.rc = f'plugins=(git)\nZSH_THEME="clean"\nZSH="{self.omz}"\nsource $ZSH/oh-my-zsh.sh\n'
        self.zshenv = 'export PATH="$HOME/.nix-profile/bin:$PATH"\n# hm-session-vars.sh\n'
        self.valid_files()
        self.mock('id', 'case "$1" in -u) echo 1000 ;; *) echo droid ;; esac')
        self.mock('nix-store', '''echo "verify $*" >> "$CALLS"
[ "$1" = --verify-path ] || exit 90
[ ! -e "$BAD_HASH" ]''')
        self.mock('nix', '''echo "$ANTIX_USER|$ANTIX_HOME|$*" >> "$CALLS"
case " $* " in *" --repair "*)
  [ "${REPAIR_FAIL:-0}" = 0 ] || exit 32
  cp "$GOOD_RC" "$ACTIVATION/home-files/.zshrc"
  cp "$GOOD_ENV" "$ACTIVATION/home-files/.zshenv"
  rm -f "$BAD_HASH"
  ;; esac
printf '%s\n' "$ACTIVATION"''')
        (self.root/'good-rc').write_text(self.rc)
        (self.root/'good-env').write_text(self.zshenv)
        script = self.activation/'activate'
        script.write_text('''#!/bin/sh
echo activated >> "$CALLS"
mkdir -p "$HOME/.nix-profile/bin"
ln -sfn "$ZSH_BIN" "$HOME/.nix-profile/bin/zsh"
ln -sfn "$ACTIVATION/home-files/.zshrc" "$HOME/.zshrc"
ln -sfn "$ACTIVATION/home-files/.zshenv" "$HOME/.zshenv"
if [ "${POST_CORRUPT:-0}" = 1 ] && [ ! -e "$ACTIVATION/once" ]; then
  touch "$ACTIVATION/once"
  : > "$ACTIVATION/home-files/.zshrc"
fi
''')
        script.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), ANTIX_PATH=str(self.repo),
                        PATH=str(self.bin)+':'+os.environ['PATH'], CALLS=str(self.calls),
                        ACTIVATION=str(self.activation), BAD_HASH=str(self.marker),
                        GOOD_RC=str(self.root/'good-rc'), GOOD_ENV=str(self.root/'good-env'),
                        ZSH_BIN=shutil.which('zsh') or '/missing-zsh')

    def tearDown(self):
        self.tmp.cleanup()

    def valid_files(self):
        (self.files/'.zshrc').write_text(self.rc)
        (self.files/'.zshenv').write_text(self.zshenv)

    def mock(self, name, body):
        path = self.bin/name
        path.write_text('#!/bin/sh\n'+body+'\n')
        path.chmod(0o755)

    def rebuild(self):
        return subprocess.run(['bash', str(REPO/'commands/antix-rebuild.sh')],
                              env=self.env, capture_output=True, text=True)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('PASS interactive Zsh', result.stdout)

    def test_valid_and_repeated_rebuild_idempotent(self):
        for _ in range(2):
            self.assert_ok(self.rebuild())
        calls = self.calls.read_text()
        self.assertNotIn('--repair', calls)
        self.assertEqual(calls.count('activated'), 2)
        self.assertIn('droid|'+str(self.home), calls)
        self.assertIn('--impure --no-update-lock-file --no-link --print-out-paths', calls)
        self.assertIn('homeConfigurations.antix.activationPackage', calls)
        self.assertEqual((self.home/'.zshrc').read_text(), self.rc)

    def test_empty_rc_repaired_once_before_activation(self):
        (self.files/'.zshrc').write_text('')
        self.assert_ok(self.rebuild())
        calls = self.calls.read_text()
        self.assertEqual(calls.count('--repair'), 1)
        self.assertLess(calls.index('--repair'), calls.index('activated'))
        self.assert_ok(self.rebuild())
        self.assertEqual(self.calls.read_text().count('--repair'), 1)

    def test_missing_env_repaired(self):
        (self.files/'.zshenv').unlink()
        self.assert_ok(self.rebuild())

    def test_broken_generated_link_repaired(self):
        (self.files/'.zshrc').unlink()
        (self.files/'.zshrc').symlink_to(self.root/'missing')
        # Simulate Nix replacing its output, not writing through a broken link.
        self.mock('nix', '''echo "$*" >> "$CALLS"
case " $* " in *" --repair "*)
 rm "$ACTIVATION/home-files/.zshrc"
 cp "$GOOD_RC" "$ACTIVATION/home-files/.zshrc" ;; esac
printf '%s\n' "$ACTIVATION"''')
        self.assert_ok(self.rebuild())

    def test_hash_failure_repaired_and_reverified(self):
        self.marker.touch()
        self.assert_ok(self.rebuild())
        calls = self.calls.read_text()
        self.assertEqual(calls.count('--repair'), 1)
        self.assertGreater(calls.count('--verify-path'), 4)

    def test_repair_failure_blocks_activation_and_success(self):
        (self.files/'.zshrc').write_text('')
        self.env['REPAIR_FAIL'] = '1'
        result = self.rebuild()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Nix repair failed', result.stderr)
        self.assertNotIn('activated', self.calls.read_text())
        self.assertNotIn('verified.', result.stdout)

    def test_successful_command_with_unrepaired_hash_fails(self):
        self.marker.touch()
        self.mock('nix', 'echo "$*" >> "$CALLS"; printf "%s\\n" "$ACTIVATION"')
        result = self.rebuild()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls.read_text().count('--repair'), 1)
        self.assertNotIn('activated', self.calls.read_text())

    def test_post_activation_corruption_repaired_and_reactivated(self):
        self.env['POST_CORRUPT'] = '1'
        self.assert_ok(self.rebuild())
        self.assertEqual(self.calls.read_text().count('activated'), 2)
        self.assertEqual(self.calls.read_text().count('--repair'), 1)

    def test_corruption_before_and_after_activation_stops_at_one_repair(self):
        (self.files/'.zshrc').write_text('')
        self.env['POST_CORRUPT'] = '1'
        result = self.rebuild()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls.read_text().count('--repair'), 1)
        self.assertIn('after one repair', result.stderr)

    def test_wrong_generated_content_not_accepted(self):
        (self.files/'.zshrc').write_text('ZSH_THEME=wrong\n')
        self.env['REPAIR_FAIL'] = '1'
        result = self.rebuild()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('lacks expected Oh My Zsh', result.stderr)

    def test_runtime_failure_not_masked_by_valid_evaluation_or_hash(self):
        (self.omz/'oh-my-zsh.sh').write_text(': # function never defined\n')
        result = self.rebuild()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Interactive Zsh initialization failed', result.stderr)
        self.assertNotIn('--repair', self.calls.read_text())

    def test_isolated_startup_ignores_inherited_zdotdir_and_hm_sentinel(self):
        self.env.update(ZDOTDIR='/missing', __HM_ZSH_SESS_VARS_SOURCED='1', ZSH_THEME='wrong')
        self.assert_ok(self.rebuild())

    def test_noninteractive_zsh_does_not_source_rc(self):
        self.assert_ok(self.rebuild())
        result = subprocess.run([self.env['ZSH_BIN'], '-c',
                                 '(( $+functions[omz] == 0 )) && print noninteractive'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'noninteractive\n')

    def test_doctor_accepts_socket_activation_and_reports_corrupt_artifacts(self):
        self.assert_ok(self.rebuild())
        self.mock('systemctl', 'case "$*" in *nix-daemon.socket) exit 0 ;; *) exit 3 ;; esac')
        result = subprocess.run(['bash', str(REPO/'commands/antix-doctor.sh')],
                                env=self.env, capture_output=True, text=True)
        self.assertIn('PASS nix-daemon socket/service', result.stdout)
        self.assertIn('PASS generated Zsh integrity/content', result.stdout)
        self.assertIn('PASS interactive Oh My Zsh (clean/git)', result.stdout)
        self.marker.touch()
        result = subprocess.run(['bash', str(REPO/'commands/antix-doctor.sh')],
                                env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL generated Zsh integrity/content', result.stdout)
        self.assertIn('Nix integrity verification failed', result.stderr)
        self.assertNotIn('--repair', self.calls.read_text())
