"""User requirements: self-review is not independent; sentence repeats are caught."""
import unittest
from pathlib import Path
import test_md
import md_rules
import md_write


class NewGateTests(unittest.TestCase):
    setUp=test_md.MarkdownTests.setUp
    tearDown=test_md.MarkdownTests.tearDown
    author_review=test_md.MarkdownTests.author_review
    def test_self_signed_review_cannot_publish(self):
        draft=self.root/'candidate.stage'
        draft.write_text(self.new)
        with self.assertRaisesRegex(ValueError,'independent'):
            md_write.apply(self.target,draft,self.author_review())
        self.assertEqual(self.target.read_text(),self.old)

    def test_same_paragraph_duplicate_is_rejected(self):
        text='# Rules\n\nKeep this task scoped. Keep this task scoped.\n'
        self.assertTrue(any(k.startswith('md:duplicate') for k in md_rules.lint(text,self.target)))
