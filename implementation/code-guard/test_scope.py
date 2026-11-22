"""Task ownership must follow tool windows, never elapsed chat lifetime."""
import json
import unittest
import test_failure_paths


class ScopeTests(unittest.TestCase):
    setUp = test_failure_paths.FailurePathTests.setUp
    tearDown = test_failure_paths.FailurePathTests.tearDown
    invoke = test_failure_paths.FailurePathTests.invoke
    def baseline_bytes(self):
        return {p.name: p.read_bytes() for p in (self.engine/'state').glob('baseline-*.json')}

    def test_other_repository_changes_after_read_do_not_block(self):
        self.invoke('PreToolUse')
        self.invoke('PostToolUse')
        before = self.baseline_bytes()
        (self.project/'foreign.js').write_text('new Buffer(1);\n')
        other = self.home/'other'
        other.mkdir()
        self.invoke('PreToolUse', cwd=str(other))
        self.invoke('PostToolUse')
        result = self.invoke('Stop')
        self.assertNotEqual(result.get('decision'), 'block', result)
        self.assertIn('not certification', result['systemMessage'])
        for name, content in before.items():
            self.assertEqual((self.engine/'state'/name).read_bytes(), content)

    def test_external_change_before_read_tool_is_not_owned(self):
        self.invoke('PreToolUse')
        self.invoke('PostToolUse')
        (self.project/'foreign.js').write_text('new Buffer(1);\n')
        self.invoke('PreToolUse')
        self.invoke('PostToolUse')
        self.assertNotEqual(self.invoke('Stop').get('decision'), 'block')

    def test_both_written_repositories_remain_enforced(self):
        self.invoke('PreToolUse')
        (self.project/'one.js').write_text('new Buffer(1);\n')
        self.invoke('PostToolUse')
        other = self.home/'other'
        other.mkdir()
        self.invoke('PreToolUse', cwd=str(other))
        (other/'two.js').write_text('new Buffer(2);\n')
        self.invoke('PostToolUse')
        self.assertEqual(self.invoke('Stop')['decision'], 'block')
        (self.project/'one.js').write_text('const one = 1;\n')
        result = self.invoke('Stop', turn_id='second-stop')
        self.assertEqual(result['decision'], 'block')
        self.assertIn('two.js', result['reason'])
        (other/'two.js').write_text('const two = 2;\n')
        self.assertEqual(self.invoke('Stop'), {})

    def test_legacy_observation_ledger_is_preserved_without_false_ownership(self):
        self.invoke('PreToolUse')
        self.invoke('PostToolUse')
        state = self.engine/'state'
        for path in state.glob('*-*.json'):
            if path.name.startswith(('baseline-', 'pending-')):
                continue
            data = json.loads(path.read_text())
            for key in ('scope_version', 'owned', 'inflight'):
                data.pop(key, None)
            path.write_text(json.dumps(data))
        (self.project/'foreign.js').write_text('new Buffer(1);\n')
        for path in state.glob('pending-*.json'):
            path.write_text(json.dumps(['foreign.js']))
        result = self.invoke('Stop')
        self.assertNotEqual(result.get('decision'), 'block', result)
        ledgers = [json.loads(p.read_text()) for p in state.glob('pending-*.json')]
        self.assertTrue(any('foreign.js' in d.get('legacy_unattributed', []) for d in ledgers))
        self.invoke('PreToolUse')
        (self.project/'foreign.js').write_text('new Buffer(1);\nnew Buffer(2);\n')
        self.invoke('PostToolUse')
        self.assertEqual(self.invoke('Stop', turn_id='own-edit')['decision'], 'block')

    def test_async_write_after_post_is_still_caught(self):
        self.invoke('PreToolUse')
        self.invoke('PostToolUse', tool_response={'session_id': 123})
        (self.project/'late.js').write_text('new Buffer(1);\n')
        self.assertEqual(self.invoke('Stop')['decision'], 'block')
