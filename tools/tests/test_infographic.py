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


def test_build_prompt_carries_title_note_and_rules() -> None:
    prompt = ig.build_prompt("Pathology of first trimester bleeding", "Complete mole: 46 XX.\n", "detailed")
    assert "Pathology of first trimester bleeding" in prompt
    assert "Complete mole: 46 XX." in prompt
    assert "only facts from the source" in prompt.lower() or "only facts in the source" in prompt.lower()
    assert "portrait" in prompt.lower()
    assert "detailed" in prompt.lower()


def test_build_prompt_concise_differs() -> None:
    a = ig.build_prompt("T", "body\n", "concise")
    b = ig.build_prompt("T", "body\n", "detailed")
    assert a != b
    assert "concise" in a.lower()


def test_build_prompt_rejects_unknown_detail() -> None:
    with pytest.raises(ValueError):
        ig.build_prompt("T", "body\n", "lavish")


def test_dry_run_prints_prompt_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = make_vault(tmp_path)
    monkeypatch.setattr(ig, "VAULT", vault)
    monkeypatch.delenv(ig.KEY_VAR, raising=False)
    rc = ig.main(["pathology of 1st", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pathology of 1st Trimester Bleeding" in out
    assert not list((vault / "Attachments").iterdir())


import base64  # noqa: E402


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status
        self._payload = payload or {}
        self.text = text or str(payload)

    def json(self) -> dict:
        return self._payload


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake"


def image_payload() -> dict:
    return {"candidates": [{"content": {"parts": [
        {"text": "Here is your infographic."},
        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG_BYTES).decode()}},
    ]}}]}


def test_generate_image_returns_png_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_post(url: str, headers: dict | None = None, json: dict | None = None, timeout: float | None = None) -> FakeResponse:
        calls.append((url, headers, json))
        return FakeResponse(200, image_payload())

    monkeypatch.setattr(ig.requests, "post", fake_post)
    out = ig.generate_image("draw", "KEY123", model="m-test")
    assert out == PNG_BYTES
    url, headers, body = calls[0]
    assert url.endswith("/models/m-test:generateContent")
    assert headers["x-goog-api-key"] == "KEY123"
    assert body["contents"][0]["parts"][0]["text"] == "draw"
    assert "IMAGE" in body["generationConfig"]["responseModalities"]


def test_generate_image_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    seq = [FakeResponse(429, text="slow down"), FakeResponse(503, text="busy"), FakeResponse(200, image_payload())]
    slept = []
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: seq.pop(0))
    out = ig.generate_image("draw", "K", sleep=slept.append)
    assert out == PNG_BYTES
    assert len(slept) == 2


def test_generate_image_gives_up_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: FakeResponse(429, text="quota"))
    with pytest.raises(RuntimeError) as err:
        ig.generate_image("draw", "K", sleep=lambda s: None)
    assert "429" in str(err.value) and "quota" in str(err.value)


def test_generate_image_fails_fast_on_400(monkeypatch: pytest.MonkeyPatch) -> None:
    posts = []
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: posts.append(1) or FakeResponse(400, text="bad key"))
    with pytest.raises(RuntimeError) as err:
        ig.generate_image("draw", "K", sleep=lambda s: None)
    assert "400" in str(err.value) and len(posts) == 1


def test_generate_image_text_only_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"candidates": [{"content": {"parts": [{"text": "I cannot draw that."}]}}]}
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: FakeResponse(200, payload))
    with pytest.raises(RuntimeError) as err:
        ig.generate_image("draw", "K")
    assert "I cannot draw that." in str(err.value)


def test_read_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ig.KEY_VAR, raising=False)
    with pytest.raises(ig.ApiKeyMissing) as err:
        ig.read_api_key()
    assert "aistudio.google.com" in str(err.value)


def test_read_api_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ig.KEY_VAR, "abc")
    assert ig.read_api_key() == "abc"
