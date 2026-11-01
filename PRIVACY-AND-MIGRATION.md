# Private tracking and migration

This is a **new initial-commit project**, not a fork or a Git-clone of the original public repository. Upload these extracted files into a new empty repository to avoid copying historical commits.

**Privacy boundary:** This public project contains its software, a public company directory, publicly listed job metadata, and general relevance rules. Personal preferences and application notes are saved locally in each browser; GitHub does not receive or sync them. Export tracking backups only to a private place. Do not commit your personal CSV or JSON backups.

If an older repository exposed private details in its Git history, making it private limits normal public access going forward but is not a guarantee of erasing prior copies, caches, or forks. Keep the old repository private until the replacement is verified, then decide whether to remove it.

## Going live

1. Create a **new** GitHub repository (for example `internship-radar`) and initialize with *no README*.
2. Upload all files, including the hidden `.github/workflows/update.yml` file; make a single clean initial commit.
3. Start `Actions → Update internships → Run workflow` and inspect the log for a successful directory refresh and actual source scans.
4. Enable GitHub Pages from `main` and `/ (root)`.
5. Enter any personal settings in the dashboard only. Save applications there and export a local tracking backup occasionally.

This public project does not claim to identify every startup or independently verify internship eligibility. Review employer pages directly.
