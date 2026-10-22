# Project instructions

Whenever implementing a new dashboard feature or changing existing dashboard
behavior, update the relevant Markdown documentation in the same task without
waiting for a separate request. This is the user's standing preference.

- Keep `docs/implementation.md` brief and accurate about the current implementation.
- Update `README.md` when behavior, defaults, setup, or usage changes.
- When present, consult and update `notes/RESUMING.md` for local session handoff,
  including decisions, verification results, and outstanding work. It is optional
  and Git-ignored; shared maintenance documentation must remain self-contained.
- Update specialized source/provenance notes when their subject changes.

Update only the documents relevant to the change, remove superseded claims,
and distinguish completed implementation from future ideas. Report only checks
actually performed. Preserve historical planning documents as historical.

Put personal/scratch notes in the Git-ignored root `notes/` folder, regardless
of file extension. Keep shared implementation, review, deployment, and provenance
documentation outside it so those documents remain available in Git.

Prefer maintainable, readable implementations using supported package APIs.
Treat current viewer bundle patches as prototype technical debt; consult
`docs/compatibility.md` before extending them. Distinguish observed behavior
in the pinned stack from confirmed package defects or universal limitations.
