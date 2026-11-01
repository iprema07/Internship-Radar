"""Conservative base-pay extraction. No bonus, equity or OTE treated as hourly pay."""
from __future__ import annotations
import re

HOURLY = re.compile(
    r'\$\s*(\d{1,3}(?:\.\d{1,2})?)\s*'
    r'(?:[-–—]\s*\$?\s*(\d{1,3}(?:\.\d{1,2})?)\s*)?'
    r'(?:/\s*(?:hour|hr)\b|per\s+hour\b|an\s+hour\b|hourly\b)', re.I)
HOURLY_PREFIX = re.compile(
    r'(?:hourly\s+(?:base\s+)?(?:pay|rate|salary|range)|(?:base\s+)?pay\s+rate)\s*(?:is|of|:|-)?\s*'
    r'\$\s*(\d{1,3}(?:\.\d{1,2})?)'
    r'(?:\s*[-–—]\s*\$?\s*(\d{1,3}(?:\.\d{1,2})?))?', re.I)


def hourly_range(description):
    """Only explicit dollar-per-hour text; not full-time wages or unmarked amounts."""
    text = str(description or '')
    candidate = HOURLY.search(text) or HOURLY_PREFIX.search(text)
    if not candidate:
        return None
    low = float(candidate.group(1))
    high = float(candidate.group(2) or low)
    if not (8 <= low <= high <= 300):
        return None
    return low, high


def structured_pay(job):
    """Lever salaryRange and Ashby salary components. Return USD base only."""
    v = job.get('salary_range') or {}
    if v and isinstance(v, dict) and str(v.get('currency', '')).upper() in ('USD', 'US DOLLAR', '$'):
        interval = str(v.get('interval') or '').lower()
        try:
            low, high = float(v['min']), float(v['max'])
        except (TypeError, ValueError, KeyError):
            return None
        if 0 < low <= high:
            if 'hour' in interval:
                return {'hourly_min': round(low, 2), 'hourly_max': round(high, 2), 'basis': 'stated_hourly'}
            if 'year' in interval:
                return {'hourly_min': round(low / 2080, 2), 'hourly_max': round(high / 2080, 2), 'basis': 'annualized_estimate'}
    comp = job.get('compensation') or {}
    # Summary components can represent different geography tiers. We take only USD salary components.
    components = comp.get('summaryComponents') or [c for t in comp.get('compensationTiers', []) for c in t.get('components', [])]
    groups = {'hour': [], 'year': []}
    for c in components:
        if c.get('compensationType') not in ('Salary', 'BaseSalary') or c.get('currencyCode') != 'USD':
            continue
        interval = str(c.get('interval', '')).lower()
        try:
            lo, hi = float(c['minValue']), float(c['maxValue'])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= 0 or hi < lo:
            continue
        typ = 'hour' if 'hour' in interval else 'year' if 'year' in interval else None
        if typ:
            groups[typ].append((lo, hi))
    for typ in ('hour', 'year'):
        if groups[typ]:
            vals = groups[typ]
            factor = 1 if typ == 'hour' else 2080
            return {'hourly_min': round(min(x[0] for x in vals) / factor, 2),
                    'hourly_max': round(max(x[1] for x in vals) / factor, 2),
                    'basis': 'stated_hourly' if typ == 'hour' else 'annualized_estimate'}
    return None


def extract_pay(job, prefs=None):
    """Extract advertised hourly/annualized base pay; personal comparisons are browser-local."""
    result = structured_pay(job)
    if result is None:
        parsed = hourly_range(job.get('description') or '')
        result = ({'hourly_min': parsed[0], 'hourly_max': parsed[1], 'basis': 'stated_hourly'}
                  if parsed else {'hourly_min': None, 'hourly_max': None, 'basis': 'unknown'})
    return result
