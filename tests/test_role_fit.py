"""Tests for relevance and eligibility triage (not resume or compensation claims)."""
import json
import unittest
from scripts.fetch_jobs import match_job, PREFS

class RoleFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prefs=json.loads(PREFS.read_text())

    def job(self,title,description='Python, R and statistical models. Graduate student roles.',employment_type=''):
        return {'id':'test:1','title':title,'description':description,
                'url':'https://example.org/opening','location':'California',
                'department':'','employment_type':employment_type,
                'posted_at':'','modified_at':''}

    def test_core_biostat(self):
        result=match_job(self.job('Summer 2027 Biostatistics Intern'),self.prefs)
        self.assertIsNotNone(result)
        self.assertEqual(result['fit_tier'],'strong')
        self.assertEqual(result['season'],'summer_confirmed')

    def test_core_business_analytics(self):
        result=match_job(self.job('Business Analytics Summer Analyst 2027'),self.prefs)
        self.assertIsNotNone(result)
        self.assertIn('Analytics / BI',result['focus'])

    def test_related_data_engineering(self):
        result=match_job(self.job('2027 Data Engineer Intern'),self.prefs)
        self.assertIsNotNone(result)
        self.assertEqual(result['fit_tier'],'related')

    def test_quant_finance_is_excluded(self):
        self.assertIsNone(match_job(self.job('Quantitative Research Intern Summer 2027'),self.prefs))
        self.assertIsNone(match_job(self.job('Quant Trading Intern Summer 2027'),self.prefs))
        self.assertIsNone(match_job(self.job('Portfolio Research Analyst Intern Summer 2027'),self.prefs))

    def test_generic_simulation_is_not_assumed_relevant(self):
        self.assertIsNone(match_job(self.job('Simulation Intern Summer 2027', 'Mechanical simulation of aircraft structures.'),self.prefs))

    def test_generic_software_eng_excluded(self):
        self.assertIsNone(match_job(self.job('Software Engineer Machine Learning Intern'),self.prefs))

    def test_ml_engineer_excluded(self):
        self.assertIsNone(match_job(self.job('Machine Learning Engineer Intern'),self.prefs))

    def test_wet_lab_excluded(self):
        self.assertIsNone(match_job(self.job('Research Scientist Intern','Cell culture and pipetting.'),self.prefs))

    def test_analytical_scientist_reviewed(self):
        x=match_job(self.job('Research Scientist Intern','Statistical models and causal inference using Python.'),self.prefs)
        self.assertIsNotNone(x)
        self.assertIn('Statistics / Statistical Methods',x['focus'])

    def test_phd_only_excluded(self):
        self.assertIsNone(match_job(self.job('PhD Data Science Intern'),self.prefs))
        self.assertIsNone(match_job(self.job('Summer 2027 Data Science Intern','A PhD is required. Work with Python and SQL.'),self.prefs))

    def test_master_or_phd_kept(self):
        self.assertIsNotNone(match_job(self.job('MS or PhD Data Science Intern'),self.prefs))

    def test_undergrad_only_excluded(self):
        self.assertIsNone(match_job(self.job('Data Science Intern','Undergraduate only. No other degree required.'),self.prefs))

    def test_undated_summer_flag(self):
        x=match_job(self.job('Data Science Intern'),self.prefs)
        self.assertEqual(x['season'],'season_unconfirmed')

    def test_fall_only_excluded(self):
        self.assertIsNone(match_job(self.job('Fall 2027 Data Science Intern'),self.prefs))

    def test_pay_does_not_influence_relevance_score(self):
        a=match_job(self.job('2027 Data Science Intern','Python, R'),self.prefs)
        b=match_job(self.job('2027 Data Science Intern','Python, R. Hourly salary $80 per hour.'),self.prefs)
        self.assertEqual(a['score'],b['score'])


    def test_healthcare_consulting_with_analytics(self):
        job=self.job('Healthcare Consulting Summer Analyst 2027', 'Research health delivery systems; analyze datasets in SQL and Excel.')
        result=match_job(job,self.prefs)
        self.assertIsNotNone(result)
        self.assertIn('Strategy / Consulting',result['focus'])

    def test_product_analytics_from_any_industry(self):
        result=match_job(self.job('Product Analytics Intern 2027', 'Experimentation, SQL, Python and causal inference at a robotics company.'),self.prefs)
        self.assertIsNotNone(result)
        self.assertIn('Analytics / BI',result['focus'])

    def test_business_analyst_role(self):
        result=match_job(self.job('Business Analyst Intern 2027', 'Analyze workflows and customer outcomes in Python and SQL.'),self.prefs)
        self.assertIsNotNone(result)
        self.assertIn('Strategy / Consulting',result['focus'])

    def test_generic_business_analyst_requires_evidence(self):
        result=match_job(self.job('Business Analyst Intern 2027', 'Manage inboxes and schedule meetings.'),self.prefs)
        self.assertIsNone(result)

    def test_ml_analytics_not_ml_engineering(self):
        self.assertIsNotNone(match_job(self.job('Machine Learning Research Intern 2027','Statistical modeling using scikit-learn.'),self.prefs))
        self.assertIsNone(match_job(self.job('Machine Learning Engineer Intern 2027','Build API systems.'),self.prefs))

    def test_wetlab_bio_not_auto_added(self):
        self.assertIsNone(match_job(self.job('Cell Biology Research Intern 2027','Pipetting, immunohistochemistry, and cell culture.'),self.prefs))

    def test_fintech_data_science_is_relevant(self):
        self.assertIsNotNone(match_job(self.job('Data Science Intern 2027','Python, analytics, A/B testing for financial software.'),self.prefs))

    def test_research_data_analyst(self):
        self.assertIsNotNone(match_job(self.job('Research Data Analyst Intern 2027','Python and survey data quality.'),self.prefs))

if __name__=='__main__': unittest.main()

class ExpandedTitles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.prefs=json.loads(PREFS.read_text())
    def check(self,title):
        return match_job({'title':title,'description':'Statistics, R, SQL','employment_type':'','url':'https://example.org/a'},self.prefs)
    def test_statistics_title(self):self.assertIsNotNone(self.check('Statistics Intern Summer 2027'))
    def test_healthcare_analytics(self):self.assertIsNotNone(self.check('Healthcare Analytics Intern Summer 2027'))
    def test_data_ai(self):self.assertIsNotNone(self.check('Data & AI Intern 2027'))
    def test_ops_analyst(self):self.assertIsNotNone(self.check('Operations Analytics Intern 2027'))
