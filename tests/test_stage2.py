# -*- coding: utf-8 -*-
"""Tests for stage 2: structure_headers + inject_code."""
import sys, asyncio, json
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, r"D:\Desktop\longtext2md")

from src.pipeline.stage2_structure import (
    _mark_paragraphs,
    _insert_headers,
    structure_headers,
    inject_code,
)

SECT = chr(0xA7)


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
        # Short paragraphs should merge with the previous one
        text = "A long enough paragraph with sufficient text to exceed the minimum character count threshold for merging logic.\n\nshort\n\nAnother long paragraph that should also be comfortably above the minimum threshold.\n\nshort2"
        marked, count = _mark_paragraphs(text)
        # short paragraphs should be merged into neighbors
        assert count <= 3

    def test_empty_input(self):
        marked, count = _mark_paragraphs("")
        assert count == 0


class TestInsertHeaders:
    def test_insert_single_header(self):
        marked = f"[{SECT}1]\nParagraph one here.\n\n[{SECT}2]\nParagraph two here."
        headers = [{"marker": f"{SECT}1", "level": 2, "text": "Title One"}]
        result = _insert_headers(marked, headers)
        assert "## Title One" in result
        assert "Paragraph one here" in result
        assert "Paragraph two here" in result
        # Markers should be removed
        assert f"[{SECT}1]" not in result
        assert f"[{SECT}2]" not in result
        # No character-level splitting
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
        # Should return original text on JSON parse failure
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
        # No part should be a single character
        for p in parts:
            if p.strip() and not p.strip().startswith("#"):
                assert len(p.strip()) >= 3, f"Short part found: {repr(p)}"


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