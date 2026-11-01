import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from directory import choose_batch
import fetch_jobs

NOW = '2026-10-31T20:30:00+00:00'

class FastDetectionTests(unittest.TestCase):
    def test_lookback_requires_real_timestamp(self):
        self.assertIsNone(fetch_jobs.recent_age_hours('2026-10-31', NOW))
        self.assertIsNone(fetch_jobs.recent_age_hours('', NOW))
        self.assertAlmostEqual(fetch_jobs.recent_age_hours('2026-10-31T19:30:00Z', NOW),1)

    def test_first_seen_at_stays_stable(self):
        job={'id':'greenhouse:abc:1','title':'Biostatistics Intern','company':'ABC','location':'Boston, MA',
             'department':'Statistics','url':'https://job-boards.greenhouse.io/abc/jobs/1','posted_at':'', 'modified_at':''}
        src={'ats':'greenhouse','id':'abc','name':'ABC','sector':'Biotechnology'}
        meta={'focus':['Biostatistics / Statistical Programming'],'score':85,'pay':{},'season':'summer_confirmed','reasons':[]}
        first=fetch_jobs.normalize(job,src,meta,{},'2026-10-31', NOW)
        later=fetch_jobs.normalize(job,src,meta,{first['id']:first},'2026-11-01','2026-11-01T09:00:00Z')
        self.assertEqual(later['first_seen_at'],NOW)
        self.assertEqual(later['last_seen_at'],'2026-11-01T09:00:00Z')

    def test_backfilled_old_date_does_not_fake_hour(self):
        job={'id':'greenhouse:abc:1','title':'Biostatistics Intern','location':'Boston, MA',
             'department':'Statistics','url':'https://job-boards.greenhouse.io/abc/jobs/1','posted_at':'', 'modified_at':''}
        src={'ats':'greenhouse','id':'abc','name':'ABC','sector':'Biotechnology'}
        meta={'focus':['Biostatistics / Statistical Programming'],'score':85,'pay':{},'season':'summer_confirmed','reasons':[]}
        original={'greenhouse:abc:1':{'first_seen':'2026-10-20'}}
        j=fetch_jobs.normalize(job,src,meta,original,'2026-10-31',NOW)
        self.assertIsNone(j['first_seen_at'])

    def test_hourly_rotation_distributes_four_batches(self):
        entries=[{'id':str(i),'name':'Name '+str(i),'ats':'ashby','slug':'slug'+str(i),'directory_rank':2} for i in range(2000)]
        t=datetime(2026,10,31,20,tzinfo=timezone.utc)
        batches=[choose_batch(entries,[],500,t+timedelta(hours=i),slot_minutes=60) for i in range(4)]
        self.assertEqual([len(x) for x in batches],[500]*4)
        self.assertEqual(len({e['id'] for batch in batches for e in batch}),2000)

    def test_rss_has_detected_and_direct_link(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(fetch_jobs,'ROOT',Path(d)):
                fetch_jobs.write_rss({'jobs':[{'id':'a','title':'Statistics Intern','company':'A&B',
                   'first_seen_at':NOW,'url':'https://example.com/job','status':'open'}]})
                xml=(Path(d)/'feed.xml').read_text()
                self.assertIn('https://example.com/job',xml)
                self.assertIn('A&amp;B',xml)
                self.assertIn('<pubDate>',xml)

if __name__=='__main__':unittest.main()
