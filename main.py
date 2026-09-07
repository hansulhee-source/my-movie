# my-movieimport datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import pytz

# 페이지 기본 설정 (타이틀, 레이아웃)
st.set_page_config(
    page_title="어제 일별 박스오피스",
    page_icon="🎬",
    layout="wide"
)

# -----------------------------------------------------------------------------
# [캐싱 함수] KOBIS API 데이터 불러오기
# ttl=3600: 동일한 날짜 요청 시 1시간(3600초) 동안 API를 재호출하지 않고 저장된 결과를 사용합니다.
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_daily_box_office(api_key: str, target_date: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": target_date
    }
    
    try:
        # API 데이터 요청 (타임아웃 10초 설정)
        response = requests.get(url, params=params, timeout=10)
        
        # HTTP 응답 상태 코드가 200이 아닌 경우
        if response.status_code != 200:
            return None, f"서버 응답 오류 (HTTP 상태 코드: {response.status_code})"
        
        data = response.json()
        
        # 1. API 오류 발생 검사 (인증키 오류 등 - faultInfo 응답 처리)
        if "faultInfo" in data:
            error_msg = data["faultInfo"].get("message", "알 수 없는 오류가 발생했습니다.")
            return None, f"API 오류 발생: {error_msg}"
        
        # 2. 데이터 구조 확인 및 영화 목록 추출
        box_office_result = data.get("boxOfficeResult", {})
        daily_list = box_office_result.get("dailyBoxOfficeList", [])
        
        # 목록이 비어 있는 경우 처리
        if not daily_list:
            return None, "해당 날짜의 영화 목록이 비어 있습니다."
        
        return daily_list, None

    except requests.exceptions.RequestException as e:
        return None, f"네트워크 요청 중 오류가 발생했습니다: {str(e)}"
    except Exception as e:
        return None, f"데이터 처리 중 오류가 발생했습니다: {str(e)}"


# -----------------------------------------------------------------------------
# [메인 실행 로직]
# -----------------------------------------------------------------------------
def main():
    st.title("🎬 어제 일별 박스오피스")

    # 1. secrets에서 API 키 불러오기 확인
    if "KOBIS_KEY" not in st.secrets:
        st.error("🔑 API 키를 찾을 수 없습니다!")
        st.info(
            "Streamlit Cloud의 App Settings > Secrets에 아래 형식으로 인증키를 등록했는지 확인해 주세요:\n\n"
            "```toml\n"
            'KOBIS_KEY = "발급받은_인증키_입력"\n'
            "```"
        )
        return

    api_key = st.secrets["KOBIS_KEY"]

    # 2. 한국 표준시(KST) 기준 '어제' 날짜 계산 (YYYYMMDD 형식)
    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.datetime.now(kst)
    yesterday = now_kst - datetime.timedelta(days=1)
    target_dt_str = yesterday.strftime("%Y%m%d")
    formatted_date_display = yesterday.strftime("%Y년 %m월 %d일")

    st.caption(f"기준 날짜 (한국 시간 어제): **{formatted_date_display}**")

    # 3. API 데이터 호출
    with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
        daily_list, error_message = fetch_daily_box_office(api_key, target_dt_str)

    # 4. 에러 발생 시 한국어 안내 및 체크리스트 출력
    if error_message:
        st.error(f"🚨 데이터를 불러오지 못했습니다: {error_message}")
        st.warning(
            "**다음 항목을 확인해 주세요:**\n"
            "1. Secrets에 등록된 `KOBIS_KEY`가 올바른 발급 키인지 확인하세요.\n"
            "2. KOBIS 오픈 API 서비스가 정상 작동 중인지 확인하세요.\n"
            "3. 인터넷 연결 상태를 확인하고 잠시 후 다시 시도해 주세요."
        )
        return

    # 5. 데이터 프레임 변환 및 타입 정제
    df = pd.DataFrame(daily_list)

    # 문자열로 들어오는 숫자 데이터들을 정수(int) 타입으로 변환
    numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt", "rankInten"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # 순위 기준 재정렬
    df = df.sort_values(by="rank").reset_index(drop=True)

    # -------------------------------------------------------------------------
    # [시각화 1] 1위 영화 지표 카드 (Metric) 3장
    # -------------------------------------------------------------------------
    st.subheader("🥇 어제의 1위 영화")
    top_movie = df.iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="영화명",
            value=top_movie["movieNm"]
        )
    with col2:
        st.metric(
            label="일별 관객수",
            value=f"{top_movie['audiCnt']:,} 명"
        )
    with col3:
        st.metric(
            label="누적 관객수",
            value=f"{top_movie['audiAcc']:,} 명"
        )

    st.divider()

    # -------------------------------------------------------------------------
    # [시각화 2] 관객수 상위 5편 막대그래프
    # -------------------------------------------------------------------------
    st.subheader("📊 관객수 상위 5개 영화")
    top_5_df = df.head(5)

    # Plotly 막대그래프 생성
    fig = px.bar(
        top_5_df,
        x="movieNm",
        y="audiCnt",
        text="audiCnt",
        labels={"movieNm": "영화명", "audiCnt": "일별 관객수"},
        title="상위 5개 영화 일별 관객수 비교"
    )
    # 데이터 레이블 포맷팅 및 그래프 레이아웃 설정
    fig.update_traces(texttemplate="%{text:,}명", textposition="outside")
    fig.update_layout(yaxis=dict(title="관객수 (명)"))
    
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # -------------------------------------------------------------------------
    # [시각화 3] 박스오피스 전체 순위 표
    # -------------------------------------------------------------------------
    st.subheader("📋 전체 순위표")

    # 표시할 컬럼 정의 및 이름 변경
    display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
    display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

    # 천 단위 쉼표 포맷팅을 적용한 데이터프레임 출력
    st.dataframe(
        display_df.style.format({
            "순위": "{:}위",
            "관객수": "{:,}명",
            "누적관객": "{:,}명",
            "스크린수": "{:,}개"
        }),
        use_container_width=True,
        hide_index=True
    )


if __name__ == "__main__":
    main()
