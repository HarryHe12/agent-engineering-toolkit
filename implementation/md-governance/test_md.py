"""Requirements-based checks: no stale, duplicate or unreviewed instructions."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import md_rules,md_store,md_gate,md_write
class MarkdownTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); self.target=self.root/'AGENTS.md'
        self.old='# Rules\n\n- Preserve user work before editing any source files.\n'; self.target.write_text(self.old)
        self.new='# Rules\n\n- Preserve user work before editing any source files.\n- Verify the requested behavior before committing the change.\n'
        self.state=self.root/'state'; self.patches=[patch.object(md_store,'STATE',self.state),patch.object(md_gate,'STATE',self.state),patch.object(md_gate,'GLOBAL',self.target)]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in self.patches: p.stop()
        self.temp.cleanup()
    def author_review(self,new=None):
        text=new or self.new
        return {'target':str(self.target.resolve()),'base_sha256':md_rules.digest(self.old),'candidate_sha256':md_rules.digest(text),'basis':'The user explicitly approved local instruction governance.','ownership':'Project-specific instructions belong only in this project entry.','overlap':'Compared existing clauses and updated the unique canonical location.','conflicts':'Checked the existing authorization boundary and retained its meaning.','preservation':'The existing user-work protection rule remains unchanged.','clauses':[{'id':row['id'],'reason':'Adds an observable validation requirement requested by the user.','source':'user:approved-task'} for row in md_rules.added_units(self.old,text)]}
    def review(self,new=None):
        from test_support import token
        draft=self.root/'review.stage'; draft.write_text(new or self.new)
        request=self.root/'request.txt'
        request.write_text('Preserve user work and require verification before committing this project change.')
        return token(self.target,draft,request)
    def test_exact_duplicate_and_punctuation_variant_block(self):
        text=self.old+'- Preserve user work before editing any source files!\n'
        self.assertTrue(any(k.startswith('md:duplicate:') for k in md_rules.lint(text,self.target)))
    def test_duplicate_across_authorities_blocks(self):
        errors=md_rules.lint(self.old,self.target,{str(self.root/'SKILL.md'):self.old+'\n# Extra\n'})
        self.assertTrue(any(k.startswith('md:cross-duplicate:') for k in errors))
    def test_identical_document_copy_is_not_a_second_authority(self):
        errors=md_rules.lint(self.old,self.target,{str(self.root/'other.md'):self.old})
        self.assertTrue(any(k.startswith('md:cross-duplicate:') for k in errors))
    def test_filename_case_cannot_raise_budget(self):
        for name in ['AGENTS.md','agents.md']:
            self.assertIn('md:size',md_rules.lint('x'*3001,self.root/name))
    def test_linked_reference_is_governed(self):
        guide=self.root/'guide.md'; guide.write_text('# Scoped guidance\n')
        self.target.write_text('# Rules\n\nRead [guidance](guide.md).\n')
        self.assertIn(guide.resolve(),{p.resolve() for p in md_gate.discover(self.root)})
    def test_linked_archive_is_not_automatically_loaded(self):
        old=self.root/'archive/old.md'; old.parent.mkdir(); old.write_text('# Historical evidence\n')
        self.target.write_text('# Rules\n\nHistorical [evidence](archive/old.md).\n')
        self.assertNotIn(old.resolve(),{p.resolve() for p in md_gate.discover(self.root)})
    def test_negation_is_not_discarded_by_normalization(self):
        self.assertNotEqual(md_rules.normalize('Allow automatic deployment.'),md_rules.normalize('Do not allow automatic deployment.'))
    def test_budget_cannot_be_evaded_by_one_long_line(self):
        self.assertIn('md:size',md_rules.lint('# Rules\n'+('x'*3001),self.target))
    def test_broken_local_link_blocks(self):
        errors=md_rules.lint('# Rules\n\nRead [rules](missing.md).\n',self.target)
        self.assertIn('md:broken-link:missing.md',errors)
    def test_fenced_examples_are_not_active_duplicates(self):
        text=self.old+'\n```md\n'+self.old+'```\n'
        self.assertFalse(any('duplicate' in k for k in md_rules.lint(text,self.target)))
    def test_repeated_sibling_heading_blocks(self):
        self.assertTrue(md_rules.heading_errors('# Rules\n## Scope\n## Scope\n'))
        self.assertFalse(md_rules.heading_errors('# One\n## Scope\n# Two\n## Scope\n'))
    def test_changed_candidate_or_original_invalidates_review(self):
        for old,new in [(self.old+'changed',self.new),(self.old,self.new+'changed')]:
            with self.assertRaisesRegex(ValueError,'Stale.*review'): md_store.verify_review(self.review(),self.target,old,new)
    def test_each_added_clause_requires_review(self):
        from test_support import verdict,run_review
        import md_context
        draft=self.root/'candidate.stage'; draft.write_text(self.new)
        request=self.root/'request.txt'; request.write_text('Add verification while preserving user work.')
        packet=md_context.build(self.target,draft,request)[2]
        response=verdict(packet); response['clauses']=[]
        result=run_review(self.target,draft,request,response)
        self.assertEqual(result['decision'],'unavailable')
        self.assertIn('every added clause',result['error'])
    def test_generic_review_is_not_accepted(self):
        from md_verdict import validate
        from test_support import verdict
        import md_context
        draft=self.root/'candidate.stage'; draft.write_text(self.new)
        request=self.root/'request.txt'; request.write_text('Add scoped verification.')
        packet=md_context.build(self.target,draft,request)[2]
        response=verdict(packet); response['dimensions']['consistency']['reason']='checked'
        with self.assertRaisesRegex(ValueError,'specific'): validate(response,packet)
    def test_invalid_draft_never_replaces_target(self):
        draft=self.root/'candidate.stage'; text=self.old+self.old; draft.write_text(text)
        with self.assertRaises(ValueError): md_write.apply(self.target,draft,{})
        self.assertEqual(self.target.read_text(),self.old)
    def test_approved_publish_has_hash_bound_receipt(self):
        draft=self.root/'candidate.stage'; draft.write_text(self.new)
        md_write.apply(self.target,draft,self.review())
        self.assertEqual(self.target.read_text(),self.new)
        self.assertTrue(md_store.has_receipt(self.target,self.new))
        self.assertFalse(md_store.has_receipt(self.target,self.new+'modified'))
    def test_unapproved_changed_managed_doc_is_flagged(self):
        md_store.approve(self.target,self.old,self.new,self.review()); self.target.write_text(self.new+'\nUnreviewed additions.\n')
        rows=md_gate.scan(self.root,{})
        self.assertTrue(any('md:managed-review-required' in row['metrics'] for row in rows.values()))
    def test_deleting_managed_authority_is_flagged(self):
        md_store.approve(self.target,self.old,self.new,self.review()); self.target.unlink()
        self.assertTrue(any('md:managed-missing' in row['metrics'] for row in md_gate.scan(self.root,{}).values()))
    def test_similar_rewording_is_shown_for_semantic_review(self):
        source='- 默认使用后台方式打开网页，避免抢占用户当前窗口的焦点。\n'
        candidate='- 默认通过后台方式打开网页，避免抢占用户当前窗口的焦点。\n'
        self.assertTrue(md_rules.similar_clauses(candidate,{'other.md':source},self.target))
if __name__=='__main__': unittest.main()
