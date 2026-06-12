import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="지도 테스트", layout="wide")

st.title("서울시 자치구 개선 우선순위 지도 테스트")

DB_PATH = "final.db"
GEOJSON_PATH = "data/seoul_district_boundary_simplified.geojson"

# -----------------------------
# DB 확인
# -----------------------------
if not os.path.exists(DB_PATH):
    st.error("final.db 파일이 없습니다.")
    st.stop()

if not os.path.exists(GEOJSON_PATH):
    st.error("GeoJSON 파일이 없습니다.")
    st.stop()

st.success("DB와 GeoJSON 파일 찾기 성공")

# -----------------------------
# DB 연결
# -----------------------------
conn = sqlite3.connect(DB_PATH)

query = """
SELECT
    district,
    priority_type,
    priority_score,
    elderly_total,
    shelter_count,
    capacity_rate,
    shelters_per_1000
FROM district_priority
"""

df = pd.read_sql_query(query, conn)
conn.close()

st.subheader("district_priority 미리보기")
st.dataframe(df.head())

# -----------------------------
# GeoJSON 읽기
# -----------------------------
with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

st.success("GeoJSON 읽기 성공")

# -----------------------------
# 서울 중심 지도
# -----------------------------
m = folium.Map(
    location=[37.5665, 126.9780],
    zoom_start=10,
    tiles="cartodbpositron"
)

# -----------------------------
# Choropleth 지도
# -----------------------------
folium.Choropleth(
    geo_data=geojson_data,
    data=df,
    columns=["district", "priority_score"],
    key_on="feature.properties.district",
    fill_color="OrRd",
    fill_opacity=0.7,
    line_opacity=0.4,
    legend_name="개선 우선순위 점수"
).add_to(m)

# -----------------------------
# Tooltip 추가
# -----------------------------
tooltip = folium.GeoJsonTooltip(
    fields=["district"],
    aliases=["자치구:"],
    localize=True
)

folium.GeoJson(
    geojson_data,
    tooltip=tooltip,
    style_function=lambda x: {
        "fillOpacity": 0,
        "color": "black",
        "weight": 1
    }
).add_to(m)

# -----------------------------
# 지도 출력
# -----------------------------
st.subheader("서울시 자치구별 개선 우선순위 지도")

st_folium(m, width=1000, height=600)

st.success("지도 렌더링 성공")
