"""Regression tests: find the statistical jobs that generic tech lists overlook."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import fetch_jobs

class StatisticsDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefs=json.loads(fetch_jobs.PREFS.read_text())

    def opening(self,title,description='',department=''):
        return {
          'id':'demo:'+title,'title':title,'department':department,
          'description':description,'location':'Cambridge, MA','employment_type':'',
          'url':'https://example.org/apply','posted_at':'','modified_at':'',
        }

    def test_statistics_and_decision_sciences_title(self):
        r=fetch_jobs.match_job(self.opening('2027 Statistics & Decision Sciences Summer Intern','R SAS statistical methodology'),self.prefs)
        self.assertEqual(r['primary_focus'],'Statistics / Statistical Methods')
        self.assertEqual(r['fit_tier'],'strong')

    def test_statistical_programming_title(self):
        r=fetch_jobs.match_job(self.opening('2027 Biostatistics & Statistical Programming Intern','R Shiny and SAS'),self.prefs)
        self.assertEqual(r['primary_focus'],'Biostatistics / Statistical Programming')

    def test_survey_methods_title(self):
        r=fetch_jobs.match_job(self.opening('Survey Methodology Summer Intern 2027','Sample design and R analysis'),self.prefs)
        self.assertEqual(r['primary_focus'],'Statistics / Statistical Methods')

    def test_hidden_methods_under_generic_research_title(self):
        r=fetch_jobs.match_job(self.opening('2027 Research Intern','Conduct survival analysis and longitudinal models in R.'),self.prefs)
        self.assertEqual(r['primary_focus'],'Statistics / Statistical Methods')
        self.assertIn('Statistical work in description',r['reasons'][0])

    def test_hidden_statistics_department_plus_one_method(self):
        r=fetch_jobs.match_job(self.opening('Summer 2027 Research Intern','Build Bayesian models using R.','Research Decision Sciences'),self.prefs)
        self.assertEqual(r['primary_focus'],'Statistics / Statistical Methods')

    def test_do_not_assume_generic_analytics(self):
        self.assertIsNone(fetch_jobs.match_job(self.opening('Research Intern Summer 2027','Clean Excel files and write weekly reports.'),self.prefs))

    def test_biometrics_authentication_not_clinical_statistics(self):
        self.assertIsNone(fetch_jobs.match_job(self.opening('Biometrics Intern Summer 2027','Fingerprint sensor verification.','Hardware Security'),self.prefs))

    def test_phd_only_filtered_and_masters_option_kept(self):
        self.assertIsNone(fetch_jobs.match_job(self.opening('PhD Biostatistics Intern Summer 2027','Survival analysis'),self.prefs))
        self.assertIsNotNone(fetch_jobs.match_job(self.opening('MS or PhD Biostatistics Intern Summer 2027','Statistical modeling'),self.prefs))

    def test_data_science_remains_included(self):
        self.assertEqual(fetch_jobs.match_job(self.opening('Data Science Intern Summer 2027','Python SQL modeling'),self.prefs)['primary_focus'],'Data Science / ML')

    def test_browsable_markdown_stats_first_no_private_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetch_jobs,'ROOT',Path(tmp)):
                job_base={'status':'open','url':'https://jobs.example.org/apply','location':'Boston','pay':{'hourly_min':None},'season':'summer_confirmed','score':88}
                a={**job_base,'id':'stats1','company':'StatTech','title':'Biostatistics Intern','primary_focus':'Biostatistics / Statistical Programming'}
                b={**job_base,'id':'ds1','company':'DataTech','title':'Data Science Intern','primary_focus':'Data Science / ML'}
                fetch_jobs.write_openings({'updated_at':'2026-10-31T20:00:00Z','jobs':[a,b]})
                content=(Path(tmp)/'OPENINGS.md').read_text()
                self.assertIn('Sorted by employer posting date, newest first',content)
                self.assertIn('Biostatistics / Statistical Programming',content)
                self.assertIn('Data Science / ML',content)
                self.assertIn('https://jobs.example.org/apply',content)
                self.assertNotIn('minimum compensation',content.lower())
                self.assertNotIn('personal salary',content.lower())

if __name__=='__main__': unittest.main()
