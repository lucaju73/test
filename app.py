import streamlit as st
import pandas as pd
import plotly.express as px

st.title("plotly 테스트")

df = pd.DataFrame({
    "x": [1,2,3],
    "y": [4,5,6]
})

fig = px.scatter(df, x="x", y="y")

st.plotly_chart(fig)