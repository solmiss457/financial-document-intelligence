"""Integration regression against hash-pinned public PDFs; includes known failures."""
import contextlib
import io
import json
import unittest
from pathlib import Path
from scripts.probe_pdf import run, ROOT


class PdfProbeRegression(unittest.TestCase):
    def test_observed_successes_and_failures(self):
        with contextlib.redirect_stdout(io.StringIO()):
            run()
        actual = json.loads((ROOT / 'work/pdf-probe/summary.json').read_text())
        expected = json.loads((ROOT / 'eval/configs/pdf_probe_expected.json').read_text())
        self.assertEqual(actual['pymupdf'], '1.26.7')
        self.assertEqual(actual['results'], expected)


if __name__ == '__main__':
    unittest.main()
