"""Foreign hook debt must not become ownership in an unrelated project."""
import unittest
import test_failure_paths


class CrossSessionScopeTests(unittest.TestCase):
    setUp = test_failure_paths.FailurePathTests.setUp
    tearDown = test_failure_paths.FailurePathTests.tearDown
    invoke = test_failure_paths.FailurePathTests.invoke

    def switch_to_unrelated(self):
        other = self.home/'unrelated'
        other.mkdir()
        self.invoke('PreToolUse', cwd=str(other))
        self.invoke('PostToolUse')

    def test_foreign_session_debt_does_not_block_unrelated_task(self):
        self.invoke('PreToolUse')
        self.invoke('PostToolUse')
        self.invoke('PreToolUse', session_id='foreign-writer')
        (self.project/'foreign.js').write_text('new Buffer(1);\n')
        self.invoke('PostToolUse')
        self.event['session_id'] = 'isolated-failure-test'
        self.switch_to_unrelated()
        result = self.invoke('Stop')
        self.assertNotEqual(result.get('decision'), 'block', result)
        self.assertIn('not certification', result['systemMessage'])

    def test_cleaned_owned_file_does_not_capture_future_foreign_edit(self):
        self.invoke('PreToolUse')
        (self.project/'app.js').write_text('const safe = 1;\n')
        self.invoke('PostToolUse')
        (self.project/'app.js').write_text('new Buffer(1);\n')
        self.switch_to_unrelated()
        result = self.invoke('Stop')
        self.assertNotEqual(result.get('decision'), 'block', result)
        self.assertIn('not certification', result['systemMessage'])
