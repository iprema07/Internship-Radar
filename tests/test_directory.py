"""Offline validation of expanding employer coverage and safe source parsing."""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from scripts.directory import (
    parse_directory, parse_live_directory, prioritized, choose_batch,
    load_and_refresh, classify
)


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 31, 0, 0, tzinfo=timezone.utc)

    def test_csv_only_public_vendor_slugs(self):
        csv_text = ('ats_vendor,company_name,board_slug,last_crawled\n'
                    'ashby,"Candid Health",candidhealth,2026-08-01\n'
                    'greenhouse,"Freenome",freenome,2026-08-01\n'
                    'workday,"Bad domain",pretend,2026-08-01\n'
                    'lever,"Attack",https://bad.example.org,2026-08-01\n')
        entries = parse_directory(csv_text)
        self.assertEqual(len(entries), 2)
        self.assertIn('directory:ashby:candidhealth', [e['id'] for e in entries])

    def test_current_directory_validates_vendor_api_urls(self):
        inp=[{'platform':'workday','company':'Pharma Labs', 'api_url':'https://pharma.wd1.myworkdayjobs.com/wday/cxs/pharma/Careers/jobs'},
             {'platform':'greenhouse','company':'Bio Alpha','token':'bioalpha'},
             {'platform':'workday','company':'Evil','api_url':'https://outside.example.com/jobs'},
             {'platform':'ashby','company':'Evil Again','token':'../etc'},
             {'platform':'workable','company':'Not supported','token':'workable'}]
        found=parse_live_directory(json.dumps(inp))
        self.assertEqual(len(found),2)
        wd=next(x for x in found if x['ats']=='workday')
        self.assertEqual(wd['site'],'Careers')
        self.assertEqual(wd['tenant'],'pharma')

    def test_2000_valid_directory_entries_can_be_selected(self):
        csv_text='ats_vendor,company_name,board_slug,last_crawled\n' + ''.join(
            f'greenhouse,Bio Company {i},bioco{i},2026-08-01\n' for i in range(2700))
        selected=prioritized(parse_directory(csv_text),max_boards=2000)
        self.assertEqual(len(selected),2000)
        self.assertEqual(len({x['id'] for x in selected}),2000)

    def test_rotation_covers_2000_in_four_cycles(self):
        entries=[{'id':f'directory:greenhouse:bio{i}', 'slug':f'bio{i}', 'ats':'greenhouse',
                  'name':f'Bio {i}', 'directory_rank':3} for i in range(2000)]
        batches=[]
        for slot in range(4):
            batches.append(choose_batch(entries,[],500,self.start+timedelta(hours=8*slot)))
        self.assertTrue(all(len(b)==500 for b in batches))
        self.assertEqual(len({x['id'] for b in batches for x in b}),2000)

    def test_pin_does_not_duplicate_directory(self):
        a={'id':'directory:ashby:nabla','slug':'nabla','ats':'ashby','name':'Nabla','directory_rank':3}
        self.assertEqual(choose_batch([a],[{'ats':'ashby','slug':'nabla'}],500,self.start),[])

    def test_cache_works_and_weekly_refresh_works(self):
        csv_text='ats_vendor,company_name,board_slug,last_crawled\n'+ ''.join(
            f'ashby,Data Labs {i},lab{i},2026-08-01\n' for i in range(700))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'catalog.json'
            first,state=load_and_refresh(600,self.start,path,lambda u: csv_text if u.endswith('.csv') else '[]')
            self.assertEqual(state,'refreshed')
            self.assertEqual(len(first['companies']),600)
            second,state=load_and_refresh(600,self.start+timedelta(days=1),path,
                                         lambda u: self.fail('Cache must avoid new HTTP requests'))
            self.assertEqual(state,'cache')
            self.assertEqual(len(second['companies']),600)

    def test_failed_refresh_keeps_cached(self):
        csv_text='ats_vendor,company_name,board_slug,last_crawled\n'+ ''.join(
            f'greenhouse,Bio Labs {i},bio{i},2026-08-01\n' for i in range(550))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'catalog.json'
            first,_=load_and_refresh(500,self.start,path,lambda u: csv_text if u.endswith('.csv') else '[]')
            second,status=load_and_refresh(500,self.start+timedelta(days=8),path,
                    lambda url: (_ for _ in ()).throw(OSError('temporary network error')))
            self.assertEqual(len(first['companies']),len(second['companies']))
            self.assertIn('stale cache',status)

if __name__=='__main__':unittest.main()
