import unittest
import json
from scripts import fetch_jobs as f
from scripts.pay import extract_pay


class PayTests(unittest.TestCase):
    def test_parses_explicit_hourly_without_personal_threshold(self):
        x = extract_pay({'description': 'Base Salary: $37/hr.'})
        self.assertEqual(x['hourly_min'], 37)
        self.assertEqual(x['basis'], 'stated_hourly')
        self.assertNotIn('pay_tier', x)

    def test_hourly_range_retained(self):
        x = extract_pay({'description': 'The hourly rate range is $18.90-$58.90 per hour.'})
        self.assertEqual(x['hourly_max'], 58.90)

    def test_no_salary_is_unknown(self):
        self.assertEqual(extract_pay({'description': 'Intern will use statistics and python.'})['basis'], 'unknown')

    def test_bonus_is_not_base_pay(self):
        self.assertEqual(extract_pay({'description': 'The annual base salary is $80,000 with bonus of $10,000.'})['basis'], 'unknown')

    def test_lever_hourly(self):
        x = extract_pay({'salary_range': {'currency':'USD','interval':'hour','min':48,'max':65}})
        self.assertEqual(x['basis'], 'stated_hourly')
        self.assertEqual(x['hourly_min'], 48)

    def test_ashby_hourly_excludes_equity(self):
        job = {'compensation': {'summaryComponents': [
            {'compensationType':'EquityPercentage','currencyCode':None,'interval':'NONE','minValue':0.1,'maxValue':0.5},
            {'compensationType':'Salary','currencyCode':'USD','interval':'1 HOUR','minValue':38,'maxValue':61},
        ]}}
        x = extract_pay(job)
        self.assertEqual(x['hourly_min'], 38)
        self.assertEqual(x['basis'], 'stated_hourly')

    def test_annualized_not_confirmed_hourly(self):
        x = extract_pay({'salary_range': {'currency':'USD','interval':'year','min':104000,'max':124800}})
        self.assertEqual(x['hourly_min'], 50)
        self.assertEqual(x['basis'], 'annualized_estimate')


class BroadDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.prefs = json.loads(f.PREFS.read_text())
        self.src = {'id':'zapply-2027','name':'Zapply 2027','sector':'Cross-industry','stage':'Mixed','ats':'github_markdown'}

    def test_upstream_markdown_parser(self):
        lines = ['| Company | Role | Location | Posted | Visa | Apply |','|---|---|---|---|---|---|']
        for i in range(12):
            lines.append(f'| Startup{i} | Summer 2027 Data Scientist Intern | California | 1d | | [Apply](https://jobs.ashbyhq.com/startup/{i}?utm_source=source) |')
        raw = f.markdown_jobs('\n'.join(lines), self.src)
        self.assertEqual(len(raw), 12)
        self.assertEqual(raw[0]['company'],'Startup0')
        self.assertEqual(raw[0]['url'], 'https://jobs.ashbyhq.com/startup/0?utm_source=source')
        self.assertIsNotNone(f.match_job(raw[0],self.prefs))

    def test_short_malformed_feed_fails_without_closing_positions(self):
        with self.assertRaises(ValueError):
            f.markdown_jobs('| Foo | Intern | NY | 1d | | [Apply](https://jobs.example.com/1) |',self.src)

    def test_spring_only_is_excluded(self):
        j={'title':'2027 Spring Data Science Intern','description':'Python','employment_type':''}
        self.assertIsNone(f.match_job(j,self.prefs))

    def test_summer_and_spring_allowed(self):
        j={'title':'2027 Summer or Spring Data Science Intern','description':'Python','employment_type':''}
        self.assertIsNotNone(f.match_job(j,self.prefs))

    def test_undated_intern_is_eligible_for_review(self):
        j={'title':'Machine Learning Intern','description':'Python','employment_type':''}
        self.assertEqual(f.match_job(j,self.prefs)['season'],'season_unconfirmed')


if __name__=='__main__':
    unittest.main()
