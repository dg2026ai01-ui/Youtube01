import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs

# ════════════════════════════════════════════════
# 페이지 설정
# ════════════════════════════════════════════════
st.set_page_config(
    page_title="유튜브 댓글 뷰어",
    page_icon="🎬",
    layout="wide"
)

# ════════════════════════════════════════════════
# API 키 로드
# ════════════════════════════════════════════════
try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except KeyError:
    st.error("❌ API 키가 없습니다. Streamlit Secrets에 YOUTUBE_API_KEY를 추가하세요.")
    st.stop()

# ════════════════════════════════════════════════
# 유틸 함수
# ════════════════════════════════════════════════
def extract_video_id(url: str):
    url = url.strip()
    parsed = urlparse(url)

    if parsed.netloc == "youtu.be":
        return parsed.path.lstrip("/").split("?")[0]

    if parsed.netloc in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("?")[0]
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]

    return None


def get_video_info(youtube, video_id: str):
    try:
        res = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if not res["items"]:
            return None

        item    = res["items"][0]
        snippet = item["snippet"]
        stats   = item.get("statistics", {})

        return {
            "title":         snippet.get("title", "제목 없음"),
            "channel":       snippet.get("channelTitle", "알 수 없음"),
            "thumbnail":     snippet["thumbnails"].get("high", {}).get("url", ""),
            "published":     snippet.get("publishedAt", "")[:10],
            "view_count":    int(stats.get("viewCount",    0)),
            "like_count":    int(stats.get("likeCount",    0)),
            "comment_count": int(stats.get("commentCount", 0)),
        }
    except Exception as e:
        st.error(f"영상 정보 오류: {e}")
        return None


def get_comments(youtube, video_id: str, max_results: int, order: str):
    comments        = []
    next_page_token = None

    try:
        while len(comments) < max_results:
            fetch = min(100, max_results - len(comments))

            res = youtube.commentThreads().list(
                part       = "snippet",
                videoId    = video_id,
                maxResults = fetch,
                order      = order,
                pageToken  = next_page_token,
                textFormat = "plainText"
            ).execute()

            for item in res.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "작성자":    top.get("authorDisplayName", "알 수 없음"),
                    "댓글 내용": top.get("textDisplay", ""),
                    "좋아요":    top.get("likeCount", 0),
                    "답글 수":   item["snippet"].get("totalReplyCount", 0),
                    "작성일":    top.get("publishedAt", "")[:10],
                })

            next_page_token = res.get("nextPageToken")
            if not next_page_token:
                break

    except Exception as e:
        msg = str(e)
        if "commentsDisabled" in msg:
            st.warning("⚠️ 이 영상은 댓글이 비활성화되어 있습니다.")
        elif "quotaExceeded" in msg:
            st.error("❌ API 할당량을 초과했습니다. 내일 다시 시도하세요.")
        else:
            st.error(f"댓글 로드 오류: {e}")

    return comments


def fmt(n: int) -> str:
    return f"{n:,}"

# ════════════════════════════════════════════════
# UI — 헤더
# ════════════════════════════════════════════════
st.title("🎬 유튜브 댓글 뷰어")
st.caption("유튜브 영상 링크를 붙여넣으면 댓글을 수집합니다.")
st.divider()

# ════════════════════════════════════════════════
# UI — 입력 폼
# ════════════════════════════════════════════════
with st.form("input_form"):
    url_input = st.text_input(
        "🔗 유튜브 URL",
        placeholder="https://www.youtube.com/watch?v=XXXXXXXXXXX"
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        max_comments = st.slider("최대 댓글 수", 10, 500, 100, step=10)
    with col_b:
        order_label = st.radio("정렬", ["인기순", "최신순"], horizontal=True)
    with col_c:
        st.write("")
        st.write("")
        submitted = st.form_submit_button("🔍 댓글 불러오기", use_container_width=True)

order_map = {"인기순": "relevance", "최신순": "time"}

# ════════════════════════════════════════════════
# 실행 로직
# ════════════════════════════════════════════════
if submitted:

    if not url_input.strip():
        st.warning("⚠️ URL을 입력해주세요.")
        st.stop()

    video_id = extract_video_id(url_input)
    if not video_id:
        st.error("❌ 올바른 유튜브 URL이 아닙니다. 다시 확인해주세요.")
        st.stop()

    youtube = build("youtube", "v3", developerKey=API_KEY)

    with st.spinner("📡 영상 정보를 불러오는 중..."):
        info = get_video_info(youtube, video_id)

    if not info:
        st.error("❌ 영상 정보를 가져올 수 없습니다.")
        st.stop()

    c1, c2 = st.columns([1, 2])
    with c1:
        if info["thumbnail"]:
            st.image(info["thumbnail"], use_container_width=True)
    with c2:
        st.subheader(info["title"])
        st.caption(f"📺 {info['channel']}  ·  📅 업로드: {info['published']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("👁️ 조회수",    fmt(info["view_count"]))
        m2.metric("👍 좋아요",    fmt(info["like_count"]))
        m3.metric("💬 전체 댓글", fmt(info["comment_count"]))

    st.divider()

    with st.spinner(f"💬 댓글 수집 중... (최대 {max_comments}개, {order_label})"):
        comments = get_comments(
            youtube,
            video_id,
            max_results = max_comments,
            order       = order_map[order_label]
        )

    if not comments:
        st.info("수집된 댓글이 없습니다.")
        st.stop()

    df = pd.DataFrame(comments)

    st.success(f"✅ 댓글 **{len(df)}개** 수집 완료! ({order_label})")

    keyword = st.text_input("🔎 댓글 검색 (키워드 필터)", placeholder="검색어를 입력하세요")
    if keyword:
        df = df[df["댓글 내용"].str.contains(keyword, case=False, na=False)]
        st.info(f"🔍 '{keyword}' 검색 결과: **{len(df)}개**")

    with st.expander("📊 수집 댓글 통계 보기"):
        s1, s2, s3 = st.columns(3)
        s1.metric("평균 좋아요", f"{df['좋아요'].mean():.1f}")
        s2.metric("최대 좋아요", fmt(int(df['좋아요'].max())))
        s3.metric("총 답글 수", fmt(int(df['답글 수'].sum())))

        st.bar_chart(
            df.sort_values("좋아요", ascending=False).head(10).set_index("작성자")["좋아요"],
            height=250
        )

    st.dataframe(
        df,
        use_container_width=True,
        height=480,
        column_config={
            "작성자":    st.column_config.TextColumn("👤 작성자",    width="medium"),
            "댓글 내용": st.column_config.TextColumn("💬 댓글 내용", width="large"),
            "좋아요":    st.column_config.NumberColumn("👍 좋아요",   width="small"),
            "답글 수":   st.column_config.NumberColumn("↩️ 답글",    width="small"),
            "작성일":    st.column_config.TextColumn("📅 작성일",    width="small"),
        }
    )

    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label     = "⬇️ CSV 다운로드",
        data      = csv,
        file_name = f"comments_{video_id}.csv",
        mime      = "text/csv",
        use_container_width=True
    )

st.divider()
st.caption("🏫 당곡고등학교 | YouTube Data API v3")
