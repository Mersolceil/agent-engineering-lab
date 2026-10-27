"""Offline commands must not overwrite the recorded experiment snapshots."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent


class OutputIsolationTests(unittest.TestCase):
    def test_commands_keep_historical_results_untouched(self):
        commands = {
            'evaluate.py': ['runs.json', 'summary.json'],
            'ablations.py': ['ablations.json'],
            'planning.py': ['planning.json'],
            'compare.py': ['comparison.json'],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / 'results'
            old.mkdir()
            for files in commands.values():
                for name in files:
                    (old / name).write_text('historical snapshot', encoding='utf-8')
            for command, files in commands.items():
                subprocess.run([sys.executable, str(HERE / command)], cwd=root,
                               check=True, capture_output=True, text=True)
                for name in files:
                    self.assertEqual((old / name).read_text(encoding='utf-8'),
                                     'historical snapshot')
                    with (old / 'generated' / name).open(encoding='utf-8') as stream:
                        self.assertTrue(json.load(stream))


if __name__ == '__main__':
    unittest.main()
