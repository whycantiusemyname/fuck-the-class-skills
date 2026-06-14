from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from normalize_obsidian_output import repair_bracket_math_blocks


class BracketMathRepairTests(unittest.TestCase):
    def test_inline_left_right_brackets_are_untouched(self) -> None:
        source = r"$F(x)=\left[\frac{1}{1+x}\right]$"

        self.assertEqual(repair_bracket_math_blocks(source), source)

    def test_bracketed_prose_is_untouched(self) -> None:
        source = "Keep [a_reference_with_underscores] in prose."

        self.assertEqual(repair_bracket_math_blocks(source), source)

    def test_standalone_bracket_math_block_is_repaired(self) -> None:
        source = "Before\n[ \\frac{1}{1+x} ]\nAfter"
        expected = "Before\n$$\n\\frac{1}{1+x}\n$$\nAfter"

        self.assertEqual(repair_bracket_math_blocks(source), expected)


if __name__ == "__main__":
    unittest.main()
