# Changelog

Each version of parsed, newest first.

A **Breaking** line means code written for the version before may fail, or behave differently.

The top entry, while it reads *unreleased*, collects what has merged for the next version; each change adds its own
lines as it lands, and the entry is dated when that version is released.

## 0.1.0 — 2026-10-21

**The scaffold.** The family's toolchain and release model, and a package root that re-exports seared's
declaration surface. Commands arrive in the releases that follow.

### Added

- **The package root:** `import parsed` gives seared's field types and its errors, its base class as
  `parsed.Parsed` and its decorator as `parsed.parsed`, as zeared re-exports them. Every name is seared's own
  object; the rest of seared stays reachable as `seared.*`. The package ships `py.typed`.
- **The toolchain:** hatchling; ruff, ty, deptry and pytest; `prek` hooks that gate each commit on them, and refuse
  one on `master`; a release workflow that tags `v<version>` when a version merges to `master`.
- **Dependencies:** seared `>=0.4.4,<0.5.0`, pinned to `tag = "v0.4.4"`.
