"""Independent scan-result contract and empty-coverage regressions."""
import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('coverage_hook',pathlib.Path(__file__).with_name('hook.py'))
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)

class ScanCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def scan(self,result):
        response=type('Response',(),{'returncode':0,'stdout':json.dumps(result)})()
        with patch.object(hook.subprocess,'run',return_value=response):
            return hook.run_scan(self.root,{})
    def test_existing_source_missing_from_successful_result_is_rejected(self):
        (self.root/'app.js').write_text('const n = 1;')
        with self.assertRaisesRegex(RuntimeError,'coverage'):self.scan({})
    def test_partial_scan_is_rejected(self):
        (self.root/'one.py').write_text('n = 1')
        (self.root/'two.ts').write_text('const n = 1;')
        with self.assertRaisesRegex(RuntimeError,'coverage'):
            self.scan({'one.py':{'hash':'a'*64,'metrics':{}}})
    def test_invalid_payloads_are_rejected(self):
        for result in [[],{'app.js':{}},{'app.js':{'hash':'a'*64,'metrics':[]}}]:
            with self.subTest(result=result),self.assertRaises(RuntimeError):self.scan(result)
    def test_covered_source_is_accepted(self):
        (self.root/'app.js').write_text('const n = 1;')
        result={'app.js':{'hash':'a'*64,'metrics':{}}}
        self.assertEqual(self.scan(result),result)
    def test_empty_root_is_explicitly_uncertified(self):
        self.assertEqual(self.scan({}),{})
        result=hook.coverage_outcome({},'Stop')
        self.assertIn('not performed',result['systemMessage'])
    def test_instruction_checks_do_not_mask_empty_source_coverage(self):
        result=hook.coverage_outcome({'@md:global':{'hash':'a'*64,'metrics':{}}},'Stop')
        self.assertIn('verification not performed',result['systemMessage'])
    def test_missing_root_is_not_an_empty_success(self):
        self.root=self.root/'missing'
        with self.assertRaises(OSError):self.scan({})
    def test_unsupported_source_cannot_disappear(self):
        (self.root/'view.vue').write_text('<template/>')
        with self.assertRaisesRegex(RuntimeError,'coverage'):self.scan({})
    def test_unregistered_stop_is_explicitly_uncertified(self):
        with patch.object(hook,'STATE',self.root):
            result=hook.stop_roots({'cwd':str(self.root)},'unknown')
        self.assertIn('verification not performed',result['systemMessage'])
    def test_ignored_dependencies_do_not_require_coverage(self):
        (self.root/'node_modules').mkdir()
        (self.root/'node_modules'/'dependency.js').write_text('')
        self.assertEqual(self.scan({}),{})

if __name__=='__main__':unittest.main()
