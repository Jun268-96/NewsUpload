import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import uuid
from urllib.parse import urljoin, urlparse

# --- PRD 5. 기술 요구사항 & 9. 제약사항 관련 ---
# PRD는 서버 없는 로컬 스토리지를 명시했으나, 이 프로토타입은 Streamlit의 서버 기반 세션 상태를 활용합니다.
# st.session_state는 사용자의 브라우저 세션 동안 데이터를 메모리에 저장하는 역할을 합니다.
if 'news_list' not in st.session_state:
    st.session_state.news_list = []

# --- PRD 3.1 & 4.2 관련 ---
CATEGORIES = {
    "사회": "blue",
    "과학": "green",
    "기술": "orange",
    "생활/문화": "violet",
    "세계": "red"
}

# --- PRD 3.1.3 메타데이터 추출 기능 ---
def fetch_metadata(url):
    """URL에서 뉴스 메타데이터(제목, 설명, 이미지)를 추출합니다."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Open Graph 태그 우선 탐색
        title = soup.find('meta', property='og:title')
        description = soup.find('meta', property='og:description')
        image_url = soup.find('meta', property='og:image')

        # OG 태그가 없을 경우 대체 탐색
        title = title['content'] if title else soup.title.string
        description = description['content'] if description else ''
        if image_url:
            image_url = image_url['content']
        else:
            # 기본 이미지 탐색 (첫 번째 의미 있는 이미지)
            first_img = soup.find('img')
            if first_img and first_img.get('src'):
                # 상대 경로를 절대 경로로 변환
                image_url = urljoin(url, first_img['src'])

        return {
            "title": title.strip() if title else "제목을 찾을 수 없습니다",
            "description": description.strip() if description else "설명을 찾을 수 없습니다",
            "image_url": image_url,
            "success": True
        }
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"URL에 접근할 수 없습니다: {e}"}
    except Exception as e:
        return {"success": False, "error": f"메타데이터 추출 중 오류 발생: {e}"}

# --- 1. 프로젝트 개요 & 6. 화면 구성 ---
st.set_page_config(layout="wide", page_title="EduNews Board")
st.title("👨‍🏫 EduNews Board")
st.caption("초등학교 고학년 대상 교실용 뉴스 큐레이션 플랫폼")

# --- 7.1 뉴스 등록 시나리오 ---
with st.expander("📰 새 뉴스 추가하기"):
    with st.form("new_news_form", clear_on_submit=True):
        news_url = st.text_input("뉴스 기사 URL을 입력하세요:", placeholder="https://example.com/news/123")
        news_category = st.selectbox("주제를 선택하세요:", options=list(CATEGORIES.keys()))
        submitted = st.form_submit_button("등록하기")

        if submitted and news_url:
            with st.spinner("뉴스 정보를 가져오는 중입니다..."):
                metadata = fetch_metadata(news_url)

            if metadata["success"]:
                # PRD 3.1 요구사항 충족
                new_article = {
                    "id": str(uuid.uuid4()),
                    "url": news_url,
                    "title": metadata["title"],
                    "image_url": metadata["image_url"],
                    "category": news_category,
                    "added_date": datetime.now() # 등록 날짜 자동 기록
                }
                st.session_state.news_list.append(new_article)
                st.success(f"'{metadata['title']}' 뉴스를 성공적으로 등록했습니다!")
                st.rerun() # 화면을 새로고침하여 목록에 즉시 반영
            else:
                st.error(metadata["error"])


# --- 3.2 & 6.1 뉴스 목록 표시 기능 ---
if not st.session_state.news_list:
    st.info("아직 등록된 뉴스가 없습니다. '새 뉴스 추가하기'를 통해 뉴스를 등록해주세요.")
else:
    for category, color in CATEGORIES.items():
        st.markdown(f"---")
        # 주제별 색상 구분 (PRD 4.2)
        st.subheader(f":{color}[{category}]")

        # 주제별 뉴스 필터링 및 최신순 정렬 (PRD 3.2.1, 3.2.2)
        category_news = [news for news in st.session_state.news_list if news["category"] == category]
        sorted_news = sorted(category_news, key=lambda x: x['added_date'], reverse=True)

        if not sorted_news:
            st.write("이 주제의 뉴스가 아직 없습니다.")
            continue

        # 카드형 레이아웃 (PRD 3.2.3)
        # 화면 너비에 따라 3개 또는 4개의 컬럼으로 표시
        cols = st.columns(3)
        for i, news in enumerate(sorted_news):
            col = cols[i % 3]
            with col:
                # 카드 컨테이너
                with st.container(border=True):
                    # 6.2 뉴스 카드 구성 & 3.2.4 미리보기 이미지
                    # 이미지가 없을 경우 주제별 기본 아이콘 대신 텍스트 메시지 표시
                    if news["image_url"]:
                        st.image(news["image_url"])
                    else:
                        st.markdown(f"<p style='text-align: center; color: grey; padding: 20px 0;'>이미지 없음</p>", unsafe_allow_html=True)
                    
                    # 큰 폰트 사이즈, 링크 이동 (PRD 4.1, 4.2, 3.3.1)
                    # Streamlit의 마크다운 링크는 자동으로 새 탭에서 열림
                    st.markdown(f"##### [{news['title']}]({news['url']})")
                    
                    # 등록 날짜 및 관리 기능 버튼
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.caption(f"등록: {news['added_date'].strftime('%Y-%m-%d %H:%M')}")
                    with col2:
                        # 3.4.1 뉴스 삭제 기능
                        if st.button("삭제", key=f"del_{news['id']}", type="secondary", use_container_width=True):
                            st.session_state.news_list = [n for n in st.session_state.news_list if n['id'] != news['id']]
                            st.rerun()