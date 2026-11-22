"""Only this chat's new or worsened diagnostics are mandatory repairs."""
import unittest
import test_failure_paths


class CurrentChatScopeTests(unittest.TestCase):
    setUp = test_failure_paths.FailurePathTests.setUp
    tearDown = test_failure_paths.FailurePathTests.tearDown
    invoke = test_failure_paths.FailurePathTests.invoke

    def test_foreign_pending_in_same_root_is_not_adopted(self):
        self.invoke('PreToolUse', session_id='foreign')
        (self.project/'old.js').write_text('new Buffer(1);\n')
        self.invoke('PostToolUse')
        self.invoke('PreToolUse', session_id='current')
        self.invoke('PostToolUse')
        self.assertNotEqual(self.invoke('Stop').get('decision'), 'block')

    def test_editing_old_violation_without_worsening_is_allowed(self):
        self.invoke('PreToolUse', session_id='foreign')
        source = self.project/'old.js'
        source.write_text('new Buffer(1);\n')
        self.invoke('PostToolUse')
        self.invoke('PreToolUse', session_id='current')
        source.write_text('new Buffer(2);\n')
        self.invoke('PostToolUse')
        self.assertNotEqual(self.invoke('Stop').get('decision'), 'block')
        self.invoke('PreToolUse')
        source.write_text('new Buffer(2);\nnew Buffer(3);\n')
        self.invoke('PostToolUse')
        self.assertEqual(self.invoke('Stop').get('decision'), 'block')

    def test_own_failure_survives_next_turn(self):
        self.invoke('PreToolUse')
        (self.project/'new.js').write_text('new Buffer(1);\n')
        self.invoke('PostToolUse')
        self.assertEqual(self.invoke('Stop').get('decision'), 'block')
        self.invoke('PreToolUse', turn_id='next-turn')
        self.assertEqual(self.invoke('Stop').get('decision'), 'block')

    def test_unchanged_managed_failure_is_not_owned(self):
        import hook
        row = {'hash': 'old', 'metrics': {'md:managed-missing': {
            'value': 1, 'count': 1, 'line': 1, 'message': 'old deletion'}}}
        data = {'root': str(self.project), 'owned': [], 'task_baseline': {'doc': row}}
        errors, _ = hook.scoped_errors({'doc': row}, {}, data, {'files': ['doc']}, str(self.project))
        self.assertEqual(errors, [])
        data['history_audit'] = True
        errors, _ = hook.scoped_errors({'doc': row}, {}, data, {'files': []})
        self.assertTrue(errors)

    def test_new_managed_failure_remains_blocking(self):
        import hook
        row = {'hash': 'missing', 'metrics': {'md:managed-missing': {
            'value': 1, 'count': 1, 'line': 1, 'message': 'new deletion'}}}
        data = {'root': str(self.project), 'owned': ['doc'], 'task_baseline': {}}
        errors, _ = hook.scoped_errors({'doc': row}, {}, data, {'files': []})
        self.assertTrue(errors)

    def test_history_audit_requires_explicit_environment_opt_in(self):
        import json
        import os
        import subprocess
        self.invoke('PreToolUse', session_id='foreign')
        (self.project/'old.js').write_text('new Buffer(1);\n')
        self.invoke('PostToolUse')
        self.invoke('PreToolUse', session_id='current')
        self.assertNotEqual(self.invoke('Stop').get('decision'), 'block')
        event = dict(self.event, hook_event_name='Stop')
        result = subprocess.run(
            ['/usr/bin/python3', str(self.engine/'hook.py')],
            input=json.dumps(event), text=True, capture_output=True, check=True,
            env=dict(os.environ, CODEX_GUARD_SCOPE='history'))
        self.assertEqual(json.loads(result.stdout).get('decision'), 'block')
