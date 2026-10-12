"""261012 P1 — publish_single() Phase A 재시도에서 Meta code=9004 +
error_subcode=2207052 응답이 정확히 확인된 경우에만 10초→60초 대기한다.
기존 3회 재시도·timeout·Phase B 동작은 무변경. HTTP·sleep 전부 mock(Live 요청 0건).

Target Test:
  1. 9004 후 회복        2. 재시도 소진          3. 다른 오류 대기 0회
  4. 응답 불명 대기 0회   5. 유사 코드 대기 0회   6. 첫 시도 성공 시 추가 생성·게시 없음
"""

from unittest.mock import patch

import pytest
import requests

from launcher import main as launcher_main


class _Resp:
    def __init__(self, status_code=200, json_data=None, json_exc=None):
        self.status_code = status_code
        self._json_data = json_data
        self._json_exc = json_exc
        self.text = "raw"

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json_data


_MEDIA_OK = _Resp(200, {"id": "creation123"})
_PUBLISH_OK = _Resp(200, {"id": "media456"})
_STATUS_FINISHED = _Resp(200, {"status_code": "FINISHED"})


def _meta_err(code, subcode):
    return _Resp(400, {"error": {"message": "Only photo or video can be accepted as media type.",
                                 "type": "OAuthException", "code": code,
                                 "error_subcode": subcode, "fbtrace_id": "X"}})


def _urls(mock_post):
    return [c.args[0] for c in mock_post.call_args_list]


def _run(post_side_effect):
    with patch("requests.post", side_effect=post_side_effect) as mp, \
         patch("requests.get", return_value=_STATUS_FINISHED), \
         patch("time.sleep") as ms:
        result = launcher_main.publish_single("r1", "http://img", "cap", "tok", "iguser")
    media = [u for u in _urls(mp) if u.endswith("/media")]
    publish = [u for u in _urls(mp) if u.endswith("/media_publish")]
    return result, ms, media, publish


def test_9004_then_recover_waits_10_once():
    result, ms, media, publish = _run([_meta_err(9004, 2207052), _MEDIA_OK, _PUBLISH_OK])
    assert result["ok"] is True
    assert [c.args[0] for c in ms.call_args_list] == [10]
    assert len(media) == 2 and len(publish) == 1


def test_9004_exhausted_waits_10_then_60_and_no_publish():
    e = _meta_err(9004, 2207052)
    result, ms, media, publish = _run([e, e, e])
    assert result["ok"] is False
    assert [c.args[0] for c in ms.call_args_list] == [10, 60]
    assert len(media) == 3 and len(publish) == 0


def test_other_meta_error_keeps_existing_no_wait():
    e = _meta_err(100, 2108006)
    result, ms, media, publish = _run([e, e, e])
    assert result["ok"] is False
    assert ms.call_count == 0
    assert len(media) == 3 and len(publish) == 0


@pytest.mark.parametrize("exc", [
    requests.exceptions.ConnectTimeout("connect timeout"),  # response 없음
    requests.exceptions.ReadTimeout("read timeout"),         # response 없음
])
def test_no_response_errors_no_wait(exc):
    result, ms, media, publish = _run([exc, exc, exc])
    assert result["ok"] is False
    assert ms.call_count == 0
    assert len(publish) == 0


def test_unparseable_body_no_wait():
    bad = _Resp(400, json_exc=ValueError("not json"))
    result, ms, media, publish = _run([bad, bad, bad])
    assert result["ok"] is False
    assert ms.call_count == 0


@pytest.mark.parametrize("code,subcode", [
    (90040, 2207052),
    (9004, 22070520),
    (9004, 2207051),
    (9004, None),
])
def test_similar_codes_no_wait(code, subcode):
    e = _meta_err(code, subcode)
    result, ms, media, publish = _run([e, e, e])
    assert result["ok"] is False
    assert ms.call_count == 0


def test_first_attempt_success_no_wait_no_extra_calls():
    result, ms, media, publish = _run([_MEDIA_OK, _PUBLISH_OK])
    assert result["ok"] is True
    assert ms.call_count == 0
    assert len(media) == 1 and len(publish) == 1
