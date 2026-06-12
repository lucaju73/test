import os
import json
import sqlite3
from copy import deepcopy

import pandas as pd
import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium


# ============================================================
# 기본 설정
# ============================================================

st.set_page_config(
    page_title="서울시 독거노인 폭염 취약지역 분석",
    layout="wide"
)

DB_PATH = "final.db"
HEAT_FILE_CANDIDATES = [
    "heat_illness.csv",
    "heat_illness.xlsx",
    "data/heat_illness.csv",
    "data/heat_illness.xlsx",
]

DISTRICT_GEOJSON_PATH = "seoul_district_boundary_simplified.geojson"
DONG_GEOJSON_PATH = "seoul_adm_dong_simplified.geojson"

GEOJSON_DISTRICT_COL = "district"
GEOJSON_DONG_DISTRICT_COL = "district"
GEOJSON_DONG_COL = "ADM_NM"


# ============================================================
# 공통 함수
# ============================================================

def format_int(x):
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return "-"


def format_float(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "-"


def format_percent(x):
    try:
        return f"{float(x):.2f}%"
    except Exception:
        return "-"


@st.cache_data
def read_sql(query):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data
def load_geojson(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_heat_file():
    for path in HEAT_FILE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


@st.cache_data
def load_heat_data():
    path = find_heat_file()
    if path is None:
        return None, None

    try:
        if path.endswith(".csv"):
            try:
                df = pd.read_csv(path, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding="cp949")
        else:
            df = pd.read_excel(path)
        return df, path
    except Exception:
        return None, path


def add_metrics_to_geojson(geojson_data, df, geo_key="district", df_key="district"):
    geo = deepcopy(geojson_data)
    lookup = df.set_index(df_key).to_dict("index")

    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        key = props.get(geo_key)

        if key in lookup:
            for col, value in lookup[key].items():
                if pd.isna(value):
                    props[col] = None
                elif isinstance(value, (int, float, str)):
                    props[col] = value
                else:
                    props[col] = str(value)

        feature["properties"] = props

    return geo


def make_choropleth(df, value_col, legend_name, tooltip_cols=None):
    geojson_data = load_geojson(DISTRICT_GEOJSON_PATH)

    if geojson_data is None:
        st.warning("자치구 경계 GeoJSON 파일이 없어 지도를 표시할 수 없습니다.")
        return

    needed_cols = ["district", value_col]
    extra_cols = tooltip_cols or []
    map_df = df[list(dict.fromkeys(needed_cols + extra_cols))].copy()

    enriched_geojson = add_metrics_to_geojson(
        geojson_data,
        map_df,
        geo_key=GEOJSON_DISTRICT_COL,
        df_key="district"
    )

    m = folium.Map(
        location=[37.5665, 126.9780],
        zoom_start=10,
        tiles="cartodbpositron"
    )

    folium.Choropleth(
        geo_data=enriched_geojson,
        data=map_df,
        columns=["district", value_col],
        key_on=f"feature.properties.{GEOJSON_DISTRICT_COL}",
        fill_color="OrRd",
        fill_opacity=0.75,
        line_opacity=0.4,
        legend_name=legend_name
    ).add_to(m)

    tooltip_fields = [GEOJSON_DISTRICT_COL] + extra_cols
    tooltip_aliases = ["자치구:"] + [f"{col}:" for col in extra_cols]

    folium.GeoJson(
        enriched_geojson,
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields,
            aliases=tooltip_aliases,
            localize=True
        ),
        style_function=lambda x: {
            "fillOpacity": 0,
            "color": "black",
            "weight": 0.8
        }
    ).add_to(m)

    st_folium(m, width=None, height=560)


# ============================================================
# 데이터 확인
# ============================================================

st.title("서울시 독거노인 폭염 취약지역 및 무더위쉼터 공급 분석")
st.caption("온열질환 피해와 독거노인 현황, 무더위쉼터 공급 수준을 결합해 폭염 대응 우선지역을 찾는 대시보드입니다.")

if not os.path.exists(DB_PATH):
    st.error("final.db 파일이 없습니다. app.py와 같은 폴더에 final.db를 넣어주세요.")
    st.stop()

district_summary = read_sql("SELECT * FROM district_summary")
district_priority = read_sql("SELECT * FROM district_priority")
shelters = read_sql("SELECT * FROM shelters")
elderly_dong = read_sql("SELECT * FROM elderly_dong")

top5 = district_priority.sort_values(
    by=["priority_score", "shelters_per_1000", "capacity_rate", "elderly_total"],
    ascending=[False, True, True, False]
).head(5)

districts = district_priority["district"].dropna().sort_values().tolist()


# ============================================================
# 사이드바
# ============================================================

st.sidebar.header("필터")

selected_district = st.sidebar.selectbox(
    "자치구 선택",
    ["전체"] + districts
)

map_metric = st.sidebar.selectbox(
    "공급 진단 지도 지표",
    [
        "쉼터 수",
        "쉼터 수용률",
        "독거노인 1,000명당 쉼터 수"
    ]
)

show_shelter_map = st.sidebar.checkbox("무더위쉼터 위치 지도 불러오기", value=False)
show_dong_map = st.sidebar.checkbox("행정동 심층 지도 불러오기", value=False)

dong_district = st.sidebar.selectbox(
    "행정동 심층 분석 자치구",
    top5["district"].tolist() if not top5.empty else districts
)


# ============================================================
# 1. 프로젝트 소개
# ============================================================

st.header("1. 프로젝트 소개")

st.markdown("""
이 대시보드는 **서울시 자치구별 독거노인 수요**와 **무더위쉼터 공급 수준**을 비교해  
폭염 대응 인프라가 부족한 지역을 찾는 것을 목표로 합니다.

핵심 질문은 다음과 같습니다.

1. 독거노인이 많이 거주하는 자치구는 어디인가?  
2. 무더위쉼터 공급이 독거노인 수요에 비해 부족한 지역은 어디인가?  
3. 쉼터 추가 배치나 수용인원 확대가 필요한 우선지역은 어디인가?
""")

st.divider()


# ============================================================
# 2. 온열질환 발생 데이터
# ============================================================

st.header("2. 온열질환 발생 데이터로 보는 폭염 피해")

heat_df, heat_path = load_heat_data()

if heat_df is None:
    st.warning("heat_illness.csv 또는 heat_illness.xlsx 파일이 없어 온열질환 도입부 시각화를 건너뜁니다.")
else:
    st.caption(f"사용 파일: {heat_path}")

    col_names = heat_df.columns.tolist()

    if "occur_date" in col_names:
        heat_df["occur_date"] = pd.to_datetime(heat_df["occur_date"], errors="coerce")
        heat_df["year"] = heat_df["occur_date"].dt.year

        yearly = heat_df.dropna(subset=["year"]).groupby("year").size().reset_index(name="발생 건수")
        yearly["year"] = yearly["year"].astype(int).astype(str)

        fig = px.line(
            yearly,
            x="year",
            y="발생 건수",
            markers=True,
            title="연도별 온열질환 발생 추이",
            labels={"year": "연도", "발생 건수": "발생 건수"}
        )
        st.plotly_chart(fig, use_container_width=True)

        st.info("온열질환 발생 추이는 폭염이 단순한 날씨 문제가 아니라 실제 건강 피해로 이어지고 있음을 보여주는 배경 자료입니다.")

    if "age" in col_names:
        heat_df["age"] = pd.to_numeric(heat_df["age"], errors="coerce")

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

        heat_df["age_group"] = heat_df["age"].apply(age_group)

        order = ["0~19세", "20~39세", "40~64세", "65~79세", "80세 이상", "미상"]
        age_counts = heat_df["age_group"].value_counts().reindex(order).dropna().reset_index()
        age_counts.columns = ["연령대", "발생 건수"]

        fig = px.bar(
            age_counts,
            x="연령대",
            y="발생 건수",
            title="연령대별 온열질환 발생 건수",
            labels={"연령대": "연령대", "발생 건수": "발생 건수"}
        )
        st.plotly_chart(fig, use_container_width=True)

        heat_df["elderly_group"] = heat_df["age"].apply(
            lambda x: "65세 이상" if pd.notna(x) and x >= 65 else "65세 미만"
        )

        elderly_share = heat_df["elderly_group"].value_counts().reset_index()
        elderly_share.columns = ["구분", "발생 건수"]

        fig = px.pie(
            elderly_share,
            names="구분",
            values="발생 건수",
            hole=0.45,
            title="65세 이상 온열질환 발생 비중"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.info("연령대별 발생 현황은 고령층이 폭염 피해에서 중요한 취약계층임을 보여주며, 독거노인을 분석 대상으로 설정하는 근거가 됩니다.")

st.divider()


# ============================================================
# 3. 핵심 지표 카드
# ============================================================

st.header("3. 서울시 전체 핵심 지표")

total_elderly = district_summary["elderly_total"].sum()
total_80 = district_summary["elderly_80_plus"].sum()
total_shelters = district_summary["shelter_count"].sum()
total_capacity = district_summary["total_capacity"].sum()
avg_capacity_rate = district_summary["capacity_rate"].mean()
priority_count = (district_priority["priority_type"] == "개선 우선지역").sum()

c1, c2, c3 = st.columns(3)
c1.metric("전체 독거노인 수", format_int(total_elderly), help="서울시 자치구별 독거노인 수를 합산한 값입니다.")
c2.metric("80세 이상 독거노인 수", format_int(total_80), help="폭염에 더 취약할 수 있는 고령 독거노인 규모입니다.")
c3.metric("전체 무더위쉼터 수", format_int(total_shelters), help="서울시 전체 무더위쉼터 개수입니다.")

c4, c5, c6 = st.columns(3)
c4.metric("총 수용가능인원", format_int(total_capacity), help="무더위쉼터가 수용 가능한 총 인원입니다.")
c5.metric("평균 수용률", format_percent(avg_capacity_rate), help="독거노인 수 대비 쉼터 수용가능인원의 평균 비율입니다.")
c6.metric("개선 우선지역 수", format_int(priority_count), help="priority_type이 개선 우선지역으로 분류된 자치구 수입니다.")

st.divider()


# ============================================================
# 4. 객관 기준
# ============================================================

st.header("4. 개선 유형을 나누는 객관 기준")

q = district_priority.copy()

thresholds = {
    "독거노인 수 상위 25%": q["elderly_total"].quantile(0.75),
    "수용률 하위 25%": q["capacity_rate"].quantile(0.25),
    "1,000명당 쉼터 수 하위 25%": q["shelters_per_1000"].quantile(0.25),
    "80세 이상 비율 상위 25%": q["elderly_80_plus_rate"].quantile(0.75),
    "쉼터 1개당 담당 독거노인 수 상위 25%": q["elderly_per_shelter"].quantile(0.75),
}

criteria_df = pd.DataFrame({
    "기준": list(thresholds.keys()),
    "기준값": list(thresholds.values())
})

st.dataframe(criteria_df, use_container_width=True)

criteria_count = pd.DataFrame({
    "취약 기준": [
        "수요 과밀",
        "수용능력 부족",
        "쉼터 공급밀도 부족",
        "고령 취약성 높음",
        "쉼터 부담 과다"
    ],
    "해당 자치구 수": [
        (q["elderly_total"] >= thresholds["독거노인 수 상위 25%"]).sum(),
        (q["capacity_rate"] <= thresholds["수용률 하위 25%"]).sum(),
        (q["shelters_per_1000"] <= thresholds["1,000명당 쉼터 수 하위 25%"]).sum(),
        (q["elderly_80_plus_rate"] >= thresholds["80세 이상 비율 상위 25%"]).sum(),
        (q["elderly_per_shelter"] >= thresholds["쉼터 1개당 담당 독거노인 수 상위 25%"]).sum(),
    ]
})

fig = px.bar(
    criteria_count,
    x="취약 기준",
    y="해당 자치구 수",
    title="객관 기준별 해당 자치구 수",
    text="해당 자치구 수"
)
st.plotly_chart(fig, use_container_width=True)

st.info("상위 25%, 하위 25% 기준을 활용하면 개선 우선유형을 보다 객관적으로 설명할 수 있습니다.")

st.divider()


# ============================================================
# 5. 선택형 공급 진단 지도
# ============================================================

st.header("5. 자치구별 무더위쉼터 공급 진단 지도")

metric_map = {
    "쉼터 수": ("shelter_count", "자치구별 무더위쉼터 수"),
    "쉼터 수용률": ("capacity_rate", "자치구별 쉼터 수용률"),
    "독거노인 1,000명당 쉼터 수": ("shelters_per_1000", "독거노인 1,000명당 쉼터 수")
}

metric_col, legend_name = metric_map[map_metric]

make_choropleth(
    district_summary,
    metric_col,
    legend_name,
    tooltip_cols=[
        "elderly_total",
        "shelter_count",
        "total_capacity",
        "capacity_rate",
        "shelters_per_1000"
    ]
)

st.info("쉼터 수, 수용률, 1,000명당 쉼터 수를 함께 보면 단순히 시설 수가 적은 지역과 실제 수용능력이 부족한 지역을 구분할 수 있습니다.")

st.divider()


# ============================================================
# 6. 수요-공급 불균형 산점도
# ============================================================

st.header("6. 수요-공급 불균형 산점도")

avg_elderly = district_priority["elderly_total"].mean()
avg_capacity = district_priority["capacity_rate"].mean()

fig = px.scatter(
    district_priority,
    x="elderly_total",
    y="capacity_rate",
    size="shelter_count",
    color="priority_type",
    hover_name="district",
    hover_data=[
        "shelters_per_1000",
        "elderly_per_shelter",
        "priority_score"
    ],
    title="독거노인 수요와 쉼터 수용능력의 불균형",
    labels={
        "elderly_total": "독거노인 수",
        "capacity_rate": "쉼터 수용률(%)",
        "shelter_count": "쉼터 수",
        "priority_type": "개선 유형"
    }
)

fig.add_vline(x=avg_elderly, line_dash="dash")
fig.add_hline(y=avg_capacity, line_dash="dash")

st.plotly_chart(fig, use_container_width=True)

st.info("오른쪽 아래에 위치한 지역은 독거노인 수는 많지만 수용률이 낮아 가장 우선적으로 점검해야 하는 지역입니다.")

st.divider()


# ============================================================
# 7. TOP 5 심층 진단
# ============================================================

st.header("7. 개선 우선지역 TOP 5 심층 진단")

top5_display = top5[[
    "district",
    "priority_type",
    "priority_score",
    "elderly_total",
    "elderly_80_plus_rate",
    "vulnerable_elderly_rate",
    "shelter_count",
    "total_capacity",
    "shelters_per_1000",
    "capacity_rate",
    "elderly_per_shelter"
]].copy()

st.dataframe(top5_display, use_container_width=True)

fig = px.bar(
    top5,
    x="priority_score",
    y="district",
    orientation="h",
    title="개선 우선지역 TOP 5 우선순위 점수",
    labels={"priority_score": "우선순위 점수", "district": "자치구"}
)
fig.update_yaxes(categoryorder="total ascending")
st.plotly_chart(fig, use_container_width=True)

cause_df = top5[["district"]].copy()
cause_df["수요 과밀"] = (top5["elderly_total"] >= thresholds["독거노인 수 상위 25%"]).astype(int)
cause_df["수용능력 부족"] = (top5["capacity_rate"] <= thresholds["수용률 하위 25%"]).astype(int)
cause_df["공급밀도 부족"] = (top5["shelters_per_1000"] <= thresholds["1,000명당 쉼터 수 하위 25%"]).astype(int)
cause_df["고령 취약성"] = (top5["elderly_80_plus_rate"] >= thresholds["80세 이상 비율 상위 25%"]).astype(int)
cause_df["쉼터 부담 과다"] = (top5["elderly_per_shelter"] >= thresholds["쉼터 1개당 담당 독거노인 수 상위 25%"]).astype(int)

heatmap_df = cause_df.set_index("district")

fig = px.imshow(
    heatmap_df,
    text_auto=True,
    aspect="auto",
    title="TOP 5 지역별 취약 원인 분해",
    labels=dict(x="취약 원인", y="자치구", color="해당 여부")
)
st.plotly_chart(fig, use_container_width=True)

for _, row in top5.iterrows():
    reasons = []
    if row["elderly_total"] >= thresholds["독거노인 수 상위 25%"]:
        reasons.append("독거노인 수요가 많음")
    if row["capacity_rate"] <= thresholds["수용률 하위 25%"]:
        reasons.append("쉼터 수용률이 낮음")
    if row["shelters_per_1000"] <= thresholds["1,000명당 쉼터 수 하위 25%"]:
        reasons.append("1,000명당 쉼터 수가 부족함")
    if row["elderly_80_plus_rate"] >= thresholds["80세 이상 비율 상위 25%"]:
        reasons.append("80세 이상 고령 비율이 높음")
    if row["elderly_per_shelter"] >= thresholds["쉼터 1개당 담당 독거노인 수 상위 25%"]:
        reasons.append("쉼터 1개당 담당 독거노인이 많음")

    st.markdown(f"**{row['district']}**: " + ", ".join(reasons))

st.divider()


# ============================================================
# 8. 무더위쉼터 위치 지도
# ============================================================

st.header("8. 무더위쉼터 위치 지도")

if show_shelter_map:
    shelter_map_df = shelters.dropna(subset=["latitude", "longitude"]).copy()

    if selected_district != "전체":
        shelter_map_df = shelter_map_df[shelter_map_df["district"] == selected_district]

    if len(shelter_map_df) > 800:
        st.warning("쉼터가 너무 많아 상위 800개만 표시합니다. 특정 자치구를 선택하면 더 안정적으로 볼 수 있습니다.")
        shelter_map_df = shelter_map_df.head(800)

    if shelter_map_df.empty:
        st.warning("표시할 쉼터 위치 데이터가 없습니다.")
    else:
        center_lat = shelter_map_df["latitude"].mean()
        center_lon = shelter_map_df["longitude"].mean()

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=11,
            tiles="cartodbpositron"
        )

        for _, row in shelter_map_df.iterrows():
            popup = f"""
            <b>{row.get('shelter_name', '')}</b><br>
            자치구: {row.get('district', '')}<br>
            추정 행정동: {row.get('dong_guess', '')}<br>
            시설유형: {row.get('facility_type1', '')} / {row.get('facility_type2', '')}<br>
            주소: {row.get('road_address', '')}<br>
            수용가능인원: {row.get('capacity', '')}<br>
            면적: {row.get('area', '')}
            """

            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=3,
                fill=True,
                fill_opacity=0.7,
                popup=folium.Popup(popup, max_width=300)
            ).add_to(m)

        st_folium(m, width=None, height=550)
else:
    st.warning("무더위쉼터 위치 지도는 무거울 수 있어 기본으로 불러오지 않습니다. 사이드바에서 체크하면 표시됩니다.")

st.divider()


# ============================================================
# 9. 행정동 심층 분석
# ============================================================

st.header("9. 개선 우선지역 내부 행정동 심층 분석")

dong_df = elderly_dong[elderly_dong["district"] == dong_district].copy()
dong_df = dong_df.sort_values("elderly_total", ascending=False)

st.subheader(f"{dong_district} 행정동별 독거노인 TOP 10")
st.dataframe(dong_df.head(10), use_container_width=True)

fig = px.bar(
    dong_df.head(10),
    x="elderly_total",
    y="dong",
    orientation="h",
    title=f"{dong_district} 행정동별 독거노인 TOP 10",
    labels={"elderly_total": "독거노인 수", "dong": "행정동"}
)
fig.update_yaxes(categoryorder="total ascending")
st.plotly_chart(fig, use_container_width=True)

if show_dong_map:
    dong_geojson = load_geojson(DONG_GEOJSON_PATH)

    if dong_geojson is None:
        st.warning("행정동 GeoJSON 파일이 없습니다.")
    else:
        filtered_features = []
        for feature in dong_geojson.get("features", []):
            props = feature.get("properties", {})
            if props.get(GEOJSON_DONG_DISTRICT_COL) == dong_district:
                filtered_features.append(feature)

        filtered_geojson = {
            "type": "FeatureCollection",
            "features": filtered_features
        }

        dong_lookup = dong_df.set_index("dong").to_dict("index")

        for feature in filtered_geojson["features"]:
            props = feature["properties"]
            dong_name = props.get(GEOJSON_DONG_COL)
            if dong_name in dong_lookup:
                props["elderly_total"] = dong_lookup[dong_name].get("elderly_total")
                props["elderly_80_plus"] = dong_lookup[dong_name].get("elderly_80_plus")
                props["elderly_80_plus_ratio"] = dong_lookup[dong_name].get("elderly_80_plus_ratio")

        m = folium.Map(
            location=[37.5665, 126.9780],
            zoom_start=12,
            tiles="cartodbpositron"
        )

        choropleth_data = dong_df.copy()
        choropleth_data["dong_key"] = choropleth_data["dong"]

        folium.Choropleth(
            geo_data=filtered_geojson,
            data=choropleth_data,
            columns=["dong_key", "elderly_total"],
            key_on=f"feature.properties.{GEOJSON_DONG_COL}",
            fill_color="YlOrRd",
            fill_opacity=0.75,
            line_opacity=0.4,
            legend_name="행정동별 독거노인 수"
        ).add_to(m)

        folium.GeoJson(
            filtered_geojson,
            tooltip=folium.GeoJsonTooltip(
                fields=[GEOJSON_DONG_COL, "elderly_total", "elderly_80_plus"],
                aliases=["행정동:", "독거노인 수:", "80세 이상:"],
                localize=True
            ),
            style_function=lambda x: {
                "fillOpacity": 0,
                "color": "black",
                "weight": 0.7
            }
        ).add_to(m)

        st_folium(m, width=None, height=550)
else:
    st.warning("행정동 지도는 무거울 수 있어 기본으로 불러오지 않습니다. 사이드바에서 체크하면 표시됩니다.")

st.divider()


# ============================================================
# 10. 정책 제안
# ============================================================

st.header("10. 결과 해석 및 정책 제안")

policy_df = pd.DataFrame({
    "유형": [
        "수용능력 부족형",
        "쉼터 수 부족형",
        "고령 취약성 주의형",
        "공간 분포 불균형형",
        "안내 강화 필요형"
    ],
    "판단 기준": [
        "capacity_rate 낮음",
        "shelters_per_1000 낮음",
        "elderly_80_plus_rate 높음",
        "쉼터 위치가 특정 지역에 집중",
        "쉼터는 있으나 이용 접근성이 낮을 가능성"
    ],
    "개선 방향": [
        "대형 공공시설 추가 지정, 기존 쉼터 수용인원 확대",
        "쉼터 추가 배치, 접근성 취약지역 중심 보강",
        "80세 이상 독거노인 대상 폭염 안내와 방문 점검 강화",
        "취약 행정동 중심 재배치 검토",
        "쉼터 위치 안내, 문자 알림, 주민센터 연계 홍보 강화"
    ]
})

st.dataframe(policy_df, use_container_width=True)

st.success("서울시 무더위쉼터 정책은 단순히 쉼터 수를 늘리는 방식보다 독거노인 밀집도, 수용가능인원, 쉼터 접근성을 함께 고려해 자치구별로 다르게 설계될 필요가 있습니다.")

st.divider()


# ============================================================
# 11. 최종 결론 지도
# ============================================================

st.header("11. 최종 결론: 서울시 자치구별 개선 우선순위 지도")

make_choropleth(
    district_priority,
    "priority_score",
    "개선 우선순위 점수",
    tooltip_cols=[
        "priority_type",
        "priority_score",
        "elderly_total",
        "shelter_count",
        "capacity_rate",
        "shelters_per_1000"
    ]
)

st.info("이 지도는 전체 분석 결과를 종합한 결론 지도입니다. 색이 진한 자치구일수록 독거노인 수요 대비 무더위쉼터 공급과 수용능력을 우선적으로 점검할 필요가 있습니다.")
