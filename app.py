import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="산점도 TOP5 테스트", layout="wide")

st.title("수요-공급 불균형 산점도 + 개선 우선지역 TOP5 테스트")

DB_PATH = "final.db"

conn = sqlite3.connect(DB_PATH)

df = pd.read_sql_query("""
SELECT
    district,
    elderly_total,
    shelter_count,
    total_capacity,
    shelters_per_1000,
    elderly_per_shelter,
    capacity_rate,
    elderly_80_plus_rate,
    vulnerable_elderly_rate,
    priority_type,
    priority_score
FROM district_priority
""", conn)

conn.close()

st.success("DB 데이터 불러오기 성공")

st.subheader("1. 수요-공급 불균형 산점도")

scatter_df = df.set_index("district")[["elderly_total", "capacity_rate"]]

st.scatter_chart(scatter_df)

st.caption(
    "x축은 독거노인 수, y축은 쉼터 수용률입니다. "
    "오른쪽 아래에 가까운 지역은 독거노인은 많지만 수용률이 낮아 우선 점검이 필요한 지역입니다."
)

st.divider()

st.subheader("2. 개선 우선지역 TOP 5")

top5 = df.sort_values(
    by=["priority_score", "shelters_per_1000", "capacity_rate", "elderly_total"],
    ascending=[False, True, True, False]
).head(5)

st.dataframe(top5, use_container_width=True)

st.subheader("3. TOP5 우선순위 점수")

score_df = top5.set_index("district")[["priority_score"]]
st.bar_chart(score_df)

st.caption(
    "priority_score가 높을수록 독거노인 규모, 수용률 부족, 쉼터 공급밀도 부족 등 여러 취약 요인이 동시에 나타난 지역입니다."
)
