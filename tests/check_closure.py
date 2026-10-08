"""Reject deferred runtime dependencies in the realized ARM64 closure."""
import re
import sys
from pathlib import Path

FORBIDDEN = re.compile(r"^[^-]+-(?:nix-[0-9]|sops(?:-|$)|age-[0-9]|openssh-|shpool-|codex-|sd-switch-|rustc-|cargo-|go-[0-9]|gcc-[0-9]|clang-[0-9])")


def check(paths):
    return [path for path in paths if FORBIDDEN.search(Path(path).name) and not re.search(r"-gcc-[0-9].*-lib$", Path(path).name)]


if __name__ == "__main__":
    paths = Path(sys.argv[1]).read_text().splitlines()
    if not paths:
        raise SystemExit("Empty closure report")
    rejected = check(paths)
    if rejected:
        raise SystemExit("Deferred or compiler packages in runtime closure:\n" + "\n".join(rejected))
    print(f"Checked {len(paths)} runtime store paths")
