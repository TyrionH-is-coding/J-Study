"""Quick validation of parse_outline_sections for sectional generation."""

import sys
import unittest

sys.path.insert(0, ".")
from packages.core.jstudy_core.pipeline import parse_outline_sections


class TestParseOutlineSections(unittest.TestCase):
    def test_markdown_headings(self):
        sections = parse_outline_sections(
            "# Chapter 1\n## Section 1.1\n## Section 1.2\n# Chapter 2\n## Section 2.1"
        )
        titles = [s["title"] for s in sections]
        levels = [s["level"] for s in sections]
        self.assertEqual(titles, ["Chapter 1", "Section 1.1", "Section 1.2", "Chapter 2", "Section 2.1"])
        self.assertEqual(levels, [1, 2, 2, 1, 2])

    def test_numbered_lines(self):
        sections = parse_outline_sections("1. 抗原\n2. 抗体\n3. 补体")
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0]["title"], "1. 抗原")

    def test_chinese_numbered(self):
        sections = parse_outline_sections("一、抗原\n二、抗体\n三、补体系统")
        self.assertEqual(len(sections), 3)

    def test_empty_returns_empty(self):
        self.assertEqual(parse_outline_sections(""), [])
        self.assertEqual(parse_outline_sections("   \n\n  "), [])

    def test_single_heading_returns_one(self):
        sections = parse_outline_sections("# Just One Chapter")
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["title"], "Just One Chapter")

    def test_mixed_format(self):
        sections = parse_outline_sections(
            "# 绪论\n## 1.1 研究背景\n## 1.2 研究意义\n# 第二章 理论基础"
        )
        self.assertEqual(len(sections), 4)
        self.assertEqual(sections[0]["title"], "绪论")

    def test_noise_lines_ignored(self):
        sections = parse_outline_sections(
            "这是一段简介文本\n\n# 第一章\n\n一些内容\n\n## 第一节"
        )
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "第一章")


if __name__ == "__main__":
    unittest.main()
