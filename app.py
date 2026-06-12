import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="온열질환 CSV 테스트", layout="wide")

st.title("온열질환 CSV 파일 테스트")

FILE_PATH = "heat_illness.csv"

st.write("현재 폴더 파일 목록")
st.write(os.listdir("."))

if not os.path.exists(FILE_PATH):
    st.error("heat_illness.csv 파일이 없습니다. app.py와 같은 폴더에 넣어주세요.")
    st.stop()

st.success("heat_illness.csv 파일 찾음")

df = pd.read_csv(FILE_PATH)

st.subheader("데이터 미리보기")
st.dataframe(df.head(), use_container_width=True)

st.subheader("컬럼 목록")
st.write(df.columns.tolist())

st.subheader("행 개수")
st.write(len(df))

if "occur_date" in df.columns:
    df["occur_date"] = pd.to_datetime(df["occur_date"], errors="coerce")
    df["year"] = df["occur_date"].dt.year

    yearly = df.groupby("year").size().reset_index(name="count")
    st.subheader("연도별 온열질환 발생 건수")
    st.line_chart(yearly.set_index("year"))

if "age" in df.columns:
    df["age"] = pd.to_numeric(df["age"], errors="coerce")

    def age_group(age):
        if pd.isna(age):
            return "미상"
        elif age < 20:
            return "0~19세"
        elif age < 40:
            return "20~39세"
        elif age < 65:
            return "40~64세"
        elif age < 80:
            return "65~79세"
        else:
            return "80세 이상"

    df["age_group"] = df["age"].apply(age_group)

    age_counts = df["age_group"].value_counts().reindex(
        ["0~19세", "20~39세", "40~64세", "65~79세", "80세 이상", "미상"]
    ).dropna()

    st.subheader("연령대별 온열질환 발생 건수")
    st.bar_chart(age_counts)

st.success("온열질환 CSV 테스트 완료")
