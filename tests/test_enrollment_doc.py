"""Execute the literal documented command with strictly non-credential fake tools."""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PACKAGES = ['nixpkgs#'+name for name in
            ('bash', 'age', 'sops', 'openssh', 'coreutils', 'gnused', 'gnugrep')]


def documented_command():
    matches = re.findall(r'```sh\n(nix[^\n]+)\n```', (REPO/'docs/secrets.md').read_text())
    if len(matches) != 1:
        raise AssertionError('Expected exactly one literal, single-line enrollment command')
    return matches[0]


class EnrollmentDocumentation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root/'home'
        self.home.mkdir()
        self.scratch = self.root/'scratch'
        self.scratch.mkdir()
        self.bin = self.root/'bin'
        self.bin.mkdir()
        # Simulate a pre-existing config in cwd: enrollment must choose its own.
        (self.home/'.sops.yaml').write_text('not the Antix enrollment configuration\n')
        self.env = dict(os.environ, HOME=str(self.home), TMPDIR=str(self.scratch),
                        PATH=str(self.bin)+':'+os.environ['PATH'])
        self.env['SOPS_KMS_ARN'] = 'MOCK_INHERITED_RECIPIENT'
        self.env['SOPS_PGP_FP'] = 'MOCK_INHERITED_RECIPIENT'
        self.mock('nix', '''import os, sys
args = sys.argv[1:]
expected = ['--extra-experimental-features', 'nix-command flakes', 'shell'] + '''+repr(PACKAGES)+''' + ['-c', 'bash', '-c']
assert args[:-1] == expected
os.execv('/bin/bash', ['bash', '-c', args[-1]])
''')
        self.mock('date', '''import sys
assert sys.argv[1:] == ['+%Y%m%d-%H%M%S']
print('20261006-000000')
''')
        self.mock('age-keygen', '''import pathlib, sys
args = sys.argv[1:]
if args[0] == '-o':
    pathlib.Path(args[1]).write_text('MOCK_AGE_IDENTITY_NOT_A_CREDENTIAL\\n')
else:
    assert args[0] == '-y'
    assert pathlib.Path(args[1]).read_text() == 'MOCK_AGE_IDENTITY_NOT_A_CREDENTIAL\\n'
    print('age1test')
''')
        self.mock('ssh-keygen', '''import pathlib, sys
args = sys.argv[1:]
p = pathlib.Path(args[args.index('-f')+1])
if args[0] == '-q':
    assert args == ['-q', '-t', 'ed25519', '-N', '', '-C', 'antix-github', '-f', str(p)]
    p.write_text('MOCK_SSH_PRIVATE_PAYLOAD\\n')
    p.with_name(p.name+'.pub').write_text('ssh-ed25519 MOCK_PUBLIC_DATA\\n')
else:
    assert args == ['-y', '-P', '', '-f', str(p)]
    assert p.read_text().startswith('MOCK_')
    print('ssh-ed25519 MOCK_PUBLIC_DATA')
''')
        self.mock('sops', '''import os, pathlib, sys
args = sys.argv[1:]
config = pathlib.Path(args[args.index('--config')+1])
assert config == pathlib.Path(os.environ['HOME'])/'antix-enrollment-20261006-000000/.sops.yaml'
assert config.read_text() == 'creation_rules:\\n  - path_regex: secrets/[^/]+[.]yaml$\\n    age: age1test\\n'
assert '--input-type' in args and args[args.index('--input-type')+1] == 'yaml'
mode = os.environ.get('ANTIX_TEST_FAILURE', '')
if '--encrypt' in args:
    assert args[args.index('--age')+1] == 'age1test'
    assert args[args.index('--filename-override')+1] == str(config.parent/'secrets/github-ssh-key.yaml')
    assert args[args.index('--output-type')+1] == 'yaml'
    assert not os.environ.get('SOPS_KMS_ARN') and not os.environ.get('SOPS_PGP_FP')
    assert pathlib.Path(args[-1]).read_text() == 'github_ssh_private_key: |\\n  MOCK_SSH_PRIVATE_PAYLOAD\\n'
    print('github_ssh_private_key: '+('BEGIN OPENSSH PRIVATE KEY' if mode == 'plaintext' else 'ENC[MOCK_CIPHERTEXT]'))
    if mode != 'metadata': print('sops:\\n  age: MOCK_ONLY')
else:
    assert '--decrypt' in args
    assert args[args.index('--extract')+1] == '["github_ssh_private_key"]'
    assert args[args.index('--output-type')+1] == 'binary'
    age_file = pathlib.Path(os.environ['SOPS_AGE_KEY_FILE'])
    assert age_file == config.parent/'AGE-SECRET-KEY.txt'
    assert age_file.read_text() == 'MOCK_AGE_IDENTITY_NOT_A_CREDENTIAL\\n'
    print('MOCK_DIFFERENT_PRIVATE_PAYLOAD' if mode == 'comparison' else 'MOCK_SSH_PRIVATE_PAYLOAD')
''')

    def tearDown(self):
        self.tmp.cleanup()

    def mock(self, name, body):
        import sys
        path = self.bin/name
        path.write_text('#!'+sys.executable+'\n'+body)
        path.chmod(0o755)

    def execute(self):
        return subprocess.run(['/bin/bash', '-c', documented_command()], cwd=self.home,
                              env=self.env, text=True, capture_output=True, timeout=10)

    def test_literal_quoting_and_syntax(self):
        command = documented_command()
        body = shlex.split(command)[-1]
        for script in (command, body):
            result = subprocess.run(['/bin/bash', '-n', '-c', script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        if shutil.which('shellcheck'):
            result = subprocess.run(['shellcheck', '-s', 'bash', '-'],
                                    input=body, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_four_artifacts_permissions_and_no_private_output(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)
        out = self.home/'antix-enrollment-20261006-000000'
        expected = {'.sops.yaml', 'AGE-SECRET-KEY.txt', 'github-ssh.pub', 'secrets/github-ssh-key.yaml'}
        self.assertEqual({str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()}, expected)
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        self.assertEqual((out/'AGE-SECRET-KEY.txt').stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertNotIn('MOCK_AGE_IDENTITY_NOT_A_CREDENTIAL', result.stdout+result.stderr)
        self.assertNotIn('MOCK_SSH_PRIVATE_PAYLOAD', result.stdout+result.stderr)
        ciphertext = (out/'secrets/github-ssh-key.yaml').read_text()
        self.assertNotIn('MOCK_SSH_PRIVATE_PAYLOAD', ciphertext)
        self.assertNotIn('BEGIN OPENSSH PRIVATE KEY', ciphertext)
        self.assertIn('sops:', ciphertext)

    def test_existing_output_and_symlink_refused(self):
        out = self.home/'antix-enrollment-20261006-000000'
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    out.symlink_to('absent-output-target')
                else:
                    out.mkdir()
                result = self.execute()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Refusing existing output', result.stderr)
                self.assertEqual(list(self.scratch.iterdir()), [])
                if symlink: out.unlink()
                else: out.rmdir()

    def test_validation_failures_never_install_ciphertext(self):
        for failure in ('plaintext', 'metadata', 'comparison'):
            with self.subTest(failure=failure):
                self.env['ANTIX_TEST_FAILURE'] = failure
                result = self.execute()
                self.assertNotEqual(result.returncode, 0)
                out = self.home/'antix-enrollment-20261006-000000'
                self.assertFalse((out/'secrets/github-ssh-key.yaml').exists())
                self.assertEqual(list(self.scratch.iterdir()), [])
                shutil.rmtree(out)


if __name__ == '__main__':
    unittest.main()
