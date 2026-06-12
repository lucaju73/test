import streamlit as st
import sqlite3
import pandas as pd
import os

st.title("DB 연결 테스트")

DB_PATH = "final.db"

st.write("현재 폴더 파일 목록")
st.write(os.listdir("."))

if not os.path.exists(DB_PATH):
    st.error("final.db 파일이 없습니다.")
    st.stop()

st.success("final.db 파일을 찾았습니다.")

conn = sqlite3.connect(DB_PATH)

tables = pd.read_sql_query(
    "SELECT name FROM sqlite_master WHERE type='table';",
    conn
)

st.subheader("DB 테이블 목록")
st.dataframe(tables)

try:
    df = pd.read_sql_query(
        "SELECT * FROM district_priority LIMIT 5;",
        conn
    )
    st.subheader("district_priority 미리보기")
    st.dataframe(df)
    st.success("DB 읽기 성공")
except Exception as e:
    st.error("DB 읽기 실패")
    st.exception(e)

conn.close()
