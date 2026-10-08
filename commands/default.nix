# Stage A intentionally exports no wrappers. Invoke repository scripts with bash.
# Future wrappers must specify per-command dependencies; never share a closure
# containing secrets tools, shpool, Codex, or a second Nix client.
{ ... }: { }
