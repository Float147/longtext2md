# -*- coding: utf-8 -*-
"""Tests for stage 2: structure_headers + inject_assets."""
import sys, asyncio, json
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, r"D:\Desktop\longtext2md")

from src.pipeline.stage2_structure import (
    _mark_paragraphs,
    _insert_headers,
    _split_by_headers,
    _format_slices_for_prompt,
    _verify_headers_preserved,
    structure_headers,
    inject_code,
    inject_assets,
)

SECT = chr(0xA7)


# ============================================================
# _split_by_headers
# ============================================================


class TestSplitByHeaders:
    def test_simple_two_h2s(self):
        text = "Preamble text.\n\n## Section One\nContent of section one.\n\n## Section Two\nContent of section two."
        sections = _split_by_headers(text)
        assert len(sections) == 3  # preamble + 2 sections
        assert sections[0] == "Preamble text."
        assert sections[1].startswith("## Section One")
        assert sections[2].startswith("## Section Two")

    def test_no_headers_returns_single_section(self):
        text = "Just plain text without headers."
        sections = _split_by_headers(text)
        assert len(sections) == 1
        assert sections[0] == text

    def test_empty_input(self):
        sections = _split_by_headers("")
        assert len(sections) == 0

    def test_whitespace_only(self):
        sections = _split_by_headers("   \n\n  ")
        assert len(sections) == 0

    def test_h3_not_split_by_h2(self):
        """### 不应该被 ## 切分逻辑拆分"""
        text = "## Main Title\nSome content.\n\n### Sub Title\nSub content."
        sections = _split_by_headers(text)
        # Should be 1 section: it starts with ## and contains ### inside
        assert len(sections) == 1
        assert "### Sub Title" in sections[0]

    def test_h4_not_split_by_h2(self):
        """#### 不应该被 ## 切分逻辑拆分"""
        text = "## Main Title\nSome content.\n\n#### Deep Title\nDeep content."
        sections = _split_by_headers(text)
        assert len(sections) == 1
        assert "#### Deep Title" in sections[0]

    def test_large_section_splits_on_h3(self):
        """超大节会按 ### 再切"""
        big_content = "A" * 9000
        text = f"## Huge Section\n{big_content}\n\n### Sub A\nMore content.\n\n### Sub B\nEven more content."
        sections = _split_by_headers(text)
        # Should split into 2+ subsections since > 8000 chars
        assert len(sections) >= 2

    def test_multiple_h2s(self):
        text = "## A\nA content.\n\n## B\nB content.\n\n## C\nC content."
        sections = _split_by_headers(text)
        assert len(sections) == 3


# ============================================================
# _format_slices_for_prompt
# ============================================================


class TestFormatSlices:
    def test_empty_slices(self):
        result = _format_slices_for_prompt([])
        assert result == "（无参考资料）"

    def test_code_slice(self):
        slices = [
            ({"file": "UserController.java", "type": "code"},
             "@RestController\npublic class UserController {}")
        ]
        result = _format_slices_for_prompt(slices)
        assert "[代码]" in result
        assert "UserController.java" in result
        assert "```java" in result
        assert "@RestController" in result

    def test_courseware_slice(self):
        slices = [
            ({"file": "notes.md", "type": "courseware", "title": "Spring Notes"},
             "Some courseware content.")
        ]
        result = _format_slices_for_prompt(slices)
        assert "[课件]" in result
        assert "Spring Notes" in result
        assert "> Some courseware content." in result

    def test_mixed_slices(self):
        slices = [
            ({"file": "App.java", "type": "code"}, "public class App {}"),
            ({"file": "slides.md", "type": "courseware", "title": "Lecture 3"}, "Slide content."),
        ]
        result = _format_slices_for_prompt(slices)
        assert "[代码]" in result
        assert "[课件]" in result


# ============================================================
# inject_assets
# ============================================================


class TestInjectAssets:
    def test_no_rag_collection_returns_unchanged(self):
        text = "Some structured markdown."

        async def run():
            return await inject_assets(text, rag_collection=None)

        result = asyncio.run(run())
        assert result == text

    def test_empty_rag_collection_returns_unchanged(self):
        text = "Content here."
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        async def run():
            return await inject_assets(text, rag_collection=mock_collection)

        result = asyncio.run(run())
        assert result == text

    def test_empty_text(self):
        async def run():
            return await inject_assets("", rag_collection=MagicMock())

        result = asyncio.run(run())
        assert result == ""

    def test_with_valid_collection_calls_llm(self):
        text = "## Section A\nSome content about controllers.\n\n## Section B\nSome content about services."
        mock_collection = MagicMock()
        mock_collection.count.return_value = 5

        # Mock RAG retrieval to return slices
        mock_slice = ({"file": "Test.java", "type": "code"}, "public class Test {}")

        async def run():
            with patch(
                "src.rag.retriever.retrieve_slices_for_injection",
                return_value=[mock_slice]
            ):
                with patch(
                    "src.pipeline.stage2_structure.chat",
                    new=AsyncMock(side_effect=lambda **kwargs: kwargs["user_message"])
                ):
                    return await inject_assets(text, rag_collection=mock_collection)

        result = asyncio.run(run())
        # Should have processed both sections
        assert "Section A" in result
        assert "Section B" in result

    def test_parallel_processing(self):
        """Verify sections are processed (concurrent via asyncio.gather)."""
        text = "## S1\nContent 1.\n\n## S2\nContent 2.\n\n## S3\nContent 3."
        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        mock_slice = ({"file": "App.java", "type": "code"}, "class App {}")

        call_count = [0]

        async def mock_chat(**kwargs):
            call_count[0] += 1
            return "processed"

        async def run():
            with patch("src.rag.retriever.retrieve_slices_for_injection", return_value=[mock_slice]):
                with patch("src.pipeline.stage2_structure.chat", new=AsyncMock(side_effect=mock_chat)):
                    return await inject_assets(text, rag_collection=mock_collection)

        result = asyncio.run(run())
        # 3 sections should each trigger a chat call
        assert call_count[0] == 3


# ============================================================
# inject_code (compatibility)
# ============================================================


class TestInjectCode:
    def test_no_rag_collection_returns_unchanged(self):
        text = "Some structured markdown."

        async def run():
            return await inject_code(text, rag_collection=None)

        result = asyncio.run(run())
        assert result == text

    def test_empty_rag_collection_returns_unchanged(self):
        text = "Content here."
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        async def run():
            return await inject_code(text, rag_collection=mock_collection)

        result = asyncio.run(run())
        assert result == text


# ============================================================
# _verify_headers_preserved
# ============================================================


class TestVerifyHeadersPreserved:
    def test_identical_headers_pass(self):
        original = chr(35)*2 + " A\nContent.\n\n" + chr(35)*2 + " B\nMore."
        merged = chr(35)*2 + " A\nContent with code.\n\n" + chr(35)*2 + " B\nMore."
        assert _verify_headers_preserved(original, merged) is True

    def test_missing_header_fails(self):
        original = chr(35)*2 + " A\nContent.\n\n" + chr(35)*2 + " B\nMore."
        merged = chr(35)*2 + " A\nContent."
        assert _verify_headers_preserved(original, merged) is False

    def test_extra_header_passes(self):
        """LLM may add headers (shouldn't but verification is lenient)."""
        original = chr(35)*2 + " A\nContent."
        merged = chr(35)*2 + " A\nContent.\n\n" + chr(35)*2 + " Extra\nExtra."
        assert _verify_headers_preserved(original, merged) is True

    def test_reordered_headers_fails(self):
        original = chr(35)*2 + " A\nA.\n\n" + chr(35)*2 + " B\nB."
        merged = chr(35)*2 + " B\nB.\n\n" + chr(35)*2 + " A\nA."
        assert _verify_headers_preserved(original, merged) is False

    def test_h3_and_h4_preserved(self):
        original = chr(35)*2 + " H2\nContent.\n\n" + chr(35)*3 + " H3\nSub.\n\n" + chr(35)*4 + " H4\nDeep."
        merged = chr(35)*2 + " H2\nContent modified.\n\n" + chr(35)*3 + " Extra H3\nExtra.\n\n" + chr(35)*3 + " H3\nSub.\n\n" + chr(35)*4 + " H4\nDeep."
        assert _verify_headers_preserved(original, merged) is True


# ============================================================
# _mark_paragraphs (existing)
# ============================================================


class TestMarkParagraphs:
    def test_simple_two_paras(self):
        text = "L"*120 + " para one." + chr(10) + chr(10) + "L"*120 + " para two."
        marked, count = _mark_paragraphs(text)
        assert count == 2
        assert f"[{SECT}1]" in marked
        assert f"[{SECT}2]" in marked
        assert "para one" in marked
        assert "para two" in marked

    def test_single_para(self):
        text = "just one paragraph."
        marked, count = _mark_paragraphs(text)
        assert count == 1
        assert f"[{SECT}1]" in marked

    def test_short_paragraphs_merge(self):
        text = "A long enough paragraph with sufficient text to exceed the minimum character count threshold for merging logic.\n\nshort\n\nAnother long paragraph that should also be comfortably above the minimum threshold.\n\nshort2"
        marked, count = _mark_paragraphs(text)
        assert count <= 3

    def test_empty_input(self):
        marked, count = _mark_paragraphs("")
        assert count == 0


# ============================================================
# _insert_headers (existing)
# ============================================================


class TestInsertHeaders:
    def test_insert_single_header(self):
        marked = f"[{SECT}1]\nParagraph one here.\n\n[{SECT}2]\nParagraph two here."
        headers = [{"marker": f"{SECT}1", "level": 2, "text": "Title One"}]
        result = _insert_headers(marked, headers)
        assert "## Title One" in result
        assert "Paragraph one here" in result
        assert "Paragraph two here" in result
        assert f"[{SECT}1]" not in result
        assert f"[{SECT}2]" not in result
        parts = result.split("\n\n")
        assert all(len(p) >= 3 for p in parts if p.strip())

    def test_insert_empty_headers(self):
        marked = f"[{SECT}1]\nParagraph one.\n\n[{SECT}2]\nParagraph two."
        result = _insert_headers(marked, [])
        assert "Paragraph one" in result
        assert "Paragraph two" in result

    def test_insert_headers_reverse_order(self):
        marked = f"[{SECT}1]\nFirst.\n\n[{SECT}2]\nSecond.\n\n[{SECT}3]\nThird."
        headers = [
            {"marker": f"{SECT}3", "level": 3, "text": "Third Title"},
            {"marker": f"{SECT}1", "level": 2, "text": "First Title"},
        ]
        result = _insert_headers(marked, headers)
        assert "## First Title" in result
        assert "### Third Title" in result


# ============================================================
# structure_headers (existing)
# ============================================================


class TestStructureHeaders:
    def test_valid_json_response(self):
        text = "Chapter one content here.\n\nChapter two content here longer."
        mock_json = json.dumps({
            "headers": [
                {"marker": f"{SECT}1", "level": 2, "text": "Chapter 1"},
            ]
        })

        async def run():
            with patch("src.pipeline.stage2_structure.chat", new=AsyncMock(return_value=mock_json)):
                return await structure_headers(text)

        result = asyncio.run(run())
        assert "## Chapter 1" in result
        assert "Chapter one content" in result

    def test_invalid_json_fallback(self):
        text = "Original content unchanged."

        async def run():
            with patch("src.pipeline.stage2_structure.chat", new=AsyncMock(return_value="not json at all")):
                return await structure_headers(text)

        result = asyncio.run(run())
        assert "Original content unchanged" in result

    def test_empty_headers_fallback(self):
        text = "Original content."

        async def run():
            with patch("src.pipeline.stage2_structure.chat", new=AsyncMock(return_value='{"headers": []}')):
                return await structure_headers(text)

        result = asyncio.run(run())
        assert "Original content" in result

    def test_no_character_splitting(self):
        """Regression test: verify no character-level splitting."""
        text = "Hello world this is a test paragraph.\n\nSecond paragraph here."
        mock_json = json.dumps({
            "headers": [{"marker": f"{SECT}1", "level": 2, "text": "Title"}]
        })

        async def run():
            with patch("src.pipeline.stage2_structure.chat", new=AsyncMock(return_value=mock_json)):
                return await structure_headers(text)

        result = asyncio.run(run())
        parts = result.split("\n\n")
        for p in parts:
            if p.strip() and not p.strip().startswith("#"):
                assert len(p.strip()) >= 3, f"Short part found: {repr(p)}"
