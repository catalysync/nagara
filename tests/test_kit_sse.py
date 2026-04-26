import json

import pytest

from nagara.kit.sse import (
    complete_event,
    error_event,
    format_event,
    progress_event,
    stream_events,
)


def test_format_event_json_dumps_dict():
    out = format_event({"a": 1})
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    body = out[len("data: ") :].rstrip("\n")
    assert json.loads(body) == {"a": 1}


def test_format_event_passes_string_through():
    out = format_event("hello")
    assert out == "data: hello\n\n"


def test_format_event_with_id_and_event_type():
    out = format_event({"x": 2}, event="progress", id="r1")
    assert "id: r1\n" in out
    assert "event: progress\n" in out
    assert 'data: {"x": 2}\n' in out


def test_format_event_handles_multiline_string():
    out = format_event("line1\nline2", event="msg")
    assert "data: line1\n" in out
    assert "data: line2\n" in out


def test_progress_event_has_event_type():
    out = progress_event({"pct": 50}, id="r1")
    assert "event: progress" in out
    assert "id: r1" in out


def test_complete_event_default_payload():
    out = complete_event(id="r1")
    assert "event: complete" in out
    assert '"status": "complete"' in out


def test_complete_event_custom_payload():
    out = complete_event({"rows": 100}, id="r1")
    assert '"rows": 100' in out


def test_error_event_includes_extra_fields():
    out = error_event("boom", code="timeout", retry_in=30)
    body_line = [ln for ln in out.split("\n") if ln.startswith("data: ")][0]
    payload = json.loads(body_line[len("data: ") :])
    assert payload == {"error": "boom", "code": "timeout", "retry_in": 30}


@pytest.mark.asyncio
async def test_stream_events_encodes_dicts_and_passes_strings():
    async def gen():
        yield {"a": 1}
        yield format_event("raw")

    out = []
    async for chunk in stream_events(gen()):
        out.append(chunk)
    assert out[0] == b'data: {"a": 1}\n\n'
    assert out[1] == b"data: raw\n\n"
