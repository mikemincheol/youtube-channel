import re
from urllib.parse import unquote, urlparse

import requests
import streamlit as st

API_URL = "https://www.googleapis.com/youtube/v3/channels"


def parse_channel_input(text: str):
    """채널 링크(또는 @핸들, UC... ID)를 API 조회 파라미터로 변환합니다."""
    text = text.strip()
    if not text:
        return None

    # 링크 없이 핸들이나 채널 ID만 입력한 경우
    if text.startswith("@"):
        return {"forHandle": unquote(text)}
    if re.fullmatch(r"UC[\w-]{22}", text):
        return {"id": text}

    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text

    parsed = urlparse(text)
    host = parsed.netloc.lower()
    if host != "youtube.com" and not host.endswith(".youtube.com"):
        return None

    segments = [unquote(s) for s in parsed.path.split("/") if s]
    if not segments:
        return None

    first = segments[0]
    if first.startswith("@"):
        return {"forHandle": first}
    if first == "channel" and len(segments) > 1:
        return {"id": segments[1]}
    return None


st.set_page_config(page_title="유튜브 채널 정보 조회", layout="centered")
st.title("유튜브 채널 정보 조회")
st.caption("채널 링크를 입력하면 YouTube Data API 응답을 그대로 보여 줍니다.")

try:
    api_key = st.secrets["YOUTUBE_API_KEY"]
except (KeyError, FileNotFoundError):
    st.error("st.secrets에 YOUTUBE_API_KEY가 설정되어 있지 않습니다.")
    st.stop()

with st.form("channel_form"):
    channel_url = st.text_input(
        "유튜브 채널 링크",
        placeholder="https://www.youtube.com/@핸들 또는 https://www.youtube.com/channel/UC...",
    )
    submitted = st.form_submit_button("조회")

if submitted:
    lookup = parse_channel_input(channel_url)
    if lookup is None:
        st.error(
            "지원하지 않는 링크 형식입니다. "
            "youtube.com/@핸들 또는 youtube.com/channel/UC... 형식으로 입력해 주세요."
        )
        st.stop()

    params = {
        "part": "snippet,statistics,contentDetails",
        "key": api_key,
        **lookup,
    }

    try:
        with st.spinner("조회 중입니다"):
            response = requests.get(API_URL, params=params, timeout=10)
    except requests.RequestException as exc:
        # 예외 메시지에 요청 URL(API 키 포함)이 담길 수 있어 종류만 표시합니다
        st.error(f"API 요청에 실패했습니다 ({type(exc).__name__})")
        st.stop()

    try:
        data = response.json()
    except ValueError:
        st.error(f"JSON이 아닌 응답을 받았습니다 (HTTP {response.status_code})")
        st.stop()

    if not response.ok:
        message = data.get("error", {}).get("message", "알 수 없는 오류")
        st.error(f"API 오류 (HTTP {response.status_code}) {message}")
        st.stop()

    items = data.get("items")
    if not items:
        st.warning("해당 채널을 찾지 못했습니다. 링크를 다시 확인해 주세요.")
        st.stop()

    channel = items[0]
    stats = channel.get("statistics", {})

    def fmt(key):
        value = stats.get(key)
        return f"{int(value):,}" if value is not None else "비공개"

    st.subheader(channel.get("snippet", {}).get("title", "채널 이름 없음"))

    col1, col2, col3 = st.columns(3)
    col1.metric("구독자 수", fmt("subscriberCount"))
    col2.metric("총 조회수", fmt("viewCount"))
    col3.metric("영상 수", fmt("videoCount"))
