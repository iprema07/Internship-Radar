# Internship Radar

An automatically refreshed directory of internships in statistics, biostatistics, epidemiology, scientific research, data science, and related analytical fields.

**[Browse openings](OPENINGS.md)** · Interactive dashboard available through GitHub Pages

## Features

- Discovers internships across startups, research organizations, healthcare companies, and established employers
- Collects public listings from supported applicant tracking systems and attributed internship directories
- Groups opportunities by discipline, with statistics-focused roles easy to find
- Links to original employer postings and identifies listings that need further verification
- Provides an interactive dashboard with filters, bookmarks, and optional browser-local tracking

## Update frequency

Priority employers are checked on a 15-minute schedule. A 500-board directory batch is
scanned hourly (2,000 registered boards in approximately four scheduled cycles).
The dashboard distinguishes employer posting time from first detection; unknown ages
are labeled as unknown. Scheduled jobs may run late and employer feeds may lag.

New openings are saved directly to GitHub as `data/jobs.json` and `OPENINGS.md`.
The dashboard includes 1-hour, 6-hour and 24-hour discovery filters. No external accounts or notification services are required.
An optional GitHub-hosted RSS file is published at [`feed.xml`](feed.xml).

## What is scanned

The scanner reads public employer ATS job boards directly, not Google search results.
Where an employer feed provides a full job description, the matcher evaluates titles, departments, statistical methods, and responsibilities. Unclear postings remain marked for review.
Read [source coverage and limitations](SCANNER-COVERAGE.md).

## Updates

Run **Actions → Update internships → Run workflow** to refresh the directory. For the dashboard, enable GitHub Pages from the `main` branch and `/ (root)`.

## Sources and attribution

- [LastRound AI ATS Directory](https://github.com/fyrosofttech/lastroundai-hiring-data) — CC BY 4.0
- [Public Job Board Directory](https://kalebconfer-sys.github.io/job-board-directory/)
- [Zapply Internships 2027](https://github.com/zapplyjobs/Internships-2027)

Coverage is not comprehensive. Always verify availability, dates, and eligibility with employers.
