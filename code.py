import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import uuid
from urllib.parse import urljoin
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- 1. 프로젝트 개요 & 6. 화면 구성 ---
st.set_page_config(layout="wide", page_title="EduNews Board")
st.title("👨‍🏫 EduNews Board")
st.caption("초등학교 고학년 대상 교실용 뉴스 큐레이션 플랫폼")

# --- 상수 정의 ---
CATEGORIES = {
    "사회": "blue",
    "과학": "green",
    "기술": "orange",
    "생활/문화": "violet",
    "세계": "red"
}
# Google Sheet의 헤더와 순서가 일치해야 함
SHEET_HEADERS = ['id', 'url', 'title', 'image_url', 'category', 'added_date']

# --- gspread를 사용한 Google Sheets 연결 함수 ---
@st.cache_resource(ttl=600)  # 10분 동안 연결 캐시
def connect_to_gsheet():
    try:
        creds_json_str = st.secrets["gcp_service_account"]["json_credentials"]
        creds_dict = json.loads(creds_json_str)
        
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 'EduNewsDB'는 실제 Google Sheet 파일 이름입니다.
        spreadsheet = client.open("EduNewsDB") 
        worksheet = spreadsheet.worksheet("Sheet1") # 'Sheet1'은 시트 이름입니다.
        return worksheet
    except Exception as e:
        st.error(f"Google Sheets에 연결하는 중 오류가 발생했습니다: {e}")
        return None

worksheet = connect_to_gsheet()

# --- 메타데이터 추출 함수 (기존과 동일) ---
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

# --- 뉴스 등록 폼 ---
with st.expander("📰 새 뉴스 추가하기"):
    with st.form("new_news_form", clear_on_submit=True):
        news_url = st.text_input("뉴스 기사 URL을 입력하세요:", placeholder="https://example.com/news/123")
        news_category = st.selectbox("주제를 선택하세요:", options=list(CATEGORIES.keys()))
        submitted = st.form_submit_button("등록하기")

        if submitted and news_url and worksheet:
            with st.spinner("뉴스 정보를 가져오는 중입니다..."):
                metadata = fetch_metadata(news_url)

            if metadata["success"]:
                new_article_data = {
                    "id": str(uuid.uuid4()),
                    "url": news_url,
                    "title": metadata["title"],
                    "image_url": metadata["image_url"] or "", # 이미지가 없을 경우 빈 문자열로 저장
                    "category": news_category,
                    "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                # 헤더 순서에 맞게 값 리스트 생성
                row_to_add = [new_article_data.get(h, "") for h in SHEET_HEADERS]
                worksheet.append_row(row_to_add, value_input_option='USER_ENTERED')
                
                st.success(f"'{metadata['title']}' 뉴스를 성공적으로 등록했습니다!")
                st.rerun()
            else:
                st.error("뉴스 정보를 가져오는데 실패했습니다. URL을 확인해주세요.")

# --- 뉴스 목록 표시 ---
if worksheet:
    # Google Sheet에서 데이터 불러오기
    all_data = worksheet.get_all_records()
    if not all_data:
        st.info("아직 등록된 뉴스가 없습니다. '새 뉴스 추가하기'를 통해 뉴스를 등록해주세요.")
    else:
        news_list = pd.DataFrame(all_data)

        for category, color in CATEGORIES.items():
            st.markdown(f"---")
            st.subheader(f":{color}[{category}]")

            # Pandas DataFrame으로 필터링 및 정렬
            category_df = news_list[news_list['category'] == category]
            
            # added_date를 datetime으로 변환하여 정렬 (오류 방지)
            category_df['added_date_dt'] = pd.to_datetime(category_df['added_date'], errors='coerce')
            sorted_df = category_df.sort_values(by='added_date_dt', ascending=False)

            if sorted_df.empty:
                st.write("이 주제의 뉴스가 아직 없습니다.")
                continue

            cols = st.columns(3)
            # DataFrame의 행을 순회하며 뉴스 카드 생성
            for i, news_row in enumerate(sorted_df.itertuples()):
                col = cols[i % 3]
                with col:
                    with st.container(border=True):
                        if pd.notna(news_row.image_url) and news_row.image_url:
                            st.image(news_row.image_url)
                        else:
                            st.markdown(f"<p style='text-align: center; color: grey; padding: 20px 0;'>이미지 없음</p>", unsafe_allow_html=True)
                        
                        st.markdown(f"##### [{str(news_row.title)}]({str(news_row.url)})")
                        
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"등록: {str(news_row.added_date)}")
                        with col2:
                            if st.button("삭제", key=f"del_{news_row.id}", type="secondary", use_container_width=True):
                                try:
                                    # gspread는 행 번호로 삭제하므로, id 값으로 해당 셀을 찾아 행 번호를 알아내야 함
                                    cell = worksheet.find(news_row.id)
                                    if cell:
                                        worksheet.delete_rows(cell.row)
                                        st.success("뉴스를 삭제했습니다.")
                                        st.rerun()
                                    else:
                                        st.error("삭제할 뉴스를 시트에서 찾지 못했습니다.")
                                except gspread.exceptions.CellNotFound:
                                    st.error("삭제할 뉴스를 찾지 못했습니다. 이미 삭제되었을 수 있습니다.")
                                except Exception as e:
                                    st.error(f"삭제 중 오류 발생: {e}")

else:
    st.warning("Google Sheets에 연결할 수 없어 앱을 실행할 수 없습니다. 설정을 확인해주세요.")