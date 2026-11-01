"""Offline tests for high recall with full descriptions and no external alerts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import fetch_jobs

class DescriptionRecallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefs=json.loads(fetch_jobs.PREFS.read_text())
    def job(self,title,desc,employment_type='Intern',status='full'):
        return {'id':'test:desc','title':title,'description':desc,'department':'',
                'employment_type':employment_type,'description_status':status,
                'location':'Ann Arbor, MI','url':'https://example.org/jobs/1','posted_at':'','modified_at':''}

    def test_generic_intern_hidden_statistics_in_full_description(self):
        j=self.job('Research Operations Intern Summer 2027',
            'Conduct longitudinal analysis and survival analysis using R to evaluate clinical trial outcomes.')
        x=fetch_jobs.match_job(j,self.prefs)
        self.assertIsNotNone(x)
        self.assertEqual(x['primary_focus'],'Statistics / Statistical Methods')
        self.assertGreaterEqual(x['method_signal_count'],2)

    def test_generic_scientific_intern_with_modeling_in_description(self):
        j=self.job('Scientific Intern Summer 2027',
            'Develop statistical modeling pipelines for clinical data and evaluate models with Python.')
        x=fetch_jobs.match_job(j,self.prefs)
        self.assertIsNotNone(x)
        self.assertIn(x['fit_tier'],('review','strong'))

    def test_no_weak_python_mention_from_unrelated_role(self):
        j=self.job('Events Intern Summer 2027','Organize meetings; familiarity with Python is nice.')
        self.assertIsNone(fetch_jobs.match_job(j,self.prefs))

    def test_description_missing_is_review_not_strong(self):
        j=self.job('Data Science Intern Summer 2027','',status='missing')
        x=fetch_jobs.match_job(j,self.prefs)
        self.assertEqual(x['fit_tier'],'review')

    def test_lever_combines_description_lists_and_no_undefined_posted(self):
        src={'slug':'example','region':'us'}
        payload=[{'id':'123','text':'Research Intern','descriptionPlain':'Analyze trial data',
                  'lists':[{'text':'What you will do','content':'<p>Survival analysis and causal inference</p>'}],
                  'categories':{'commitment':'Internship'}}]
        with patch.object(fetch_jobs,'get_json',return_value=payload):
            jobs=list(fetch_jobs.lever(src))
        self.assertIn('survival analysis',jobs[0]['description'].lower())
        self.assertEqual(jobs[0]['posted_at'],'')
        self.assertEqual(jobs[0]['description_status'],'full')

    def test_workday_loads_candidate_details(self):
        src={'host':'example.wd5.myworkdayjobs.com','tenant':'example','site':'External','search':'intern'}
        urls=[]
        def get(url,post_data=None):
            urls.append(url)
            if post_data is not None:return {'jobPostings':[{'title':'Research Intern','externalPath':'/job/US/Research-Intern_R1','locationsText':'US'}],'total':1}
            return {'jobPostingInfo':{'jobDescription':'<p>Survival analysis and longitudinal models in R</p>','startDate':'2026-10-31'}}
        with patch.object(fetch_jobs,'get_json',side_effect=get),patch.object(fetch_jobs.time,'sleep'):
            jobs=list(fetch_jobs.workday(src,self.prefs))
        self.assertEqual(jobs[0]['description_status'],'full')
        self.assertIn('survival analysis',jobs[0]['description'].lower())
        self.assertEqual(len(urls),2)

    def test_public_automation_has_no_external_notification_service(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/'.github/workflows/update.yml').read_text()
        self.assertNotIn('secrets.',workflow)
        self.assertNotIn('outbox',workflow)
        self.assertNotIn('notify_new_positions',fetch_jobs.run.__code__.co_names)

if __name__=='__main__':unittest.main()
