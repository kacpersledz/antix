import unittest
from check_closure import check


class Closure(unittest.TestCase):
    def test_rejects_deferred_tools_but_accepts_runtime_libraries(self):
        forbidden = ['nix-2.28', 'sops-3.10', 'age-1.2', 'openssh-10', 'shpool-0.8', 'codex-0.1', 'sd-switch-0.5', 'rustc-1.89', 'cargo-1.89', 'go-1.24', 'gcc-14', 'clang-20']
        paths = ['/nix/store/hash-' + name for name in forbidden]
        self.assertEqual(check(paths), paths)
        self.assertEqual(check(['/nix/store/hash-gcc-14-lib', '/nix/store/hash-gcc-14-libgcc', '/nix/store/hash-git-2.50']), [])
