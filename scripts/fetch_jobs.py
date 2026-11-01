#!/usr/bin/env python3
"""Personal internship feed. Public job-board endpoints; no credentials required.

Run from the repository root with `python scripts/fetch_jobs.py`.
Fetchers are deliberately independent: a failed company never closes its old jobs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
import os
import re
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
if __package__:
    from .pay import extract_pay
else:
    from pay import extract_pay

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/jobs.json"
SOURCES = ROOT / "config/companies.json"
PREFS = ROOT / "config/preferences.json"
README = ROOT / "README.md"
USER_AGENT = "BioDataInternshipRadar/1.0 (personal noncommercial job monitoring)"
RETRY_STATUS = {429, 500, 502, 503, 504}
TAGS = {
    "Biostatistics": ["biostat", "statistic", "statistical", "pharmacometrics"],
    "Bioinformatics": ["bioinformatic", "computational biol", "computational genom", "omics", "biomarker"],
    "Data Science / ML": ["data scien", "machine learn", "ai/ml", "artificial intelligence", "modeling", "modelling"],
    "Clinical / RWE": ["clinical data", "clinical informatic", "epidemiolog", "real.world evidence", "rwe", "health economic", "outcomes research", "population health"],
    "Analytics / BI": ["data analy", "analytics", "business intelligence", "business analy", "insights", "data & ai", "data and ai", "decision science", "data management", "market intelligence"],
}


def plain_text(s):
    """Deal with HTML-escaped Greenhouse content without external dependencies."""
    value = unescape(unescape(str(s or "")))
    value = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def get_json(url, post_data=None):
    data = json.dumps(post_data).encode() if post_data is not None else None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    for attempt in range(3):
        try:
            with urlopen(req, timeout=22) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("Unable to fetch")


def greenhouse(src):
    slug = src["slug"]
    response = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not isinstance(response.get("jobs"), list):
        raise ValueError("Malformed Greenhouse response")
    for j in response["jobs"]:
        if not j.get("id") or not j.get("title"):
            continue
        department = ", ".join(d.get("name", "") for d in (j.get("departments") or []))
        yield {
            "id": f"greenhouse:{slug}:{j['id']}", "title": j["title"],
            "url": j.get("absolute_url") or f"https://job-boards.greenhouse.io/{slug}/jobs/{j['id']}",
            "location": (j.get("location") or {}).get("name") or "Not listed",
            "department": department, "description": plain_text(j.get("content"))[:24000], "description_status": "full" if j.get("content") else "missing",
            "posted_at": j.get("first_published") or "",
            "modified_at": j.get("updated_at") or "",
            "employment_type": "", "salary_range": {}, "compensation": {}
        }


def lever(src):
    slug = src["slug"]
    host = "api.eu.lever.co" if src.get("region") == "eu" else "api.lever.co"
    # API supports pagination; continue until fewer than limit returned.
    limit = 100
    for offset in range(0, 2000, limit):
        jobs = get_json(f"https://{host}/v0/postings/{slug}?mode=json&skip={offset}&limit={limit}")
        if not isinstance(jobs, list):
            raise ValueError("Malformed Lever response")
        for j in jobs:
            if not j.get("id") or not j.get("text"):
                continue
            cats = j.get("categories") or {}
            description = " ".join(filter(None, [
                j.get("descriptionPlain") or j.get("description"),
                *[plain_text(part.get("content")) for part in (j.get("lists") or []) if isinstance(part, dict)],
                j.get("additionalPlain") or j.get("additional")
            ]))
            yield {
                "id": f"lever:{slug}:{j['id']}", "title": j["text"],
                "url": j.get("hostedUrl") or j.get("applyUrl") or f"https://jobs.lever.co/{slug}/{j['id']}",
                "location": cats.get("location") or "Not listed",
                "department": cats.get("team") or "", "description": plain_text(description)[:24000], "description_status": "full" if description.strip() else "missing",
                "posted_at": "", "modified_at": "", "employment_type": cats.get("commitment") or "",
                "salary_range": j.get("salaryRange") or {}, "workplace_type": j.get("workplaceType") or ""
            }
        if len(jobs) < limit:
            break


def ashby(src):
    slug = src["slug"]
    response = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    if not isinstance(response.get("jobs"), list):
        raise ValueError("Malformed Ashby response")
    for j in response["jobs"]:
        if not j.get("title") or j.get("isListed") is False:
            continue
        url = j.get("jobUrl") or j.get("applyUrl") or ""
        # Ashby jobs have a stable URL even when the response has no separate id.
        uid = str(j.get("id") or hashlib.sha256((url or j["title"] + (j.get("location") or "")).encode()).hexdigest()[:16])
        yield {
            "id": f"ashby:{slug}:{uid}", "title": j["title"], "url": url,
            "location": j.get("location") or "Not listed",
            "department": j.get("department") or j.get("team") or "",
            "description": plain_text(j.get("descriptionPlain") or j.get("descriptionHtml") or "")[:24000], "description_status": "full" if (j.get("descriptionPlain") or j.get("descriptionHtml")) else "missing",
            "posted_at": j.get("publishedAt") or "", "modified_at": "",
            "employment_type": j.get("employmentType") or "",
            "compensation": j.get("compensation") or {}, "workplace_type": j.get("workplaceType") or ""
        }


def workday(src, prefs):
    """Query a company's public Workday career listing and enrich likely internships.

    Workday's list payload does not carry the full description. We request each
    likely early-career posting's public detail record; a failed detail request
    never causes a plausible opening to disappear.
    """
    host, tenant, site = src["host"], src["tenant"], src["site"]
    if not re.fullmatch(r"[a-zA-Z0-9.-]+\.myworkdayjobs\.com", host):
        raise ValueError("Invalid Workday host")
    if not all(re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',v) for v in (tenant,site)):
        raise ValueError('Invalid Workday tenant or site')
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    limit = 20
    max_pages = min(int(prefs.get("max_workday_pages", 20)), 50)
    max_details = max(1,int(prefs.get('workday_details_per_board',100)))
    enriched = 0
    # A list query may return jobs because an internship was mentioned in the
    # body. Keep details for those with plausible titles, rather than assuming
    # the result title must contain one particular discipline keyword.
    for page in range(max_pages):
        response = get_json(base+'/jobs', {"limit":limit,"offset":page*limit,
                                             "searchText":src.get('search','intern'),"appliedFacets":{}})
        results=response.get('jobPostings')
        if not isinstance(results,list):raise ValueError('Malformed Workday response')
        for j in results:
            path=j.get('externalPath') or ''
            if not j.get('title') or not re.fullmatch(r'/job/[a-zA-Z0-9_./%~\-]{1,450}',path):
                continue
            title=str(j['title'])
            summary=' '.join(str(x) for x in (j.get('bulletFields') or []))
            description=summary
            description_status='summary'
            pub_date=''
            employment_type=''
            url=f'https://{host}/en-US/{site}{path}'
            # Rate-limited detail requests for internship / research candidates;
            # avoid fetching hundreds of clearly senior unrelated postings.
            candidate=bool(EARLY_CAREER.search(title) or re.search(
                r'\b(research|biometric|statistics|biostat|analytics|data|scientist|epidemiol|'
                r'methods|modeling|modelling)\b',title,re.I))
            if candidate and enriched < max_details:
                enriched+=1
                try:
                    detail=get_json(base+path).get('jobPostingInfo') or {}
                    full=plain_text(detail.get('jobDescription') or '')
                    if full:
                        description=full[:24000]
                        description_status='full'
                    pub_date=str(detail.get('startDate') or '')
                    employment_type=str(detail.get('timeType') or '')
                    ext=detail.get('externalUrl')
                    if isinstance(ext,str) and ext.startswith('https://'):url=ext
                except (HTTPError,URLError,TimeoutError,ValueError,TypeError,KeyError) as ex:
                    print(f'WARN Workday detail missing for {tenant}: {type(ex).__name__}',file=sys.stderr)
                time.sleep(0.05)
            yield {
                'id':f"workday:{tenant}:{site}:{hashlib.sha256(path.encode()).hexdigest()[:18]}",
                'title':title,'url':url,'location':j.get('locationsText') or 'Not listed',
                'department':'','description':description,'description_status':description_status,
                'posted_at':pub_date,'modified_at':'','employment_type':employment_type,
                'salary_range':{}
            }
        if len(results)<limit or (page+1)*limit>=response.get('total',10**9):break
    else:
        raise ValueError(f'Workday scan exceeded {max_pages*limit} jobs; narrow source search')


def get_text(url, max_bytes=3_000_000):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain"})
    with urlopen(req, timeout=30) as response:
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("Community feed exceeded size limit")
        return content.decode("utf-8", errors="replace")


def canonical_url(url):
    """Remove advertising parameters without removing job-identifying query args."""
    u = urlparse(str(url or ""))
    remaining = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                 if k.lower() not in {'src','source','ref','gh_src','utm_source','utm_medium','utm_campaign','utm_content','utm_term'}]
    return urlunparse((u.scheme, u.netloc.lower(), u.path.rstrip('/'), '', urlencode(sorted(remaining)), ''))


def markdown_jobs(source_text, src):
    """Parse Zapply's six-column Company|Role|Location|Posted|Visa|Apply table.

    Only use direct HTTPS apply links; do not republish enrichment fields. The
    app links back to Zapply for required attribution.
    """
    records = []
    for line in source_text.splitlines():
        if not line.lstrip().startswith('|'):
            continue
        cells = [c.strip() for c in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
        if len(cells) != 6:
            continue
        company, title, location, _age, _visa, apply_cell = cells
        if company.lower() == 'company' or not company or not title:
            continue
        match = re.search(r'\]\((https://[^\s)]+)', apply_cell) or re.search(r'href=["\'](https://[^"\']+)', apply_cell)
        if not match:
            continue
        url = unescape(match.group(1))
        # The readme may include decoration / HTML; avoid storing it as metadata.
        title = plain_text(re.sub(r'!\[[^]]*\]\([^)]*\)', '', title))
        company = plain_text(re.sub(r'!\[[^]]*\]\([^)]*\)', '', company))
        location = plain_text(location) or 'Not listed'
        if len(title) > 300 or len(company) > 120:
            continue
        uid = hashlib.sha256(canonical_url(url).encode()).hexdigest()[:24]
        records.append({"id": f"community:{src['id']}:{uid}", "title": title,
                        "company": company, "url": url, "location": location, "department": "",
                        "description": "", "description_status": "missing", "posted_at": "", "modified_at": "", "employment_type": ""})
    if len(records) < 10:
        raise ValueError(f"Community feed parsed only {len(records)} rows; upstream layout may have changed")
    return records


def github_markdown(src):
    yield from markdown_jobs(get_text(src['url']), src)



FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "github_markdown": github_markdown}
EARLY_CAREER = re.compile(r"\b(intern(ship)?|co[ -]?op|student|trainee|summer associate|summer analyst|fellow(ship)?)\b", re.I)

# Prioritize the actual role, not the employer's industry. These families are broad
# public defaults; personal preferences belong in the browser, not the repository.
ROLE_FAMILIES = (
    # Statistics first: pharma teams use "biometrics", "decision sciences",
    # and "statistical programming" as well as "biostatistics".
    ('Biostatistics / Statistical Programming',
     r'biostatistic|statistical program|clinical statist|statistical scien|biometric(?:s|ian)'),
    ('Statistics / Statistical Methods',
     r'\bstatistics\b|\bstatistician\b|statistical analy|statistical method|'
     r'statistical research|statistical model|statistical computing|decision sciences|'
     r'experimental design|experiment(?:ation|al) scien|causal inferen|'
     r'survey method|survey statist|sampling method|research decision sciences|'
     r'\bpsychometric|\beconometric|operations research'),
    ('Epidemiology / RWE / HEOR',
     r'epidemiolog|real.world evidence|\brwe\b|health economic|\bheor\b|'
     r'outcomes research|evidence generation|pharmacoepidemiolog|'
     r'population health|public health analy|clinical outcomes|market access analy'),
    ('Bioinformatics / Computational Biology',
     r'bioinformatic|computational biol|computational genom|genomic data|'
     r'omics data|biomarker data|genetic analy|computational bio'),
    ('Data Science / ML',
     r'data scien|machine learn|\bai/ml\b|data & ai|data and ai|'
     r'applied scientist|\bml research\b'),
    ('Analytics / BI',
     r'\banalytics\b|data analy|business analy(?:tics|sis)|product analy|'
     r'commercial analy|marketing analy|business intelligence|market intelligence|'
     r'decision scien|research analy|operations analy|supply chain analy|'
     r'financial analy|pricing analy|risk analy|strategy analy|clinical data|'
     r'clinical informatic|medical informatic|healthcare analy'),
    ('Data Engineering',
     r'data engineer|analytics engineer|data platform|data infrastructure|data automation'),
    ('Applied Research / Modeling',
     r'computational research|predictive model|research informatic|modeling|'
     r'modelling|computational health|behavioral research|behavioural research'),
    ('Strategy / Consulting',
     r'business analyst|product analyst|product operations|strategy analyst|'
     r'strategy & operations|healthcare consult|life sciences consult|'
     r'management consult|market research|market intelligence|research analyst|'
     r'growth analyst|healthcare analyst|data strategy'),
)
STATISTICAL_METHODS = (
    r'\bsurvival analysis\b', r'\blongitudinal (?:analysis|data|model)',
    r'\bclinical trial (?:design|data|analysis|statistics)', r'\bstatistical (?:analysis|methods?|models?|programming|inference|computing)',
    r'\bcausal (?:inference|estimation|effect)', r'\brandomized (?:controlled|trial|experiment)',
    r'\bexperimental design', r'\ba/b test(?:ing)?\b', r'\bhypothesis test',
    r'\bregression (?:analysis|model)', r'\bmixed.effects? model',
    r'\bbayesian (?:model|statistic|inference|analysis)', r'\btime.series (?:analysis|model)',
    r'\bsurvey (?:methodology|sampling|weighting|statistics)',
    r'\bstatistical programming', r'\bprobability model', r'\bsas programming',
)
STAT_METHODS_RX = [re.compile(p,re.I) for p in STATISTICAL_METHODS]
STATS_DEPARTMENT = re.compile(
    r'\b(biostatistics?|statistics?|statistical programming|biometrics|'
    r'decision sciences|research decision sciences|clinical data sciences?)\b',re.I)
GENERIC_RESEARCH = re.compile(
    r'\b(research|clinical development|scientific|data|evidence|'
    r'clinical science|intern(?:ship)? program|\br&d\b)\b',re.I)

# Hard exclusions apply to *job titles*. Qualifying data-science openings at
# hardware or software companies remain visible; generic SWE does not.
NON_TARGET = re.compile(
    r'software (?:engineer|develop)|full[ -]?stack|front[ -]?end|back[ -]?end|'
    r'\bdevops\b|site reliability|security engineer|embedded|firmware|'
    r'electrical engineer|mechanical engineer|hardware engineer|'
    r'\b(?:ml|ai|machine learning) engineer\b|platform engineer|'
    r'\b(?:quant|quantitative)[ -]?(?:research|trading|trader|developer|analyst)\b|'
    r'algorithmic trading|equity research|investment banking|portfolio (?:research|manager)|'
    r'\bwet[ -]?lab\b|clinical trial coordinator|laboratory technician|'
    r'clinical research coordinator|pharmacy technician|nursing|postdoc|post-doctoral', re.I)
WET_LAB = re.compile(r'cell culture|pipetting|western blot|animal handling|immunohistochemistry|protein purification',re.I)
ANALYTICAL_CONTEXT = re.compile(r'\b(python|\bsql\b|\bR\b|sas|statistics|machine learning|data science|'
                                r'quantitative|regression|causal inference|bioinformatics|modeling|modelling|'
                                r'clinical data|analytics|computational biology)\b',re.I)
PHD_EXCLUSIVE_TITLE = re.compile(r'\b(?:ph\.?d\.?|doctoral|doctorate)\s*(?:only|students?|interns?|candidate)\b',re.I)
PHD_EXCLUSIVE_DESCRIPTION = re.compile(r'\b(?:ph\.?d\.?|doctorate|doctoral degree)\s+(?:is\s+)?(?:required|mandatory|only)\b',re.I)


def match_job(job, prefs):
    title = str(job.get('title') or '')
    lower = title.lower()
    desc = str(job.get('description') or '')
    year = str(prefs.get('target_year',2027))
    if not EARLY_CAREER.search(title) and not re.search(r'\b(intern|co[ -]?op)\b',str(job.get('employment_type') or ''),re.I):
        # Only accept clear early-career program descriptions, not generic
        # careers-page boilerplate mentioning a company's internship program.
        if not re.search(r'\b(?:this|the|our)\s+(?:summer\s+)?(?:internship|intern|co[ -]?op)\s+(?:role|position|opportunity|will|program)\b',desc[:500],re.I):
            return None
    if NON_TARGET.search(title): return None
    if re.search(r'\b(?:quant(?:itative)?\s+(?:research|trading|trader|analyst|developer)|quant trader|algorithmic trading|derivatives trading|high.frequency trading|portfolio optimization)\b', title, re.I): return None
    if any(term in lower for term in prefs.get('excluded_title_terms',[])):
        return None
    if PHD_EXCLUSIVE_TITLE.search(title): return None
    # A role explicitly restricted to doctoral students is outside the target scope.
    if re.search(r'\b(?:ph\.?d\.?|doctoral)\b', title, re.I) and not re.search(r'\b(?:master|m\.?s\.?|graduate studies)\b', title, re.I):
        return None
    if re.search(r'\bundergrad(?:uate)?\s+only\b|\bbachelor(?:\'s)?\s+only\b', title+' '+desc, re.I):
        return None
    if PHD_EXCLUSIVE_DESCRIPTION.search(desc) and not re.search(r'\b(master|m\.?s\.?|bachelor)\b',desc,re.I):
        return None
    if re.search(r'\b(?:spring|fall|winter)\s*(?:of\s*)?'+year+r'\b|\b'+year+r'\s*(?:spring|fall|winter)\b',lower):
        if not re.search(r'\bsummer\b',lower):return None
    years=set(re.findall(r'\b20\d{2}\b',title))
    if years and year not in years and any(int(y)<int(year) for y in years):return None
    is_summer=bool(re.search(r'\bsummer\s*(?:of\s*)?'+year+r'\b|\b'+year+r'\s*summer\b',lower+' '+desc.lower()))

    department = str(job.get('department') or '')
    groups=[label for label,expression in ROLE_FAMILIES if re.search(expression,title,re.I)]
    method_hits=sum(bool(rx.search(desc)) for rx in STAT_METHODS_RX)
    department_stat=bool(STATS_DEPARTMENT.search(department))
    title_stat=any(g in groups for g in ('Biostatistics / Statistical Programming','Statistics / Statistical Methods'))
    # An ambiguous "Biometrics Intern" may be about authentication rather than
    # clinical statistics; confirm context before ranking as a strong stats role.
    biometrics_ambiguous=bool(re.search('biometric',title,re.I)) and not (
        department_stat or method_hits or re.search('clinical|pharma|trial|SAS|statistics',desc,re.I))
    if biometrics_ambiguous:
        groups=[g for g in groups if g!='Biostatistics / Statistical Programming']
    if groups == ['Strategy / Consulting'] and not (ANALYTICAL_CONTEXT.search(desc) or re.search(r'healthcare|life sciences|product metrics|market research|data|analytics|business strategy',desc,re.I)):
        return None
    evidence='Role title'
    # Match a role hidden in a broader "research" title by its actual work:
    # multiple distinct statistical methods, or a statistics department plus
    # one method. A generic "Python" or "SQL" mention is not enough.
    if not title_stat and GENERIC_RESEARCH.search(title) and (method_hits>=2 or (department_stat and method_hits>=1)):
        groups=['Statistics / Statistical Methods']+[g for g in groups if g!='Statistics / Statistical Methods']
        evidence='Description and department' if department_stat else 'Statistical work in description'
    elif not groups and department_stat and method_hits>=1:
        groups=['Statistics / Statistical Methods']
        evidence='Statistics department and methods'
    if not groups:
        # Open recall: broad internships may hide relevant modeling/statistical
        # work under titles like Scientific Intern, Biometrics Associate, or
        # Research Operations Intern. Require substantive description evidence,
        # not only generic Python/SQL mentions or employer marketing text.
        strong_methods = method_hits >= 2
        quantitative_work = bool(re.search(
            r'\b(?:predictive model(?:s|ing)?|experimental design|randomized controlled|'
            r'statistical modeling|statistical analysis|clinical trial analysis|'
            r'computational biology|bioinformatics|real.world evidence|'
            r'causal inference|hypothesis testing|a/b testing|survival analysis|'
            r'epidemiological analysis|longitudinal analysis|biostatistics)\b',desc,re.I))
        data_work = bool(re.search(
            r'\b(?:build|analyz(?:e|ing)|design|develop|model|process|evaluate|'
            r'interpret|estimate|validate)\b.{0,90}\b(?:data|datasets|statistical|'
            r'models|experiments|clinical outcomes|population health)\b',desc,re.I))
        plausible_title = bool(re.search(
            r'\b(?:research|scientific|science|biometric|clinical|health|'
            r'product|business|strategy|operations|data|analytics|program|'
            r'evidence|insights|intern|fellow|trainee)\b',title,re.I))
        if not plausible_title or not (strong_methods or quantitative_work or (data_work and ANALYTICAL_CONTEXT.search(desc))):
            return None
        if WET_LAB.search(desc) and not (strong_methods or quantitative_work):return None
        groups=['Statistics / Statistical Methods' if strong_methods else 'Applied Research / Modeling']
        evidence='Statistical methods in full description' if strong_methods else 'Analytical responsibilities in description'
    if biometrics_ambiguous and not groups:return None

    # Prioritize statistical methods and role relevance; eligibility is separate.
    statistical_role=groups[0] in ('Biostatistics / Statistical Programming','Statistics / Statistical Methods')
    core=any(g in groups for g in ('Epidemiology / RWE / HEOR','Bioinformatics / Computational Biology','Data Science / ML','Analytics / BI'))
    tier='strong' if statistical_role or core else 'related'
    score=88 if statistical_role and title_stat else 79 if statistical_role else 76 if core else 63
    reasons=[evidence+' matches '+', '.join(groups[:2])]
    if method_hits>=2:
        score+=4;reasons.append('Multiple statistical methods mentioned')
    if department_stat:
        score+=4;reasons.append('Statistics-related department')
    if re.search(r'\b(master|m\.?s\.?|graduate student)\b',desc,re.I):
        score+=6;reasons.append('Graduate student eligibility mentioned; verify dates')
    if is_summer:score+=7;reasons.append('Summer target explicitly mentioned')
    else:reasons.append('Summer dates need confirmation')
    if ANALYTICAL_CONTEXT.search(desc):score+=6;reasons.append('Relevant analytical methods or tools mentioned')
    description_status=job.get('description_status') or ('full' if desc.strip() else 'missing')
    if description_status!='full':
        tier='review'
        reasons.append('Full posting description not available; verify role responsibilities')
    elif evidence!='Role title':
        tier='review'
        reasons.append('Relevant responsibilities found in description; review requirements')
    if method_hits:
        reasons.append(f'{method_hits} statistical method signal(s) in posting')
    if re.search(r'\b(software engineer|engineering degree|computer science degree)\b',desc,re.I):
        reasons.append('Check technical prerequisites')
    # Do not discard unknown pay or blend annual salary into a guaranteed hourly rate.
    pay=extract_pay(job,prefs)
    if pay.get('basis')=='annualized_estimate':reasons.append('Annualized figure; verify actual internship hourly rate')
    return {'score':min(100,score),'focus':groups,'reasons':reasons,'pay':pay,
            'fit_tier':tier,'primary_focus':groups[0],'season':'summer_confirmed' if is_summer else 'season_unconfirmed',
            'description_status':description_status, 'match_source':evidence, 'method_signal_count':method_hits}


def normalize(job, src, metadata, old, today, timestamp=None):
    uid = job["id"]
    prior = old.get(uid, {})
    return {
        "id": uid, "company": job.get("company") or src["name"], "sector": src["sector"],
        "stage": src.get("stage", "Unknown"), "aggregated": src["ats"] == "github_markdown",
        "source": src["id"], "ats": src["ats"], "title": job["title"],
        "location": job["location"], "department": job["department"],
        "url": job["url"], "focus": metadata["focus"], "score": metadata["score"],
        "reasons": metadata["reasons"], "pay": metadata["pay"], "season": metadata["season"],
        "fit_tier": metadata.get("fit_tier", "review"), "primary_focus": metadata.get("primary_focus", "Other"),
        "description_status":metadata.get('description_status','missing'),
        "match_source":metadata.get('match_source','Unverified'),
        "method_signal_count":metadata.get('method_signal_count',0),
        "posted_at": job["posted_at"],
        "modified_at": job["modified_at"], "first_seen": prior.get("first_seen") or today,
        "first_seen_at": prior.get("first_seen_at") or (timestamp if not prior else None),
        "last_seen": today, "last_seen_at": timestamp or prior.get("last_seen_at"),
        "status": "open", "closed_at": None, "missing_scans": 0
    }


def parse_employer_posted_at(value):
    """Return comparable UTC time for a trustworthy ISO employer posting date.

    A YYYY-MM-DD string has *day* precision, not an exact publication hour.
    Missing, vague or invalid values stay unknown; never substitute first_seen.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", raw):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def posted_display(value):
    """Show only the publication precision actually provided by the employer."""
    dt = parse_employer_posted_at(value)
    if dt is None:
        return 'Not provided'
    if len(str(value).strip()) == 10 or dt.tzinfo and not re.search(r'[+-]\d\d:?\d\d|Z$', str(value).strip()):
        return dt.strftime('%Y-%m-%d')
    return dt.strftime('%Y-%m-%d %H:%M UTC')


def detected_display(job):
    """An observation time, never an employer publishing time."""
    raw = job.get('first_seen_at') or ''
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except (TypeError, ValueError, AttributeError):
        pass
    return str(job.get('first_seen') or 'Unknown')


def write_openings(data):
    """Newest actual employer postings FIRST, independent of role category.

    New detection timestamps are separately labeled, and unknown publication
    dates do not jump to the top after every scanner run.
    """
    active = [j for j in data.get('jobs', []) if j.get('status') == 'open'
              and str(j.get('url', '')).startswith('https://')]
    def safe(v):
        return str(v or '').replace('\\', '').replace('|', '\\|').replace('\n', ' ').replace('[', '\\[').replace(']', '\\]')
    scan_time = parse_employer_posted_at(str(data.get('updated_at') or '')) or datetime.now(timezone.utc)
    valid = []
    unknown = []
    for job in active:
        date = parse_employer_posted_at(job.get('posted_at'))
        # Ignore implausibly future-dated records rather than making them look urgent.
        if date and (date - scan_time).total_seconds() < 86400:
            valid.append((date, job))
        else:
            unknown.append(job)
    valid.sort(key=lambda entry: (entry[0], int(entry[1].get('score') or 0),
                                  entry[1].get('company', '').casefold()), reverse=True)
    unknown.sort(key=lambda j: (j.get('first_seen_at') or j.get('first_seen') or '',
                                int(j.get('score') or 0)), reverse=True)
    categories = [
        ('today', 'Posted today (UTC)'),
        ('week', 'Posted 1–7 calendar days ago'),
        ('month', 'Posted 8–30 days ago'),
        ('older', 'Posted more than 30 days ago'),
        ('unknown', 'Employer posting date unavailable — newest detected first'),
    ]
    buckets = {k: [] for k, _ in categories}
    for date, job in valid:
        days = (scan_time.date() - date.date()).days
        bucket = 'today' if days <= 0 else 'week' if days <= 7 else 'month' if days <= 30 else 'older'
        buckets[bucket].append(job)
    buckets['unknown'] = unknown
    count = len(active)
    sections = [
        '# Summer 2027 Internships', '',
        f'**{count} currently tracked openings** · Last scan: {scan_time.strftime("%Y-%m-%d %H:%M UTC")}', '',
        '**Sorted by employer posting date, newest first.** Dates are shown only when supplied by an employer.',
        'The *First detected* column records when this scanner first found a listing; it is NOT the posting date.',
        'Postings with unknown release dates are below the dated results, sorted by first detection.', '',
        '[Project home](README.md) · [Interactive dashboard](index.html)', '',
        f'**With employer dates: {len(valid)}** · **Date unavailable: {len(unknown)}**', '',
    ]
    for key, heading in categories:
        items = buckets[key]
        if not items:
            continue
        sections += [f'## {heading} ({len(items)})', '',
            '| Posted by employer | Company | Internship | Discipline | Location | Advertised pay | First detected | Match |',
            '|---|---|---|---|---|---|---|---|']
        for j in items:
            pay = j.get('pay') or {}
            low = pay.get('hourly_min'); high = pay.get('hourly_max')
            rate = 'Not disclosed' if low is None else f'${low:g}' + (f'–${high:g}' if high is not None and high != low else '') + '/hr'
            if pay.get('basis') == 'annualized_estimate':
                rate += ' (estimated)'
            match = j.get('match_source') or 'Title'
            if j.get('fit_tier') == 'review':
                match += ' · Review'
            discipline = j.get('primary_focus') or ', '.join(j.get('focus') or []) or 'Related research'
            sections.append(
                f'| {safe(posted_display(j.get("posted_at")) if key != "unknown" else "Not provided")} '
                f'| {safe(j.get("company"))} | [{safe(j.get("title"))}]({j["url"]}) '
                f'| {safe(discipline)} | {safe(j.get("location"))} | {safe(rate)} '
                f'| {safe(detected_display(j))} | {safe(match)} |'
            )
        sections.append('')
    if not active:
        sections += ['No matching openings collected yet. Run the GitHub Actions workflow.', '']
    sections += ['---', '',
        'Posting dates are employer-supplied and may be date-only, delayed or missing. First detection is not publication time.',
        'Links, eligibility, pay and continued availability should be verified directly with the employer.', '']
    (ROOT / 'OPENINGS.md').write_text('\n'.join(sections), encoding='utf-8')



def recent_age_hours(value, now):
    """Strict timestamp parsing: do not turn the day first seen into posting time."""
    if not value: return None
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if parsed.tzinfo is None: return None
        t=datetime.fromisoformat(str(now).replace('Z','+00:00'))
        return (t-parsed).total_seconds()/3600
    except (ValueError,TypeError,OverflowError):
        return None


def write_rss(data):
    """Public RSS for feed readers and optional push-from-RSS providers."""
    from xml.etree.ElementTree import Element, SubElement, tostring
    from email.utils import format_datetime
    feed=Element('rss',{'version':'2.0'})
    channel=SubElement(feed,'channel')
    repo=os.environ.get('GITHUB_REPOSITORY','').strip()
    project_link=('https://github.com/'+repo if re.fullmatch(r'[\w.-]+/[\w.-]+',repo) else 'https://github.com/')
    for label,value in [('title','Internship Radar — new opportunities'),
                        ('link',project_link),
                        ('description','Recently detected opportunities in statistical and applied data fields')]:
        SubElement(channel,label).text=value
    jobs=[j for j in data.get('jobs',[]) if j.get('status')=='open']
    jobs.sort(key=lambda j:j.get('first_seen_at') or j.get('first_seen') or '',reverse=True)
    for job in jobs[:100]:
        item=SubElement(channel,'item')
        for key,value in [('title',job.get('company','')+' — '+job.get('title','')),
                          ('link',job.get('url','')),
                          ('guid',job.get('id','')),
                          ('description',str(job.get('location',''))+' | '+str(job.get('season',''))+' | Publisher date and discovery date may differ.')]:
            e=SubElement(item,key);e.text=value
        timestamp=job.get('first_seen_at')
        if timestamp:
            try:
                parsed=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
                if parsed.tzinfo:SubElement(item,'pubDate').text=format_datetime(parsed)
            except ValueError:pass
    (ROOT/'feed.xml').write_bytes(b'<?xml version="1.0" encoding="utf-8"?>\n'+tostring(feed,encoding='utf-8'))



def run(fetchers=None, now=None, scan_mode='broad'):
    pinned = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    prefs = json.loads(PREFS.read_text(encoding="utf-8"))
    prior_data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"jobs": []}
    previous = {j["id"]: {
        **j,
        'reasons': [r for r in j.get('reasons', []) if 'hourly' not in r.lower() and '$' not in r],
        'pay': {k:v for k,v in (j.get('pay') or {}).items() if k != 'pay_tier'}
    } for j in prior_data.get("jobs", [])}
    current = dict(previous)
    timestamp = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    today = timestamp[:10]
    health = []
    custom_fetchers = fetchers is not None
    fetchers = fetchers or FETCHERS

    # Broad scans rotate across the full catalog hourly. Priority scans check
    # pinned boards + employers with previously relevant openings every 15m.
    directory_status = 'disabled'
    catalog_entries = []
    from datetime import datetime as _datetime
    run_time = _datetime.fromisoformat(timestamp.replace('Z','+00:00'))
    if not custom_fetchers and prefs.get('directory_enabled', False):
        if __package__:
            from .directory import choose_batch, load_and_refresh
        else:
            from directory import choose_batch, load_and_refresh
        if scan_mode == 'priority':
            # Avoid directory downloading every 15 minutes.
            from_directory_path = ROOT / 'data/board_catalog.json'
            try:
                catalog = json.loads(from_directory_path.read_text(encoding='utf-8'))
                catalog_entries = catalog.get('companies', [])
                directory_status = 'cached for priority scan'
            except (OSError, ValueError):
                catalog_entries=[]
                directory_status='catalog unavailable (run broad scan)'
            hot_ids = {j.get('source') for j in previous.values()
                       if j.get('status')=='open' and j.get('fit_tier') in ('strong','related')
                       and str(j.get('source','')).startswith('directory:')}
            hot = [e for e in catalog_entries if e['id'] in hot_ids]
            hot.sort(key=lambda e:(-e.get('directory_rank',0),e['name'].lower()))
            scheduled_directory = hot[:int(prefs.get('priority_discovered_boards',80))]
        else:
            catalog, directory_status = load_and_refresh(
                max_boards=prefs.get('directory_catalog_boards',2000), now=run_time)
            catalog_entries = catalog.get('companies', [])
            scheduled_directory = choose_batch(catalog_entries, pinned,
                boards_per_run=prefs.get('directory_boards_per_scan',500), now=run_time,
                slot_minutes=60)
    else:
        scheduled_directory = []
    sources = pinned + scheduled_directory
    # The pinned sources are always checked; rotating catalog sources are
    # batch-scanned and never marked closed when they were not scheduled.
    ok = 0
    def fetch_one(src):
        fetcher = (lambda s: workday(s,prefs)) if src['ats']=='workday' else fetchers[src['ats']]
        raw = list(fetcher(src))
        if not all(j.get('id') and j.get('title') and str(j.get('url','')).startswith('https://') for j in raw):
            raise ValueError('Invalid job or non-HTTPS URL from source')
        return raw

    # Full results are processed on the main thread; scanning in parallel never
    # mutates the historical job state and retains per-board failure isolation.
    batches = []
    if custom_fetchers:
        for src in sources:
            try: batches.append((src,fetch_one(src),None))
            except Exception as exc: batches.append((src,None,exc))
    else:
        workers = min(24,max(1,int(prefs.get('ats_parallel_workers',12))))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_one,src):src for src in sources}
            for future in as_completed(futures):
                src=futures[future]
                try:batches.append((src,future.result(),None))
                except Exception as exc:batches.append((src,None,exc))
    for src,raw,error in batches:
        name=src['name']
        if error is not None:
            health.append({'company':name,'id':src['id'],'ats':src['ats'],
                          'status':'error','message':str(error)[:180]})
            print(f'ERROR {name}: {error}',file=sys.stderr)
            continue
        try:
            matched=set()
            for job in raw:
                match=match_job(job,prefs)
                if not match:continue
                new_job=normalize(job,src,match,previous,today,timestamp)
                current[new_job['id']]=new_job
                matched.add(new_job['id'])
            for uid,prev in previous.items():
                if prev.get('source')==src['id'] and uid not in matched and prev.get('status')=='open':
                    misses=int(prev.get('missing_scans') or 0)+1
                    current[uid]={**prev,'missing_scans':misses,
                                  'status':'closed' if misses>=2 else 'open',
                                  'closed_at':today if misses>=2 else None}
            health.append({'company':name,'id':src['id'],'ats':src['ats'],
                           'status':'ok','scanned':len(raw),'matches':len(matched),
                           'stage':src.get('stage','Unclassified')})
            ok+=1
            print(f'OK    {name}: {len(matched)} matches / {len(raw)} jobs')
        except Exception as exc:
            health.append({'company':name,'id':src['id'],'ats':src['ats'],
                           'status':'error','message':str(exc)[:180]})
            print(f'ERROR {name}: {exc}',file=sys.stderr)
    keep={}
    for uid,j in current.items():
        if j['status']=='open' or not j.get('closed_at'):
            keep[uid]=j
        else:
            try:
                age=(_datetime.fromisoformat(today)-_datetime.fromisoformat(j['closed_at'])).days
                if age<=120:keep[uid]=j
            except ValueError:keep[uid]=j
    jobs=sorted(keep.values(),key=lambda j:(j['status']!='open',-j['score'],j['company'],j['id']))
    unique={}
    for j in sorted(jobs,key=lambda j:(j.get('aggregated',False),j['status']!='open')):
        key=canonical_url(j.get('url'))
        if not key or key not in unique:unique[key or j['id']]=j
    jobs=sorted(unique.values(),key=lambda j:(j['status']!='open',-j['score'],j['company'],j['id']))
    distinct={(s.get('ats'),s.get('slug','').casefold()) if s.get('slug') else (s['ats'],s['id'])
              for s in pinned+catalog_entries}
    # A green workflow with zero working sources is misleading. Preserve the
    # previous published feed and let GitHub Actions report the outage instead.
    if sources and ok==0 and not custom_fetchers:
        raise RuntimeError('All scheduled job sources failed; retained last successful feed')
    data={'updated_at':timestamp,'scan_mode':scan_mode,'jobs':jobs,'health':health,
          'counts':{'open':sum(j['status']=='open' for j in jobs),
                    'closed':sum(j['status']=='closed' for j in jobs),
                    'sources_scanned':ok,'sources_failed':len(sources)-ok,
                    'sources_scheduled':len(sources),
                    'registered_boards':len(distinct),
                    'directory_catalog_boards':len(catalog_entries),
                    'directory_refresh':directory_status}}
    DATA.parent.mkdir(parents=True,exist_ok=True)
    DATA.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if not custom_fetchers:
        write_openings(data)
        write_rss(data)
    print(f'Finished: {data["counts"]}')
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Run synthetic demo data without network access")
    parser.add_argument("--mode", choices=('broad','priority'), default='broad',
                        help='broad: hourly rolling directory; priority: frequently checked employers')
    args = parser.parse_args()
    if args.demo:
        print("Run 'python -m unittest discover -s tests -v' for synthetic offline tests.")
    else:
        run(scan_mode=args.mode)
