# Updating an existing installation

The repository is the only automated job store. No chat app, webhook, or external account is required.

1. Upload the replacement files in this archive to the repository root (retain `.github/workflows/update.yml`).
2. For an existing repository, **keep its existing `data/jobs.json` and `data/board_catalog.json`** so discovered jobs and board history survive; the full archive includes empty starter data intended only for a brand-new repository.
3. Delete obsolete files if present: `ALERTS-SETUP.md`, `data/alert_outbox.json`, and `tests/test_reliability.py` (that older test required the removed notification function).
4. In GitHub Actions, manually run `Update internships` with `scan_mode = broad` once. Confirm the directory catalog populated, inspect `data/jobs.json` and `OPENINGS.md`, and verify source health.
5. Enable GitHub Pages from `main` / root to browse the dashboard. You can filter newly detected jobs by 1, 6, or 24 hours and show "Description-based / needs review" roles.

The source feed can still miss unlisted jobs, blocked employer boards, unsupportable ATS platforms, or openings outside scanned schedules. `first_seen_at` is the scanner's detection time, never a guaranteed employer publication time. Browser-local application notes are not committed to GitHub.
