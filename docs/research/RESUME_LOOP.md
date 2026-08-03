# Resume the Polygeist verification loop in tmux (survives disconnection)

The loop's state is all on disk — `docs/research/polygeist-verification.agents.md`,
the templates, the descriptors, and git history. A cold restart resumes from
exactly where it left off. To survive a long disconnect, run claude inside tmux,
which outlives the VSCode-server terminal and SSH.

## One-time launch (in a terminal on this host)

```bash
tmux new -s polygeist      # a detachable session
# inside tmux:
claude                     # start Claude Code interactively
# paste the RESUME PROMPT below as the first message
# once it is running and has armed a ScheduleWakeup, detach with: Ctrl-b then d
```

Re-attach any time: `tmux attach -t polygeist`
Or check the state without attaching:

```bash
tail -40 /home/riftuser/aisec-invariants-mlir/docs/research/polygeist-verification.agents.md
cd /home/riftuser/aisec-invariants-mlir/prototypes/fcvd_ct && uv run fcvd-ct-coverage polygeist
git -C /home/riftuser/aisec-invariants-mlir log --oneline -10
```

## RESUME PROMPT (paste as the first message to the tmux'd claude)

Continue the Polygeist verification loop (autonomous, user away). Read
/home/riftuser/aisec-invariants-mlir/.claude/skills/polygeist-verification/SKILL.md
and FOLLOW IT. Orient via docs/research/polygeist-verification.agents.md (newest
entry's "Next angle" is the plan) and prototypes/fcvd_ct/compilers/polygeist.json.
Do ONE honest step toward it, record it per SKILL §5, commit it, then
ScheduleWakeup (~900s to continue, ~3600s if near a usage limit), passing this
same prompt back. HARD RULES: every verdict is one the tool printed this
iteration; every template cites the file:line it was transcribed from; every
preserving verdict needs a control that breaks, or the encoding is wrong; a
breaking verdict is a finding, not a failure; commit each piece, NEVER push (no
credentials on this box). Run everything via `cd
/home/riftuser/aisec-invariants-mlir/prototypes/fcvd_ct && uv run ...`.

## Note

Only one loop at a time. If you relaunch in tmux, any wake-up armed by an older
session is superseded — a dead process cannot fire one, and two loops editing the
same templates would collide. Kill the old session first if it is still attached.
