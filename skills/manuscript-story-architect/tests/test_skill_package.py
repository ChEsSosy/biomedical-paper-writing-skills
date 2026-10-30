"""Dependency-free package-integrity tests for the review candidate."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


class SkillPackageTests(unittest.TestCase):
    def test_frontmatter_name_and_description_are_present(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name: manuscript-story-architect$")
        self.assertRegex(frontmatter, r"(?m)^description: .+$")

    def test_all_local_skill_links_resolve(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        targets = re.findall(r"\]\((?!https?://)([^)#]+)(?:#[^)]+)?\)", text)
        self.assertGreater(len(targets), 0)
        missing = [target for target in targets if not (ROOT / target).is_file()]
        self.assertEqual([], missing)

    def test_ui_metadata_and_default_prompt_are_consistent(self) -> None:
        text = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        match = re.search(r'(?m)^  short_description: "([^"]+)"$', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(len(match.group(1)), 25)
        self.assertLessEqual(len(match.group(1)), 64)
        self.assertIn("$manuscript-story-architect", text)

    def test_no_unfinished_scaffold_placeholders(self) -> None:
        files = [SKILL, ROOT / "agents" / "openai.yaml", *ROOT.joinpath("references").rglob("*.md")]
        markers = {"TODO", "TBD", "PLACEHOLDER", "Replace this text"}
        findings = []
        for path in files:
            content = path.read_text(encoding="utf-8")
            for marker in markers:
                if marker in content:
                    findings.append(f"{path.name}:{marker}")
        self.assertEqual([], findings)


if __name__ == "__main__":
    unittest.main()
