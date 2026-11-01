"""Expand the monitor with a dated, attributed open ATS board directory.

The directory is a source of *possible boards*, not verified live vacancies.
It refreshes at most weekly; subsequent job scans check vendor endpoints.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data' / 'board_catalog.json'
DIRECTORY_URL = ('https://raw.githubusercontent.com/fyrosofttech/lastroundai-hiring-data/'
                 'main/ats-directory/lastroundai-ats-company-directory-2026-08.csv')
LIVE_DIRECTORY_URL = 'https://kalebconfer-sys.github.io/job-board-directory/job-board-directory.json'
LIVE_ATTRIBUTION = 'https://kalebconfer-sys.github.io/job-board-directory/'
WORKDAY_API = re.compile(r'^https://([a-zA-Z0-9.-]+\.myworkdayjobs\.com)/wday/cxs/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)/jobs$')
ATTRIBUTION = 'https://github.com/fyrosofttech/lastroundai-hiring-data/tree/main/ats-directory'
VENDORS = {'ashby','greenhouse','lever'}
SLUG = re.compile(r'^[a-zA-Z0-9_.-]{1,100}$')
LIFE = re.compile(r'bio|genom|pharm|medic|health|clinic|therap|diagnos|oncolog|care|protein|immun|neuro|hospital|life.?scien|scientif|biolog|patient|drug|molecul|research|laborator|cancer|gene|biomark|cellular|genetic|vital|nutrition|fertility|medtech', re.I)
DATA = re.compile(r'\bai\b|analytics|\bdata\b|robot|machine|intelligen|comput|cloud|fintech|automati|software|predict|vision|cyber|model|\bml\b|\blabs\b|digital|algorithm|blockchain|\btech\b|technology|systems|semiconductor', re.I)
ADJACENT = re.compile(r'bank|finance|capital|invest|insurance|payment|energy|aero|space|commerce|retail|consult|engineering|logistic|manufactur|design|mobile|electric|platform|enterprise|industr|media|games|gaming|research|education',re.I)


def classify(name):
    """These are discovery heuristics, not verified company-industry classifications."""
    if LIFE.search(name):
        return ('Potential life sciences / health', 3)
    if DATA.search(name):
        return ('Potential AI / data / technology', 2)
    if ADJACENT.search(name):
        return ('Adjacent industries', 1)
    return ('Cross-industry', 0)


def parse_directory(text):
    """Never trust remote data as a URL or domain; only approved vendors/slugs."""
    parsed = {}
    for item in csv.DictReader(io.StringIO(text)):
        ats = (item.get('ats_vendor') or '').strip().lower()
        slug = (item.get('board_slug') or '').strip()
        name = re.sub(r'\s+', ' ', (item.get('company_name') or '').strip())[:120]
        if ats not in VENDORS or not SLUG.fullmatch(slug) or not name:
            continue
        key = (ats, slug.lower())
        if key in parsed: continue
        category, rank = classify(name)
        parsed[key] = {
            'id': f'directory:{ats}:{slug.lower()}', 'name': name,
            'sector': category, 'stage': 'Unclassified', 'ats': ats, 'slug': slug,
            'directory_last_crawled': item.get('last_crawled',''),
            'directory_rank': rank, 'catalog_source': 'LastRound AI ATS Directory (CC BY 4.0)'
        }
    return list(parsed.values())


def parse_live_directory(text):
    """Parse the separately maintained, more recent public ATS directory.

    Only supported providers and validated vendor endpoints are admitted.
    URLs in the directory are *never* used directly as arbitrary fetch targets.
    """
    result=[]
    rows=json.loads(text)
    if not isinstance(rows,list):raise ValueError('Expected a JSON array')
    for item in rows:
        if not isinstance(item,dict):continue
        ats=str(item.get('platform') or '').lower()
        company=re.sub(r'\s+',' ',str(item.get('company') or '')).strip()[:120]
        slug=str(item.get('token') or '').strip()
        if not company:continue
        sector,rank=classify(company)
        if ats in VENDORS and SLUG.fullmatch(slug):
            obj={'id':f'directory:{ats}:{slug.lower()}', 'name':company,
                 'sector':sector,'stage':'Unclassified','ats':ats,'slug':slug,
                 'directory_rank':rank,'catalog_source':'Public Job Board Directory'}
            if ats=='lever' and item.get('region')=='EU':obj['region']='eu'
            result.append(obj)
        elif ats=='workday':
            match=WORKDAY_API.fullmatch(str(item.get('api_url') or ''))
            if not match:continue
            host,tenant,site=match.groups()
            obj={'id':f'directory:workday:{host}:{site}', 'name':company,
                 'sector':sector,'stage':'Unclassified','ats':'workday',
                 'host':host,'tenant':tenant,'site':site,'search':'intern',
                 'directory_rank':rank,'catalog_source':'Public Job Board Directory'}
            result.append(obj)
    return result


def unique_entries(*groups):
    result={}
    for group in groups:
        for entry in group:
            # Prefer named LastRound board metadata when both catalogs contain a pair.
            result.setdefault(entry['id'],entry)
    return list(result.values())

def prioritized(entries, max_boards=2000):
    """Balanced exploration: life-sciences, data/AI and adjacent employers.

    Deliberately include companies without sector keywords: an unfamiliar startup
    might still hire data scientists. Ties are stable by name + ATS + slug.
    """
    limit = max(0, min(int(max_boards), 9500))
    groups = {i: [] for i in (0,1,2,3)}
    for e in entries:
        groups[e.get('directory_rank',0)].append(e)
    for v in groups.values():
        v.sort(key=lambda e: (e['name'].casefold(), e['ats'], e.get('slug') or e.get('site') or e['id']))
    # 40% health + life sciences, 30% technology, 15% adjacent, 15% long tail.
    targets = {3:int(limit*.40), 2:int(limit*.30), 1:int(limit*.15), 0:limit}
    result=[]
    for rank in (3,2,1):
        result.extend(groups[rank][:targets[rank]])
    # Fill missing target group capacity from the rest, preserving affinity ranking.
    if len(result)<limit:
        already={x['id'] for x in result}
        for rank in (3,2,1,0):
            for e in groups[rank]:
                if e['id'] not in already:
                    result.append(e); already.add(e['id'])
                    if len(result)>=limit: break
            if len(result)>=limit: break
    return result[:limit]


def load_and_refresh(max_boards=2000, now=None, catalog_path=None, getter=None):
    path = catalog_path or CATALOG
    timestamp = now or datetime.now(timezone.utc)
    cached = None
    if path.exists():
        try:
            cached=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):pass
    if cached and cached.get('companies'):
        try:
            checked=datetime.fromisoformat(cached['refreshed_at'].replace('Z','+00:00'))
            if timestamp-checked<timedelta(days=7) and len(cached['companies'])>=min(max_boards,cached.get('directory_boards_found',0)):
                return cached, 'cache'
        except (KeyError, ValueError, TypeError):pass
    try:
        if getter is None:
            def getter(url):
                req=Request(url,headers={'User-Agent':'BioDataInternshipRadar/2.0 (noncommercial; public job boards)', 'Accept':'application/json,text/csv'})
                with urlopen(req,timeout=45) as response:
                    data=response.read(12_000_001)
                    if len(data)>12_000_000: raise ValueError('Directory unexpectedly large')
                    return data.decode('utf-8-sig')
        rows=[]; warnings=[]; source_counts={}
        try:
            base=parse_directory(getter(DIRECTORY_URL))
            rows=base
            source_counts['LastRound AI']=len(base)
        except Exception as exc:warnings.append(f'LastRound AI: {type(exc).__name__}')
        try:
            fresh=parse_live_directory(getter(LIVE_DIRECTORY_URL))
            rows=unique_entries(rows,fresh)
            source_counts['Public Job Board Directory']=len(fresh)
        except Exception as exc:warnings.append(f'Public Job Board Directory: {type(exc).__name__}')
        if len(rows)<400: raise ValueError(f'Only {len(rows)} valid boards; keeping prior catalog')
        result={'refreshed_at':timestamp.isoformat(),
                'source':ATTRIBUTION,'additional_source':LIVE_ATTRIBUTION,
                'license':'LastRound AI data CC BY 4.0; source attribution in README',
                'directory_boards_found':len(rows),'source_counts':source_counts,
                'refresh_warnings':warnings,
                'companies':prioritized(rows,max_boards)}
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result,'refreshed'+ (' with partial source errors' if warnings else '')
    except Exception as exc:
        # No fake success: keep last known catalog if a refresh fails.
        if cached and cached.get('companies'):
            return cached,f'stale cache: {type(exc).__name__}: {exc}'
        return {'companies':[],'directory_boards_found':0,'source':ATTRIBUTION},f'error: {type(exc).__name__}: {exc}'


def choose_batch(entries, pinned_sources, boards_per_run=500, now=None, slot_minutes=480):
    """Fixed 8-hour windows: every catalog board appears within ceil(N/batch) scans.

    pinned board endpoints are always scanned independently, even if duplicated
    in the directory; exact vendor+slug duplicates are removed.
    """
    timestamp=now or datetime.now(timezone.utc)
    pinned_keys={(s.get('ats'),s.get('slug','').lower()) for s in pinned_sources if s.get('slug')}
    pool=[e for e in entries if (e.get('ats'),e.get('slug','').lower()) not in pinned_keys]
    pool.sort(key=lambda e:(-e.get('directory_rank',0),e['name'].casefold(),e['id']))
    batch_size=max(1,int(boards_per_run))
    # Interleave the prioritized catalog across batches so every run searches
    # some life-science, AI/data and cross-industry employers.
    number_of_batches=(len(pool)+batch_size-1)//batch_size
    chunks=[[] for _ in range(number_of_batches)]
    for index, entry in enumerate(pool):
        chunks[index % number_of_batches].append(entry)
    if not chunks:return []
    # Rotate at the broad scan's cadence (hourly in production).
    slot=int(timestamp.timestamp())//(max(1,int(slot_minutes))*60)
    return chunks[slot % len(chunks)]
