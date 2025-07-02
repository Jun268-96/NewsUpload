import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import uuid
from urllib.parse import urljoin
import pandas as pd

# --- 핵심 변경점 1: Google Sheets Connection 설정 ---
from streamlit_gsheets import GSheetsConnection

# --- PRD 3.1 & 4.2 관련 ---
CATEGORIES = {
    "사회": "blue",
    "과학": "green",
    "기술": "orange",
    "생활/문화": "violet",
    "세계": "red"
}

# --- PRD 3.1.3 메타데이터 추출 기능 (기존과 동일) ---
def fetch_metadata(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('meta', property='og:title')
        image_url = soup.find('meta', property='og:image')
        title = title['content'] if title else soup.title.string
        if image_url:
            image_url = urljoin(url, image_url['content'])
        return {"title": title.strip() if title else "제목을 찾을 수 없습니다", "image_url": image_url, "success": True}
    except Exception:
        return {"success": False}

# --- 1. 프로젝트 개요 & 6. 화면 구성 ---
st.set_page_config(layout="wide", page_title="EduNews Board")
st.title("👨‍🏫 EduNews Board")
st.caption("초등학교 고학년 대상 교실용 뉴스 큐레이션 플랫폼")

# --- 핵심 변경점 2: Google Sheets에 연결하고 데이터 불러오기 ---
# Create a connection object.
conn = st.connection("gsheets", type=GSheetsConnection)
# 기존 데이터를 DataFrame으로 읽어오기
try:
    existing_data = conn.read(worksheet="Sheet1", usecols=list(range(6)), ttl=5)
    # 빈 행 제거
    existing_data = existing_data.dropna(how="all")
    # 컬럼명이 없을 경우 기본 컬럼명 설정
    if existing_data.empty or existing_data.columns.tolist()[0] != 'id':
        existing_data.columns = ['id', 'url', 'title', 'image_url', 'category', 'added_date']
    # DataFrame을 딕셔너리 리스트로 변환 (기존 코드와 호환을 위해)
    news_list = existing_data.to_dict('records')
except Exception as e:
    st.error(f"Google Sheets 연결 오류: {e}")
    existing_data = pd.DataFrame(columns=['id', 'url', 'title', 'image_url', 'category', 'added_date'])
    news_list = []


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
                new_article = {
                    "id": str(uuid.uuid4()),
                    "url": news_url,
                    "title": metadata["title"],
                    "image_url": metadata["image_url"],
                    "category": news_category,
                    "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # --- 핵심 변경점 3: Google Sheets에 새 행 추가하기 ---
                try:
                    updated_df = pd.DataFrame([new_article])
                    conn.update(worksheet="Sheet1", data=pd.concat([existing_data, updated_df], ignore_index=True))
                    st.success(f"'{metadata['title']}' 뉴스를 성공적으로 등록했습니다!")
                    st.rerun() # 화면 새로고침
                except Exception as e:
                    st.error(f"뉴스 등록 중 오류가 발생했습니다: {e}")
            else:
                st.error("뉴스 정보를 가져오는데 실패했습니다. URL을 확인해주세요.")

# --- 뉴스 목록 표시 (기존 코드와 거의 동일) ---
if not news_list:
    st.info("아직 등록된 뉴스가 없습니다. '새 뉴스 추가하기'를 통해 뉴스를 등록해주세요.")
else:
    for category, color in CATEGORIES.items():
        st.markdown(f"---")
        st.subheader(f":{color}[{category}]")

        category_news = [news for news in news_list if news["category"] == category]
        # 날짜 문자열을 datetime 객체로 변환하여 정렬
        try:
            sorted_news = sorted(category_news, key=lambda x: datetime.strptime(str(x['added_date']), "%Y-%m-%d %H:%M:%S"), reverse=True)
        except (ValueError, TypeError): # 혹시 모를 데이터 오류 대비
            sorted_news = category_news

        if not sorted_news:
            st.write("이 주제의 뉴스가 아직 없습니다.")
            continue

        cols = st.columns(3)
        for i, news in enumerate(sorted_news):
            col = cols[i % 3]
            with col:
                with st.container(border=True):
                    if pd.notna(news["image_url"]) and news["image_url"]:
                        st.image(news["image_url"])
                    else:
                        st.markdown(f"<p style='text-align: center; color: grey; padding: 20px 0;'>이미지 없음</p>", unsafe_allow_html=True)
                    
                    st.markdown(f"##### [{str(news['title'])}]({str(news['url'])})")
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.caption(f"등록: {str(news['added_date'])}")
                    with col2:
                        # --- 핵심 변경점 4: 삭제 로직 수정 ---
                        if st.button("삭제", key=f"del_{news['id']}", type="secondary", use_container_width=True):
                            try:
                                news_to_delete_id = news['id']
                                # 삭제할 행을 제외한 새로운 DataFrame 생성
                                updated_data = existing_data[existing_data['id'] != news_to_delete_id]
                                # 전체 시트 덮어쓰기
                                conn.update(worksheet="Sheet1", data=updated_data)
                                st.success("뉴스를 삭제했습니다.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 중 오류가 발생했습니다: {e}")