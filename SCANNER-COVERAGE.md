# How automatic discovery works

**No Google search is used.** GitHub Actions schedules the scanner. The scanner requests public employer job-board data through Greenhouse, Ashby, Lever, and public Workday careers endpoints, plus an attributed community internship feed. It saves the results to `data/jobs.json` and categorized `OPENINGS.md`, and publishes `feed.xml` on GitHub.

## Relevance matching

The scanner first collects publicly listed jobs from each supported employer source, then evaluates early-career jobs using the **role title, department, employment type, and description** when available. It recognizes statistical methods (e.g. survival analysis, causal inference, experimental design, longitudinal modeling), clinical and scientific analysis, bioinformatics, data science, applied analytics, and related roles. Relevant work buried inside a vague internship title can qualify.

- **Strong:** recognizable statistics or related analytical position with supporting evidence.
- **Related:** another relevant field, such as data engineering or consulting analytics.
- **Review description:** an ambiguous posting, a match found primarily in responsibilities, or a title-only feed that does not supply the full description.

The dashboard offers a `Description-based / needs review` filter and a discovery-time filter (past 1, 6, 24 hours or 7 days). `first_seen_at` means *the scanner first detected the posting*, not the employer's publication time. The employer `posted_at` date is separate, when supplied.

## Source-specific limitations

| Source | Description coverage | Notes |
|---|---|---|
| Greenhouse | Full public description with `content=true` | Public boards only; fields and timestamps vary |
| Ashby | Full plain/HTML description | Unlisted/private posts are unavailable |
| Lever | Description + lists/requirements | Paginated public feed; some fields missing |
| Workday | Detail request for candidate jobs | Tenant-specific public endpoint; per-board detail request limit, search pagination, and possible blocks |
| Community internship feed | Title/location/link only | Description unavailable; recommend manual verification |

Broad catalog scans rotate through a directory of *known ATS identifiers*. Registered boards are not evidence of currently open internships. A company using an unsupported system, a blocked board, a new startup not in the directory, or an unpublished job can still be missed. No automated system can guarantee that every posting will be found. Source errors are reported in the dashboard and do not automatically mean a previously found job closed.

GitHub Actions scheduled workflows may run late or be skipped. Priority sources are scheduled every 15 minutes; broad batches hourly. These are polling schedules, not guarantees of real-time discovery.

## Privacy

The public repository holds job postings and advertised employer compensation only. Personal application statuses, notes and comparison inputs stay in the browser unless the user exports them. No third-party notification service is configured.
