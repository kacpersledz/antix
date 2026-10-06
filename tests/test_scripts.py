"""Isolated script contract tests. Fake identities are never usable credentials."""
import os
import pty
import select
import time
import pathlib
import subprocess
import tempfile
import unittest
REPO = pathlib.Path(__file__).resolve().parents[1]
class Scripts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.repo = self.root / 'repo'
        (self.repo / 'commands').mkdir(parents=True)
        (self.repo / 'commands/common.sh').write_text((REPO/'commands/common.sh').read_text())
        (self.repo / '.sops.yaml').write_text('creation_rules:\n  - path_regex: secrets/.*\n    age: age1test\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.mock('id', 'if [ "$1" = -u ]; then echo '+str(os.getuid())+'; else echo tester; fi')
        self.mock('nix', 'if [ "$1" = --version ]; then echo "nix (Nix) 2.26.3"; else exit 1; fi')
        self.mock('age-keygen', 'if [ "$(cat "$2")" = TEST_IDENTITY ]; then echo age1test; else exit 1; fi')
        self.env = dict(os.environ, HOME=str(self.home), ANTIX_PATH=str(self.repo), PATH=str(self.bin)+':'+os.environ['PATH'])
    def tearDown(self): self.tmp.cleanup()
    def mock(self, name, body):
        p=self.bin/name
        p.write_text('#!/bin/sh\n'+body+'\n')
        p.chmod(0o755)
    def run_script(self, name, *args):
        return subprocess.run(['bash',str(REPO/'commands'/('antix-'+name+'.sh')),*args],env=self.env,capture_output=True,text=True)
    def key(self, value):
        p=self.home/'.config/sops/age/keys.txt'
        p.parent.mkdir(parents=True)
        p.write_text(value)
        return p
    def test_malformed_existing_refused(self):
        p=self.key('MALFORMED')
        self.assertNotEqual(self.run_script('secrets-bootstrap').returncode,0)
        self.assertEqual(p.read_text(),'MALFORMED')
    def test_correct_identity_idempotent(self):
        self.key('TEST_IDENTITY')
        self.assertEqual(self.run_script('secrets-bootstrap').returncode,0)
        self.assertEqual(self.run_script('secrets-bootstrap').returncode,0)
    def test_recipient_mismatch(self):
        self.key('TEST_IDENTITY')
        (self.repo/'.sops.yaml').write_text('  age: age1other\n')
        self.assertNotEqual(self.run_script('secrets-bootstrap').returncode,0)
    def test_symlink_refused(self):
        p=self.key('TEST_IDENTITY');p.rename(p.with_name('other'));p.symlink_to('other')
        self.assertNotEqual(self.run_script('secrets-bootstrap').returncode,0)
    def test_enroll_refuses_existing_payload(self):
        self.key('TEST_IDENTITY')
        (self.repo/'secrets').mkdir()
        p=self.repo/'secrets/github-ssh-key.yaml';p.write_text('existing encrypted material')
        self.assertNotEqual(self.run_script('secrets-enroll').returncode,0)
        self.assertEqual(p.read_text(),'existing encrypted material')
    def test_codex_named_attach(self):
        self.mock('shpool','printf "%s\\n" "$*"')
        result=self.run_script('codex')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.strip(),'attach --dir . --cmd codex antix-codex')
    def test_doctor_hides_identity(self):
        self.key('TEST_IDENTITY')
        r=self.run_script('doctor')
        self.assertNotIn('TEST_IDENTITY',r.stdout+r.stderr)
    def test_doctor_reports_configured_author_without_values(self):
        self.mock('git', 'case "$*" in *user.name) echo MOCK_AUTHOR ;; *user.email) echo mock@example.test ;; esac')
        r=self.run_script('doctor')
        self.assertIn('PASS Git author identity',r.stdout)
        self.assertNotIn('MOCK_AUTHOR',r.stdout+r.stderr)
        self.assertNotIn('mock@example.test',r.stdout+r.stderr)
    def test_doctor_reports_missing_author(self):
        self.mock('git','exit 1')
        r=self.run_script('doctor')
        self.assertIn('FAIL Git author identity',r.stdout)
    def restore(self, fixture):
        # A controlling pseudoterminal exercises /dev/tty and hidden input, even
        # though the installer normally reads its shell source from a pipe.
        pid, fd = pty.fork()
        if pid == 0:
            os.execve('/bin/bash', ['bash', str(REPO/'commands/antix-secrets-bootstrap.sh')], self.env)
        output=b''
        sent=False
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            readable,_,_=select.select([fd],[],[],0.1)
            if readable:
                try: chunk=os.read(fd,4096)
                except OSError: break
                if not chunk: break
                output+=chunk
                if not sent and b'Bitwarden:' in output:
                    os.write(fd,(fixture+'\n').encode());sent=True
        else:
            os.kill(pid,9)
        _, status=os.waitpid(pid,0)
        os.close(fd)
        return os.waitstatus_to_exitcode(status),output.decode()
    def test_hidden_restore_installs_atomically(self):
        status, output=self.restore('TEST_IDENTITY')
        self.assertEqual(status,0,output)
        self.assertNotIn('TEST_IDENTITY',output)
        p=self.home/'.config/sops/age/keys.txt'
        self.assertEqual(p.read_text(),'TEST_IDENTITY\n')
        self.assertEqual(p.stat().st_mode & 0o777,0o600)
        self.assertEqual(p.parent.stat().st_mode & 0o777,0o700)
    def test_malformed_paste_not_installed(self):
        status,output=self.restore('MALFORMED_INPUT')
        self.assertNotEqual(status,0)
        self.assertNotIn('MALFORMED_INPUT',output)
        self.assertFalse((self.home/'.config/sops/age/keys.txt').exists())
    def test_mismatched_paste_not_installed(self):
        (self.repo/'.sops.yaml').write_text('  age: age1other\n')
        status,output=self.restore('TEST_IDENTITY')
        self.assertNotEqual(status,0)
        self.assertFalse((self.home/'.config/sops/age/keys.txt').exists())
    def enroll_fixture(self, plaintext=False, corrupt=False):
        self.key('TEST_IDENTITY')
        (self.repo/'secrets').mkdir()
        placeholder=(REPO/'secrets/enrollment-placeholder.txt').read_text()
        (self.repo/'secrets/enrollment-placeholder.txt').write_text(placeholder)
        destination=self.repo/'secrets/github-ssh-key.yaml'
        destination.write_text(placeholder)
        ssh_dir=self.home/'.ssh';ssh_dir.mkdir()
        (ssh_dir/'antix_github_ed25519').write_text('TEST_PRIVATE_PAYLOAD\n')
        (ssh_dir/'antix_github_ed25519.pub').write_text('ssh-ed25519 TEST_PUBLIC_DATA\n')
        self.mock('ssh-keygen','echo "ssh-ed25519 TEST_PUBLIC_DATA"')
        payload='BEGIN OPENSSH PRIVATE KEY' if plaintext else 'ENC[FAKE_TEST_CIPHERTEXT]'
        decrypted='CORRUPTED_PAYLOAD' if corrupt else 'TEST_PRIVATE_PAYLOAD'
        self.mock('sops', 'if [ "$1" = --encrypt ]; then printf "github_ssh_private_key: '+payload+'\\nsops:\\n"; else printf "'+decrypted+'\\n"; fi')
        return destination,placeholder
    def test_enrollment_verifies_roundtrip(self):
        destination,_=self.enroll_fixture()
        r=self.run_script('secrets-enroll','--use-existing-key')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotIn('TEST_PRIVATE_PAYLOAD',destination.read_text()+r.stdout+r.stderr)
        self.assertIn('sops:',destination.read_text())
    def test_plaintext_sops_output_refused(self):
        destination,placeholder=self.enroll_fixture(plaintext=True)
        r=self.run_script('secrets-enroll','--use-existing-key')
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(destination.read_text(),placeholder)
    def test_roundtrip_mismatch_refused(self):
        destination,placeholder=self.enroll_fixture(corrupt=True)
        r=self.run_script('secrets-enroll','--use-existing-key')
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(destination.read_text(),placeholder)
    def test_shell_syntax(self):
        for path in [*REPO.glob('*.sh'),*REPO.glob('commands/*.sh')]:
            self.assertEqual(subprocess.run(['bash','-n',str(path)]).returncode,0,path)
if __name__ == '__main__': unittest.main()
