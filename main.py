import streamlit as st
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs

# ─────────────────────────────────────────────
# 페이지 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="유튜브 댓글 뷰어",
    page_icon="🎬",
    layout="wide"
)

# ─────────────────────────────────────────────
# API 키 불러오기 (Streamlit Secrets 사용)
# ─────────────────────────────────────────────
try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except KeyError:
    st.error("❌ API 키가 설정되지 않았습니다. Streamlit Secrets에 YOUTUBE_API_KEY를 추가해주세요.")
    st.stop()

# ─────────────────────────────────────────────
# 유튜브 영상 ID 추출 함수
# ─────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    """
    다양한 유튜브 URL 형식에서 video ID를 추출합니다.
    지원 형식:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/shorts/VIDEO_ID
      - https://m.youtube.com/watch?v=VIDEO_ID
    """
    url = url.strip()
    parsed = urlparse(url)

    # youtu.be 단축 URL
    if parsed.netloc in ("youtu.be",):
        return parsed.path.lstrip("/").split("?")[0]

    # youtube.com 일반/모바일/shorts URL
    if parsed.netloc in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        # /shorts/VIDEO_ID 형식
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("?")[0]
        # ?v=VIDEO_ID 형식
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]

    return None

# ─────────────────────────────────────────────
# 영상 정보 가져오기 함수
# ─────────────────────────────────────────────
def get_video_info(youtube, video_id: str) -> dict | None:
    """영상 제목, 채널명, 썸네일, 조회수, 댓글수 반환"""
    try:
        response = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        ).execute()

        if not response["items"]:
            return None

        item = response["items"][0]
        snippet = item["snippet"]
        stats = item.get("statistics", {})

        return {
            "title": snippet.get("title", "제목 없음"),
            "channel": snippet.get("channelTitle", "채널 없음"),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
        }
    except Exception as e:
        st.error(f"영상 정보를 가져오는 중 오류 발생: {e}")
        return None

# ─────────────────────────────────────────────
# 댓글 가져오기 함수
# ─────────────────────────────────────────────
def get_comments(youtube, video_id: str, max_results: int = 100, order: str = "relevance") -> list[dict]:
    """
    유튜브 댓글을 가져옵니다.
    order: 'relevance'(인기순) 또는 'time'(최신순)
    """
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_results:
            fetch_count = min(100, max_results - len(comments))

            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=fetch_count,
                order=order,
                pageToken=next_page_token,
                textFormat="plainText"
            )
            response = request.execute()

            for item in response.get("items", []):
                top_comment = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "작성자": top_comment.get("authorDisplayName", "알 수 없음"),
                    "댓글 내용": top_comment.get("textDisplay", ""),
                    "좋아요 수": top_comment.get("likeCount", 0),
                    "작성 시간": top_comment.get("publishedAt", "")[:10],  # YYYY-MM-DD만 표시
                    "답글 수": item["snippet"].get("totalReplyCount", 0),
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except Exception as e:
        error_msg = str(e)
        if "commentsDisabled" in error_msg:
            st.warning("⚠️ 이 영상은 댓글이 비활성화되어 있습니다.")
        elif "forbidden" in error_msg.lower():
            st.error("❌ API 접근 권한이 없습니다. API 키를 확인해주세요.")
        else:
            st.error(f"댓글을 가져오는 중 오류 발생: {e}")

    return comments

# ─────────────────────────────────────────────
# 숫자 포맷 함수 (1000 → 1,000)
# ─────────────────────────────────────────────
def format_number(n: int) -> str:
    return f"{n:,}"

# ─────────────────────────────────────────────
# 메인 UI
# ─────────────────────────────────────────────
st.title("🎬 유튜브 댓글 뷰어")
st.markdown("유튜브 영상 링크를 입력하면 댓글을 불러옵니다.")
st.divider()

# ── 입력 영역 ──
with st.form("url_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        url_input = st.text_input(
            "🔗 유튜브 영상 URL 입력",
            placeholder="https://www.youtube.com/watch?v=...",
            label_visibility="collapsed"
        )
    with col2:
        submitted = st.form_submit_button("🔍 댓글 불러오기", use_container_width=True)

# ── 옵션 영역 ──
with st.expander("⚙️ 옵션 설정", expanded=False):
    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        max_comments = st.slider(
            "최대 댓글 수",
            min_value=10,
            max_value=500,
            value=100,
            step=10
        )
    with opt_col2:
        order_option = st.radio(
            "정렬 기준",
            options=["인기순", "최신순"],
            horizontal=True
        )

order_map = {"인기순": "relevance", "최신순": "time"}

# ── 실행 영역 ──
if submitted:
    if not url_input:
        st.warning("⚠️ URL을 입력해주세요.")
    else:
        video_id = extract_video_id(url_input)

        if not video_id:
            st.error("❌ 올바른 유튜브 URL이 아닙니다. URL을 다시 확인해주세요.")
        else:
            # YouTube API 클라이언트 생성
            youtube = build("youtube", "v3", developerKey=API_KEY)

            # ── 영상 정보 표시 ──
            with st.spinner("영상 정보를 불러오는 중..."):
                video_info = get_video_info(youtube, video_id)

            if video_info:
                info_col1, info_col2 = st.columns([1, 2])
                with info_col1:
                    if video_info["thumbnail"]:
                        st.image(video_info["thumbnail"], use_container_width=True)
                with info_col2:
                    st.subheader(video_info["title"])
                    st.caption(f"📺 채널: {video_info['channel']}")
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    with metric_col1:
                        st.metric("👁️ 조회수", format_number(video_info["view_count"]))
                    with metric_col2:
                        st.metric("👍 좋아요", format_number(video_info["like_count"]))
                    with metric_col3:
                        st.metric("💬 총 댓글수", format_number(video_info["comment_count"]))

                st.divider()

                # ── 댓글 불러오기 ──
                with st.spinner(f"댓글을 불러오는 중... (최대 {max_comments}개)"):
                    comments = get_comments(
                        youtube,
                        video_id,
                        max_results=max_comments,
                        order=order_map[order_option]
                    )

                if comments:
                    st.success(f"✅ 댓글 **{len(comments)}개**를 불러왔습니다! ({order_option})")

                    # ── 검색 필터 ──
                    search_keyword = st.text_input(
                        "🔎 댓글 내용 검색",
                        placeholder="키워드를 입력하세요..."
                    )

                    import pandas as pd
                    df = pd.DataFrame(comments)

                    # 키워드 필터 적용
                    if search_keyword:
                        df = df[df["댓글 내용"].str.contains(search_keyword, case=False, na=False)]
                        st.info(f"🔍 '{search_keyword}' 검색 결과: {len(df)}개")

                    # ── 댓글 테이블 표시 ──
                    st.dataframe(
                        df,
                        use_container_width=True,
                        height=500,
                        column_config={
                            "작성자": st.column_config.TextColumn("👤 작성자", width="medium"),
                            "댓글 내용": st.column_config.TextColumn("💬 댓글 내용", width="large"),
                            "좋아요 수": st.column_config.NumberColumn("👍 좋아요", width="small"),
                            "작성 시간": st.column_config.TextColumn("📅 작성일", width="small"),
                            "답글 수": st.column_config.NumberColumn("↩️ 답글", width="small"),
                        }
                    )

                    # ── CSV 다운로드 ──
                    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        label="⬇️ CSV로 다운로드",
                        data=csv_data,
                        file_name=f"youtube_comments_{video_id}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.info("불러온 댓글이 없습니다.")

st.divider()
st.caption("🏫 당곡고등학교 | YouTube Data API v3 활용 댓글 뷰어")
