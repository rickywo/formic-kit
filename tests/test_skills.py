#!/usr/bin/env python3
"""Tests for the frontmatter of skills/*/SKILL.md. Run: python3 tests/test_skills.py"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
AUTOINVOKE = "  opencode/autoinvoke: false"
DISABLE = "disable-model-invocation: true"
COORDINATOR_LOADED = {"formic-board", "formic-dispatch"}
VISIBLE = {"formic-coordinate", "formic-task-craft", "formic-task-review", "formic-board-hygiene"}


def frontmatter_lines(path):
    """Return the lines between the first two '---' lines of a SKILL.md file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{path} does not start with ---"
    for i in range(1, len(lines)):
        if lines[i] == "---":
            return lines[1:i]
    raise AssertionError(f"{path} has no closing ---")


def load_skills():
    """Return {folder name: frontmatter lines} for every skills/*/SKILL.md."""
    return {p.parent.name: frontmatter_lines(p) for p in sorted(SKILLS.glob("*/SKILL.md"))}


class SkillFrontmatterTests(unittest.TestCase):
    def test_skills_found(self):
        self.assertTrue(load_skills())

    def test_step_and_role_skills_have_both_keys(self):
        # In Claude Code a worker loads these through /<skill-id> in its brief, so they
        # are hidden from model invocation in both tools.
        for name, lines in load_skills().items():
            if name in VISIBLE or name in COORDINATOR_LOADED:
                continue
            with self.subTest(skill=name):
                self.assertIn(AUTOINVOKE, lines, f"{name}: opencode/autoinvoke: false is missing")
                self.assertIn(DISABLE, lines, f"{name}: disable-model-invocation: true is missing")

    def test_coordinator_loaded_skills_have_only_the_opencode_key(self):
        # The coordinator loads these on its own initiative; its user never types /formic-board,
        # so Claude Code must be able to load them with the Skill tool.
        skills = load_skills()
        for name in sorted(COORDINATOR_LOADED):
            with self.subTest(skill=name):
                self.assertIn(name, skills, f"{name} is missing")
                self.assertIn(AUTOINVOKE, skills[name], f"{name}: opencode/autoinvoke: false is missing")
                self.assertNotIn(DISABLE, skills[name], f"{name} must stay loadable by the Skill tool")

    def test_visible_skills_have_neither_key(self):
        skills = load_skills()
        for name in sorted(VISIBLE):
            with self.subTest(skill=name):
                self.assertIn(name, skills, f"{name} is missing")
                for line in skills[name]:
                    self.assertNotIn("autoinvoke", line, f"{name} must not hide itself")
                    self.assertNotIn("disable-model-invocation", line, f"{name} must stay visible")

    def test_name_and_description(self):
        for name, lines in load_skills().items():
            with self.subTest(skill=name):
                self.assertIn(f"name: {name}", lines, f"{name}: name must equal the folder name")
                descriptions = [line for line in lines if line.startswith("description:")]
                self.assertTrue(descriptions, f"{name}: description line missing")
                self.assertTrue(descriptions[0][len("description:"):].strip(), f"{name}: description is empty")


if __name__ == "__main__":
    unittest.main()
