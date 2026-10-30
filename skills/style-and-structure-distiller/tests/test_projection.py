"""Synthetic behavior regressions for prose preservation and draft authority."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from project_markdown import project_bytes, source_blocks, digest
from parsers import parse_document
from manifest import enforce_manifest_governance


class ProjectionTests(unittest.TestCase):
    def fixture(self):
        data = b'## Introduction\n\nThe template is\n\n### Box 1 | Note\n\nUnrelated box prose.\n\nremoved.\n\nA brief complete sentence.\n'
        blocks = source_blocks(data.decode())
        plan = {"source_sha256": digest(data), "exclude": [
            {"start_line": b.first, "end_line": b.last, "span_sha256": digest(b.text.encode()), "reason": "reviewed Box"}
            for b in blocks if b.first in (5, 7)], "joins": [{"start_line": 9, "previous_start_line": 3}]}
        return data, plan

    def test_body_resumes_after_exact_box_and_short_text_survives(self):
        data, plan = self.fixture()
        text, receipt = project_bytes(data, plan)
        self.assertIn('The template is\nremoved.', text)
        self.assertIn('A brief complete sentence.', text)
        self.assertNotIn('Unrelated box', text)
        for row in receipt['ledger']:
            if row['action'] == 'include':
                selected = '\n'.join(text.splitlines()[row['analysis_start_line']-1:row['analysis_end_line']])
                self.assertEqual(digest(selected.encode()), row['source_span_sha256'])

    def test_same_page_table_does_not_swallow_following_body(self):
        data, plan = self.fixture()
        data = data.replace(b'Box 1', b'Table 1')
        plan['source_sha256'] = digest(data)
        b = next(b for b in source_blocks(data.decode()) if b.first == 5)
        plan['exclude'][0]['span_sha256'] = digest(b.text.encode())
        self.assertIn('removed.', project_bytes(data, plan)[0])

    def test_source_or_span_changes_rejected(self):
        data, plan = self.fixture()
        with self.assertRaises(ValueError): project_bytes(data + b'changed', plan)
        plan['exclude'][0]['span_sha256'] = '0' * 64
        with self.assertRaises(ValueError): project_bytes(data, plan)

    def test_duplicate_partial_and_unresolved_spans_rejected(self):
        data, plan = self.fixture()
        duplicate = copy.deepcopy(plan)
        duplicate['exclude'].append(duplicate['exclude'][0])
        with self.assertRaises(ValueError): project_bytes(data, duplicate)
        partial = copy.deepcopy(plan)
        partial['exclude'][0]['end_line'] = 6
        with self.assertRaises(ValueError): project_bytes(data, partial)
        plan['exclude'] = []
        with self.assertRaises(ValueError): project_bytes(data, plan)

    def test_wrong_join_rejected(self):
        data, plan = self.fixture()
        plan['joins'][0]['previous_start_line'] = 1
        with self.assertRaises(ValueError): project_bytes(data, plan)

    def test_cross_page_continuation_keeps_page_and_span_identity(self):
        data = b'First half of\n\n<!-- PDF PAGE 2 / 3 -->\n\na sentence.\n'
        plan = {'source_sha256': digest(data), 'exclude': [],
                'joins': [{'start_line': 5, 'previous_start_line': 1}]}
        text, receipt = project_bytes(data, plan)
        self.assertEqual(text, 'First half of\na sentence.\n')
        self.assertEqual(receipt['ledger'][-1]['pdf_page'], 2)
        self.assertEqual(receipt['ledger'][-1]['analysis_start_line'], 2)

    def test_exact_literal_removal_preserves_prose_and_original_provenance(self):
        data = ('Body text before\nRunning page header\n\ncontinues here.\n\n'
                'Another clause, Author manuscript; available in PMC.\n\nresumes.\n').encode()
        blocks = source_blocks(data.decode())
        literals = {1: '\nRunning page header', 6: ' Author manuscript; available in PMC.'}
        plan = {'source_sha256': digest(data), 'exclude': [], 'remove_literals': [
            {'start_line': b.first, 'end_line': b.last,
             'source_span_sha256': digest(b.text.encode()), 'literal': literals[b.first],
             'literal_sha256': digest(literals[b.first].encode()), 'reason': 'running header'}
            for b in blocks if b.first in literals],
            'joins': [{'start_line': 4, 'previous_start_line': 1},
                      {'start_line': 8, 'previous_start_line': 6}]}
        output, receipt = project_bytes(data, plan)
        self.assertEqual(output, 'Body text before\ncontinues here.\n\nAnother clause,\nresumes.\n')
        changed = [r for r in receipt['ledger'] if r.get('removed_literals')]
        self.assertEqual(len(changed), 2)
        self.assertTrue(all(r['source_span_sha256'] != r['projected_span_sha256'] for r in changed))
        self.assertEqual(changed[0]['removed_literals'][0]['literal_sha256'],
                         digest(literals[1].encode()))

    def test_literal_removal_rejects_unbound_or_overbroad_edit(self):
        data = b'Body text\nRunning page header\n'
        block = source_blocks(data.decode())[0]
        item = {'start_line': block.first, 'end_line': block.last,
                'source_span_sha256': digest(block.text.encode()),
                'literal': '\nRunning page header',
                'literal_sha256': digest(b'\nRunning page header'), 'reason': 'header'}
        plan = {'source_sha256': digest(data), 'remove_literals': [item]}
        self.assertEqual(project_bytes(data, plan)[0], 'Body text\n')
        for field, value in [('source_span_sha256', '0' * 64),
                             ('literal_sha256', '0' * 64), ('literal', block.text)]:
            wrong = copy.deepcopy(plan)
            wrong['remove_literals'][0][field] = value
            with self.assertRaises(ValueError): project_bytes(data, wrong)
        wrong = copy.deepcopy(plan)
        wrong['remove_literals'].append(copy.deepcopy(item))
        with self.assertRaises(ValueError): project_bytes(data, wrong)

    def test_hash_bound_paragraph_move_restores_reading_order(self):
        data = b'## First section\n\ncontinuation.\n\n## Second section\n\nFirst half\n'
        blocks = {b.first: b for b in source_blocks(data.decode())}
        move = {'start_line': 3, 'end_line': 3,
                'source_span_sha256': digest(blocks[3].text.encode()),
                'after_start_line': 7, 'after_span_sha256': digest(blocks[7].text.encode()),
                'reason': 'verified reading order'}
        plan = {'source_sha256': digest(data), 'move_after': [move],
                'joins': [{'start_line': 3, 'previous_start_line': 7}]}
        output, receipt = project_bytes(data, plan)
        self.assertEqual(output, '## First section\n\n## Second section\n\nFirst half\ncontinuation.\n')
        row = next(x for x in receipt['ledger'] if x['source_start_line'] == 3)
        self.assertEqual(row['moved_after_source_start_line'], 7)
        self.assertEqual(receipt['moves_applied'], 1)
        bad = copy.deepcopy(plan)
        bad['move_after'][0]['after_span_sha256'] = '0' * 64
        with self.assertRaises(ValueError): project_bytes(data, bad)

    def test_nested_review_summary_retains_raw_heading_and_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'paper.md'
            path.write_text('# Paper\n\nAuthor metadata under title.\n\n## Summary\n\nOpening abstract prose.\n\n## Delivery\n\nBody prose here.\n\n### Summary\n\nLocal synthesis retained.\n', encoding='utf-8')
            doc = parse_document(path, 'review-synthetic', 'review_article')
            summaries = [s for s in doc.sections if s.source_heading == 'Summary']
            self.assertEqual([s.canonical_section for s in summaries], ['abstract', 'review_body'])
            self.assertEqual(summaries[1].paragraphs[0].text, 'Local synthesis retained.')
            article = parse_document(path, 'article-synthetic', 'original_article')
            self.assertEqual([s.canonical_section for s in article.sections if s.source_heading == 'Summary'], ['abstract', 'abstract'])

    def test_draft_cli_is_explicit_and_does_not_promote_manifest(self):
        fixture = ROOT / 'tests/fixtures/approved-review-manifest.json'
        m = json.loads(fixture.read_text(encoding='utf-8'))
        for d in m['documents']:
            d['source_file'] = str((fixture.parent / d['source_file']).resolve())
        m['status'] = 'author_review_required'
        with self.assertRaises(RuntimeError): enforce_manifest_governance(m)
        self.assertTrue(enforce_manifest_governance(m, draft=True)[0])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'manifest.json'
            p.write_text(json.dumps(m), encoding='utf-8')
            out = Path(tmp) / 'out'
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/distill_corpus.py'), 'run', '--draft', '--manifest', str(p), '--out-dir', str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((out/'style-profile.json').read_text())
            self.assertEqual(profile['status'], 'author_review_required')
            self.assertIn('draft_corpus_not_approved', [x['code'] for x in profile['warnings']])
            self.assertEqual(json.loads(p.read_text())['status'], 'author_review_required')
            for f in out.rglob('*.json'):
                payload = json.loads(f.read_text(encoding='utf-8'))
                self.assertIn('draft_corpus_not_approved', [x['code'] for x in payload['warnings']], str(f))


if __name__ == '__main__':
    unittest.main()
