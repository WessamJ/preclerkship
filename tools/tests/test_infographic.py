# -*- coding: utf-8 -*-
"""Tests for tools/infographic.py. Run: python -m pytest tools/tests -v"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import infographic as ig  # noqa: E402


def make_vault(tmp_path: Path) -> Path:
    lectures = tmp_path / "01 - Lectures" / "99 - PoM 2" / "02 - Repro" / "Week 5"
    lectures.mkdir(parents=True)
    (lectures / "09 - Pathology of 1st Trimester Bleeding.md").write_text("# a\n", encoding="utf-8")
    (lectures / "11 - Approach to First Trimester Bleeding & Ultrasound.md").write_text("# b\n", encoding="utf-8")
    (tmp_path / "Attachments").mkdir()
    return tmp_path


def test_find_note_by_substring(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    found = ig.find_note(vault, "pathology of 1st trimester")
    assert found.name == "09 - Pathology of 1st Trimester Bleeding.md"


def test_find_note_accepts_a_path(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    target = next(vault.rglob("09 - *.md"))
    assert ig.find_note(vault, str(target)) == target


def test_find_note_refuses_ambiguity(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    with pytest.raises(ValueError) as err:
        ig.find_note(vault, "trimester bleeding")
    assert "09 - Pathology" in str(err.value)
    assert "11 - Approach" in str(err.value)


def test_find_note_missing(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    with pytest.raises(FileNotFoundError):
        ig.find_note(vault, "no such lecture")


OBSIDIAN = """---
type: LectureNote
tags: LectureNote, -nograph
---
# Overview chart: <u>Pathology of first trimester bleeding</u>

**Three causes** worked up by **[[beta hCG|β-hCG]] + ultrasound**.

![[hydatidiform mole.png|600]]

| | **[[spontaneous abortion\\|Spontaneous abortion]]** | [[ectopic pregnancy]] |
| --- | --- | --- |
| **Causes** | <mark class="hltr-orange">PID</mark> · <font color="#e424b7">cyto</font> | x |

> [!multi-column]
>> [!pink] Maternal
>> - basal plate
>
>> [!purple] Fetal
>> - chorionic plate

> [!check] Objectives
> 1. Describe implantation
"""


def test_clean_markdown_strips_obsidian_syntax() -> None:
    out = ig.clean_markdown(OBSIDIAN)
    for bad in ("[[", "]]", "![[", "<u>", "<mark", "<font", "[!pink]", "[!multi-column]", "type: LectureNote"):
        assert bad not in out, bad
    assert "β-hCG" in out
    assert "Spontaneous abortion" in out
    assert "ectopic pregnancy" in out
    assert "PID" in out and "cyto" in out
    assert "Maternal" in out and "basal plate" in out
    assert "Objectives" in out and "Describe implantation" in out
    assert "hydatidiform mole.png" not in out
