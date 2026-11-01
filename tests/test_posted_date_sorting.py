import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
import fetch_jobs

class PostingDateOrderingTests(unittest.TestCase):
    def fixture(self, company, posted, first, focus, score=80):
        return {'status':'open','id':company,'company':company,
                'title':'Relevant Summer 2027 Intern','url':f'https://example.org/{company}',
                'location':'Boston','pay':{},'posted_at':posted,'first_seen_at':first,
                'score':score,'primary_focus':focus,'match_source':'Role title'}
    def test_actual_recent_post_beats_old_high_scoring_role(self):
        old=self.fixture('old_stats','2026-10-01','2026-11-01T01:00:00+00:00','Biostatistics / Statistical Programming',99)
        new=self.fixture('new_ds','2026-10-31','2026-11-01T01:00:00+00:00','Data Science / ML',60)
        with tempfile.TemporaryDirectory() as d,patch.object(fetch_jobs,'ROOT',Path(d)):
            fetch_jobs.write_openings({'updated_at':'2026-11-01T02:00:00+00:00','jobs':[old,new]})
            page=(Path(d)/'OPENINGS.md').read_text()
            self.assertLess(page.index('| new_ds |'),page.index('| old_stats |'))
            self.assertIn('2026-10-31',page)
            self.assertIn('2026-10-01',page)
            self.assertIn('First detected',page)
    def test_unknown_posting_date_is_not_faked_from_first_detection(self):
        unknown=self.fixture('unknown','', '2026-11-01T01:50:00+00:00','Data Science / ML')
        known=self.fixture('known','2026-10-30','2026-10-30T09:00:00+00:00','Data Science / ML')
        with tempfile.TemporaryDirectory() as d,patch.object(fetch_jobs,'ROOT',Path(d)):
            fetch_jobs.write_openings({'updated_at':'2026-11-01T02:00:00+00:00','jobs':[unknown,known]})
            page=(Path(d)/'OPENINGS.md').read_text()
            self.assertLess(page.index('| known |'),page.index('| unknown |'))
            self.assertIn('| Not provided | unknown |',page)
            self.assertIn('2026-11-01 01:50 UTC',page)
    def test_posting_time_shown_only_when_employer_supplies_timezone(self):
        self.assertEqual(fetch_jobs.posted_display('2026-10-31'),'2026-10-31')
        self.assertEqual(fetch_jobs.posted_display('2026-10-31T14:15:00Z'),'2026-10-31 14:15 UTC')
        self.assertEqual(fetch_jobs.posted_display('yesterday'),'Not provided')
    def test_same_date_newest_hour_first(self):
        morning=self.fixture('morning','2026-10-31T10:00:00Z','2026-11-01T01:00:00Z','Data Science / ML')
        evening=self.fixture('evening','2026-10-31T22:00:00Z','2026-11-01T01:00:00Z','Data Science / ML')
        with tempfile.TemporaryDirectory() as d,patch.object(fetch_jobs,'ROOT',Path(d)):
            fetch_jobs.write_openings({'updated_at':'2026-11-01T02:00:00+00:00','jobs':[morning,evening]})
            page=(Path(d)/'OPENINGS.md').read_text()
            self.assertLess(page.index('| evening |'),page.index('| morning |'))

if __name__=='__main__':unittest.main()
