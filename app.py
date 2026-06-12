import streamlit as st
import folium
from streamlit_folium import st_folium

st.title("folium 지도 테스트")
st.success("folium, streamlit-folium 정상 설치")

# 서울시청 중심 지도
m = folium.Map(
    location=[37.5665, 126.9780],
    zoom_start=11,
    tiles="cartodbpositron"
)

folium.Marker(
    [37.5665, 126.9780],
    popup="서울시청",
    tooltip="서울시청"
).add_to(m)

st_folium(m, width=700, height=500)