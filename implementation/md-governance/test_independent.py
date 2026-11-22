"""Fail closed on stale, forged, incomplete or negative independent reviews."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import md_context
import md_semantic
import md_seal
import md_store
import md_verdict
import md_write
import test_md
from test_support import verdict,run_review


class IndependentTests(unittest.TestCase):
    def setUp(self):
        test_md.MarkdownTests.setUp(self)
        import md_gate
        extra=patch.object(md_gate,'GLOBAL',self.root/'global/AGENTS.md')
        extra.start(); self.patches.append(extra)
    tearDown=test_md.MarkdownTests.tearDown
    review=test_md.MarkdownTests.review

    def inputs(self):
        draft=self.root/'candidate.stage'; draft.write_text(self.new)
        request=self.root/'request.txt'; request.write_text('Require scoped verification and preserve user work.')
        return draft,request,md_context.build(self.target,draft,request)[2]

    def test_one_bad_dimension_prevents_publication_and_gives_advice(self):
        draft,request,packet=self.inputs()
        response=verdict(packet)
        response['dimensions']['scope'].update(status='revise',suggestion='Restrict this requirement to changes that affect source behavior.')
        response['decision']='revise'
        feedback=run_review(self.target,draft,request,response)
        self.assertEqual(feedback['decision'],'revise')
        self.assertIn('Restrict',feedback['verdict']['dimensions']['scope']['suggestion'])
        credential=json.loads(Path(feedback['review']).read_text())
        with self.assertRaisesRegex(ValueError,'requires revision'): md_write.apply(self.target,draft,credential)
        self.assertEqual(self.target.read_text(),self.old)

    def test_context_change_requires_new_review(self):
        authority=self.root/'spec.md'; authority.write_text('# Contract\n\nManagers may operate assigned stores.\n')
        credential=self.review()
        authority.write_text('# Contract\n\nNobody may operate stores.\n')
        draft=self.root/'review.stage'
        with self.assertRaisesRegex(ValueError,'context'): md_write.apply(self.target,draft,credential)
        self.assertEqual(self.target.read_text(),self.old)

    def test_source_change_requires_new_review(self):
        credential=self.review()
        (self.root/'request.txt').write_text('Different source, without authorization for verification.')
        with self.assertRaisesRegex(ValueError,'context'): md_write.apply(self.target,self.root/'review.stage',credential)

    def test_deleted_context_is_not_silently_ignored(self):
        authority=self.root/'spec.md'; authority.write_text('# Contract\n\nOnly assigned stores are accessible.\n')
        credential=self.review(); authority.unlink()
        with self.assertRaisesRegex(ValueError,'context'): md_write.apply(self.target,self.root/'review.stage',credential)

    def test_forged_token_and_modified_attestation_are_rejected(self):
        draft,request,packet=self.inputs()
        with self.assertRaisesRegex(ValueError,'Missing'): md_write.apply(self.target,draft,{'independent_review':'a'*32})
        credential=self.review()
        path=md_seal.run_directory(credential['independent_review'])/'attestation.json'
        envelope=json.loads(path.read_text()); envelope['payload']['verdict']['decision']='revise'
        path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(ValueError,'Invalid independent'): md_write.apply(self.target,self.root/'review.stage',credential)

    def test_missing_reviewer_preserves_authority(self):
        draft,request,packet=self.inputs()
        with patch('md_backend.invoke',side_effect=RuntimeError('reviewer offline')):
            feedback=md_semantic.run(self.target,draft,request)
        self.assertEqual(feedback['decision'],'unavailable')
        self.assertEqual(self.target.read_text(),self.old)

    def test_false_evidence_and_missing_criteria_fail_closed(self):
        _,_,packet=self.inputs()
        response=verdict(packet); response['dimensions']['basis']['evidence'][0]['quote']='not in input'
        with self.assertRaisesRegex(ValueError,'nonexistent'): md_verdict.validate(response,packet)
        response=verdict(packet); response['dimensions'].pop('value')
        with self.assertRaisesRegex(ValueError,'every quality'): md_verdict.validate(response,packet)

    def test_unchanged_dirty_file_cannot_mint_new_review(self):
        self.target.write_text(self.new)
        draft,request,_=self.inputs()
        with self.assertRaisesRegex(ValueError,'No candidate change'): md_semantic.run(self.target,draft,request)

    def test_changed_inputs_during_review_invalidate_result(self):
        draft,request,packet=self.inputs()
        def backend(data,path):
            request.write_text('changed request while reviewer was running')
            return verdict(data),{}
        with patch('md_backend.invoke',side_effect=backend):
            result=md_semantic.run(self.target,draft,request)
        self.assertEqual(result['decision'],'unavailable')
        self.assertEqual(self.target.read_text(),self.old)

    def test_old_unsigned_receipt_not_accepted_without_migration_catalog(self):
        path=md_store.receipt_path(self.target,self.old); path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'target':str(self.target.resolve()),'candidate_sha256':md_store.digest(self.old)}))
        self.assertFalse(md_store.has_receipt(self.target,self.old))

    def test_rejected_candidate_can_be_revised_and_approved(self):
        draft,request,packet=self.inputs()
        rejected=run_review(self.target,draft,request,verdict(packet,'revise'))
        self.assertEqual(rejected['decision'],'revise')
        draft.write_text(self.new.replace('committing','locally committing'))
        accepted=run_review(self.target,draft,request)
        self.assertEqual(accepted['decision'],'pass')
        md_write.apply(self.target,draft,json.loads(Path(accepted['review']).read_text()))
        self.assertEqual(self.target.read_text(),draft.read_text())

    def test_sentence_negation_and_fenced_examples_preserved(self):
        import md_rules
        text='# Scope\n\nAllow explicit user deployment. Do not allow automatic deployment.\n'
        self.assertFalse(md_rules.sentence_duplicates(text))
        self.assertFalse(md_rules.sentence_duplicates('```md\nKeep this task scoped. Keep this task scoped.\n```'))
        self.assertTrue(md_rules.sentence_duplicates('# Rules\n\n修改代码前先保护用户工作。修改代码前先保护用户工作。\n'))

    def test_newly_referenced_guide_is_version_bound(self):
        guide=self.root/'guide.md'; guide.write_text('# Guide\n\nUse scoped checks before committing.\n')
        draft,request,_=self.inputs()
        draft.write_text(self.new+'\nRead [verification guide](guide.md) when choosing checks.\n')
        response=run_review(self.target,draft,request)
        self.assertEqual(response['decision'],'pass')
        guide.write_text('# Guide\n\nNever perform verification.\n')
        with self.assertRaisesRegex(ValueError,'context'):
            md_write.apply(self.target,draft,json.loads(Path(response['review']).read_text()))

    def test_signed_json_without_reviewer_provenance_is_not_receipt(self):
        path=md_store.receipt_path(self.target,self.old)
        md_store.atomic_text(path,json.dumps(md_seal.signed({'target':str(self.target.resolve()),'candidate_sha256':md_store.digest(self.old)})))
        self.assertFalse(md_store.has_receipt(self.target,self.old))

    def test_legacy_snapshot_cannot_adopt_later_self_signed_receipts(self):
        import md_migrate
        path=md_store.receipt_path(self.target,self.old); path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'target':str(self.target.resolve()),'candidate_sha256':md_store.digest(self.old)}))
        md_migrate.snapshot()
        self.assertTrue(md_store.has_receipt(self.target,self.old))
        newer=md_store.receipt_path(self.target,self.new)
        newer.write_text(json.dumps({'target':str(self.target.resolve()),'candidate_sha256':md_store.digest(self.new)}))
        md_migrate.snapshot()
        self.assertFalse(md_store.has_receipt(self.target,self.new))
        path.write_text(path.read_text()+' ')
        self.assertFalse(md_store.has_receipt(self.target,self.old))

    def test_quality_checker_change_invalidates_pending_review(self):
        credential=self.review()
        with patch('md_semantic.quality_versions',return_value={'changed':'new'}):
            with self.assertRaisesRegex(ValueError,'quality checker'):
                md_write.apply(self.target,self.root/'review.stage',credential)

    def test_checker_change_during_review_cannot_be_certified(self):
        draft,request,packet=self.inputs()
        with patch('md_semantic.quality_versions',side_effect=[{'old':'a'},{'new':'b'}]):
            result=run_review(self.target,draft,request)
        self.assertEqual(result['decision'],'unavailable')
        self.assertIn('changed during review',result['error'])

    def test_criteria_change_during_review_cannot_be_certified(self):
        draft,request,packet=self.inputs()
        policy=self.root/'policy.json';policy.write_text(md_semantic.POLICY.read_text())
        def backend(data,path):
            policy.write_text(policy.read_text()+' ')
            return verdict(data),{}
        with patch('md_semantic.POLICY',policy),patch('md_backend.invoke',side_effect=backend):
            result=md_semantic.run(self.target,draft,request)
        self.assertEqual(result['decision'],'unavailable')
        self.assertEqual(self.target.read_text(),self.old)

    def test_dirty_authority_cannot_hide_removed_approved_requirements(self):
        credential=self.review()
        md_write.apply(self.target,self.root/'review.stage',credential)
        dirty='# Rules\n\nNever verify source changes.\n'
        self.target.write_text(dirty)
        draft,request,_=self.root/'next.stage',self.root/'request.txt',None
        draft.write_text(dirty+'\nPreserve user work.\n')
        with self.assertRaisesRegex(ValueError,'approved version'):
            md_semantic.run(self.target,draft,request)
        self.assertEqual(self.target.read_text(),dirty)

    def test_fixture_transport_cannot_mint_real_installation_approval(self):
        draft,request,_=self.inputs()
        with patch.object(md_store,'STATE',md_store.BASE/'state'):
            with self.assertRaisesRegex(RuntimeError,'refuses installed state'):
                run_review(self.target,draft,request)
