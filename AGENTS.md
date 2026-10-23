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

## Data preservation and implementation decisions

- Preserve source geometry, vertex order, and scalar values by default. Before
  introducing a transformation, explain its purpose and establish why supported
  viewer behavior is insufficient. Document intentional conversions or masking.
- Test the simplest supported package approach first. Add conversions, wrappers,
  or patches only for a demonstrated requirement or reproducible failure.
- Document each transformation's input, output, effect on scientific data, and
  supporting validation. Distinguish data changes from display settings.
- Inspect the current code before explaining project-specific behavior.
  Distinguish verified implementation, observed behavior, and hypotheses; do not
  present a plausible rationale as an established requirement.
- Report material implementation choices and departures from the agreed approach
  before building further work on them, especially changes to coordinates, data
  representation, or package integration. These are progress touchpoints, not
  blanket approval requirements for routine edits.
- Protect relevant invariants with regression tests: source coordinates and
  vertex order, preserved scalar values and missing-value positions, and reuse
  of prepared assets during interaction. Check the data passed to the viewer,
  not only intermediate helpers. Use synthetic source fixtures where private
  data is unavailable. Intentional exceptions (such as atlas color generation)
  must be explicit; do not weaken tests merely to accommodate a regression.
  Run the invariant tests when changing data preparation, loading, or viewer
  inputs, and report their results before declaring the change complete.
