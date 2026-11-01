import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import fetch_jobs as f


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.prefs=json.loads(f.PREFS.read_text())
        self.example={'id':'greenhouse:test:123','title':'2027 Summer Biostatistics Intern','url':'https://example.com/job',
                      'location':'Ann Arbor, MI','description':'We use Python, R, and SAS. MS degree students welcome.',
                      'employment_type':'','department':'','posted_at':'','modified_at':''}

    def test_interesting_internship(self):
        match=f.match_job(self.example,self.prefs)
        self.assertIsNotNone(match)
        self.assertIn('Biostatistics / Statistical Programming',match['focus'])
        self.assertGreaterEqual(match['score'],75)

    def test_2026_internship_is_excluded(self):
        self.assertIsNone(f.match_job({**self.example,'title':'2026 Summer Biostatistics Intern'},self.prefs))

    def test_senior_fulltime_is_excluded(self):
        self.assertIsNone(f.match_job({**self.example,'title':'Director, Data Science'},self.prefs))

    def test_undated_internship_stays(self):
        self.assertIsNotNone(f.match_job({**self.example,'title':'Data Science Intern'},self.prefs))

    def test_html_stripping(self):
        self.assertEqual(f.plain_text('&lt;p&gt;Hello &amp;amp; world&lt;/p&gt;'),'Hello & world')

    def test_generic_software_engineering_is_not_a_match(self):
        job={**self.example,'title':'Software Engineer (Machine Learning) Intern Summer 2027'}
        self.assertIsNone(f.match_job(job,self.prefs))

    def test_data_engineering_remains_a_match(self):
        job={**self.example,'title':'Summer 2027 Data Engineer Intern'}
        self.assertIsNotNone(f.match_job(job,self.prefs))

    def test_generic_wet_lab_research_scientist_is_excluded(self):
        job={**self.example,'title':'2027 Research Scientist Intern','description':'Cell culture and pipetting.'}
        self.assertIsNone(f.match_job(job,self.prefs))

    def test_statistical_research_scientist_is_included(self):
        job={**self.example,'title':'2027 Research Scientist Intern','description':'Analyze statistical models using Python and causal inference.'}
        self.assertIsNotNone(f.match_job(job,self.prefs))

    def test_stable_normalization(self):
        match=f.match_job(self.example,self.prefs)
        src={'id':'test','name':'Test Bio','sector':'Biotech','ats':'greenhouse'}
        old={self.example['id']:{'first_seen':'2026-10-20'}}
        result=f.normalize(self.example,src,match,old,'2026-10-31')
        self.assertEqual(result['first_seen'],'2026-10-20')
        self.assertEqual(result['missing_scans'],0)


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.data=root/'jobs.json'
        self.sources=root/'companies.json'
        self.prefs=root/'preferences.json'
        self.sources.write_text(json.dumps({'sources':[{'id':'test','name':'Test Bio','sector':'Biotech','ats':'greenhouse','slug':'test'}]}))
        self.prefs.write_text(f.PREFS.read_text())
        self.sample={'id':'greenhouse:test:123','title':'2027 Data Science Intern','url':'https://example.com/job',
                     'location':'Remote','description':'Python SQL','employment_type':'',
                     'department':'','posted_at':'','modified_at':''}
        self.data.write_text(json.dumps({'jobs':[]}))
        self.patchers=[patch.object(f,'DATA',self.data),patch.object(f,'SOURCES',self.sources),
                       patch.object(f,'PREFS',self.prefs),patch.object(f,'README',root/'not-found.md')]
        for p in self.patchers:p.start()

    def tearDown(self):
        for p in self.patchers:p.stop()
        self.temp.cleanup()

    def run_scan(self,fn,day):
        return f.run(fetchers={'greenhouse':fn},now=day+'T12:00:00+00:00')

    def test_first_seen_survives_subsequent_scan(self):
        first=self.run_scan(lambda s:[self.sample],'2026-10-31')
        second=self.run_scan(lambda s:[self.sample],'2026-11-02')
        self.assertEqual(second['jobs'][0]['first_seen'],'2026-10-31')
        self.assertEqual(second['jobs'][0]['last_seen'],'2026-11-02')

    def test_failed_board_does_not_close_jobs(self):
        self.run_scan(lambda s:[self.sample],'2026-10-31')
        def fail(src):raise ValueError('HTTP 503 unavailable')
        second=self.run_scan(fail,'2026-11-02')
        self.assertEqual(second['jobs'][0]['status'],'open')
        self.assertEqual(second['counts']['sources_failed'],1)

    def test_two_successful_misses_close_job(self):
        self.run_scan(lambda s:[self.sample],'2026-10-31')
        first_miss=self.run_scan(lambda s:[],'2026-11-01')
        self.assertEqual(first_miss['jobs'][0]['status'],'open')
        second_miss=self.run_scan(lambda s:[],'2026-11-02')
        self.assertEqual(second_miss['jobs'][0]['status'],'closed')
        self.assertEqual(second_miss['jobs'][0]['closed_at'],'2026-11-02')


if __name__=='__main__':unittest.main()
