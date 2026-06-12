import os
import json
import sqlite3
from copy import deepcopy

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium


st.set_page_config(
    page_title="서울시 독거노인 폭염 취약지역 분석",
    layout="wide"
)

DB_PATH = "final.db"
DISTRICT_GEOJSON_PATH = "seoul_district_boundary_simplified.geojson"

HEAT_FILES = [
    "heat_illness.csv",
    "heat_illness.xlsx"
]

GEOJSON_DISTRICT_COL = "district"


def fmt_int(x):
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return "-"


def fmt_float(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "-"


def fmt_percent(x):
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


@st.cache_data
def load_heat_data():
    for path in HEAT_FILES:
        if os.path.exists(path):
            if path.endswith(".csv"):
                try:
                    return pd.read_csv(path, encoding="utf-8-sig"), path
                except UnicodeDecodeError:
                    return pd.read_csv(path, encoding="cp949"), path
            else:
                return pd.read_excel(path), path
    return None, None


def add_metrics_to_geojson(geojson_data, df, value_cols):
    geo = deepcopy(geojson_data)
    lookup = df.set_index("district")[value_cols].to_dict("index")

    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        district = props.get(GEOJSON_DISTRICT_COL)

        if district in lookup:
            for col, val in lookup[district].items():
                if pd.isna(val):
                    props[col] = None
                elif isinstance(val, (int, float, str, bool)):
                    props[col] = val
                else:
                    props[col] = str(val)

        feature["properties"] = props

    return geo


def draw_district_map(df, value_col, legend_name):
    geojson_data = load_geojson(DISTRICT_GEOJSON_PATH)

    if geojson_data is None:
        st.warning("자치구 GeoJSON 파일을 찾지 못했습니다. app.py와 같은 위치에 seoul_district_boundary_simplified.geojson을 넣어주세요.")
        return

    value_cols = [
        value_col,
        "objective_priority_score",
        "objective_priority_type",
        "elderly_total",
        "shelter_count",
        "total_capacity",
        "capacity_rate",
        "shelters_per_1000"
    ]

    value_cols = [c for c in value_cols if c in df.columns]
    map_df = df[["district"] + value_cols].copy()

    enriched = add_metrics_to_geojson(geojson_data, map_df, value_cols)

    m = folium.Map(
        location=[37.5665, 126.9780],
        zoom_start=10,
        tiles="cartodbpositron"
    )

    folium.Choropleth(
        geo_data=enriched,
        data=map_df,
        columns=["district", value_col],
        key_on=f"feature.properties.{GEOJSON_DISTRICT_COL}",
        fill_color="YlOrRd",
        fill_opacity=0.75,
        line_opacity=0.5,
        legend_name=legend_name
    ).add_to(m)

    tooltip_fields = [
        GEOJSON_DISTRICT_COL,
        "objective_priority_type",
        "objective_priority_score",
        "elderly_total",
        "shelter_count",
        "capacity_rate",
        "shelters_per_1000"
    ]

    tooltip_aliases = [
        "자치구:",
        "우선유형:",
        "우선점수:",
        "독거노인 수:",
        "쉼터 수:",
        "수용률:",
        "1,000명당 쉼터 수:"
    ]

    tooltip_fields = [f for f in tooltip_fields if f == GEOJSON_DISTRICT_COL or f in value_cols]
    tooltip_aliases = tooltip_aliases[:len(tooltip_fields)]

    folium.GeoJson(
        enriched,
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


st.title("서울시 독거노인 폭염 취약지역 분석을 통한 무더위쉼터 개선 우선지역 도출")
st.caption("독거노인 수요와 무더위쉼터 공급은 일치하고 있는가?")

if not os.path.exists(DB_PATH):
    st.error("final.db 파일이 없습니다. app.py와 같은 위치에 final.db를 넣어주세요.")
    st.stop()

district_summary = read_sql("SELECT * FROM district_summary")
shelters = read_sql("SELECT * FROM shelters")


# ============================================================
# 1. 프로젝트 소개
# ============================================================

st.header("1. 프로젝트 소개")

st.markdown("""
본 대시보드는 서울시 자치구별 **독거노인 수요**와 **무더위쉼터 공급 수준**을 비교해  
폭염 대응 인프라가 부족한 지역을 찾는 것을 목표로 합니다.

핵심 질문은 다음과 같습니다.

1. 독거노인이 많이 거주하는 자치구는 어디인가?  
2. 무더위쉼터 공급이 독거노인 수요에 비해 충분한가?  
3. 쉼터 추가 배치나 수용인원 확대가 필요한 우선지역은 어디인가?
""")

st.divider()


# ============================================================
# 2. 온열질환 발생 데이터
# ============================================================

st.header("2. 폭염은 실제 건강 피해로 이어지는가?")

heat_df, heat_path = load_heat_data()

if heat_df is None:
    st.warning("heat_illness.csv 또는 heat_illness.xlsx 파일이 없어 온열질환 시각화를 건너뜁니다.")
else:
    st.caption(f"사용 파일: {heat_path}")

    if "occur_date" in heat_df.columns:
        heat_df["occur_date"] = pd.to_datetime(heat_df["occur_date"], errors="coerce")
        heat_df["year"] = heat_df["occur_date"].dt.year

        yearly = heat_df.dropna(subset=["year"]).groupby("year").size().reset_index(name="발생 건수")
        yearly["year"] = yearly["year"].astype(int).astype(str)

        st.subheader("연도별 온열질환 발생 추이")
        st.line_chart(yearly.set_index("year"))

    if "age" in heat_df.columns:
        heat_df["age"] = pd.to_numeric(heat_df["age"], errors="coerce")

        def age_group(age):
            if pd.isna(age):
                return "미상"
            if age < 20:
                return "0~19세"
            if age < 40:
                return "20~39세"
            if age < 65:
                return "40~64세"
            if age < 80:
                return "65~79세"
            return "80세 이상"

        heat_df["age_group"] = heat_df["age"].apply(age_group)

        order = ["0~19세", "20~39세", "40~64세", "65~79세", "80세 이상", "미상"]
        age_counts = heat_df["age_group"].value_counts().reindex(order).dropna()

        st.subheader("연령대별 온열질환 발생 건수")
        st.bar_chart(age_counts)

        elderly_share = pd.Series({
            "65세 미만": (heat_df["age"] < 65).sum(),
            "65세 이상": (heat_df["age"] >= 65).sum()
        })

        st.subheader("65세 이상 온열질환 발생 비중")
        st.bar_chart(elderly_share)

    st.info("온열질환 데이터는 폭염이 단순한 날씨 문제가 아니라 실제 건강 피해로 이어진다는 점과, 고령층이 중요한 폭염 취약계층이라는 점을 보여주는 도입부 자료입니다.")

st.divider()


# ============================================================
# 3. 분석 질문과 데이터 구성
# ============================================================

st.header("3. 분석 질문과 데이터 구성")

st.markdown("""
사용 데이터는 다음과 같습니다.

- **서울시 독거노인 현황**: 자치구별 독거노인 수, 80세 이상 독거노인 수  
- **서울시 무더위쉼터 현황**: 쉼터 수, 수용가능인원, 시설 위치  
- **센서스 경계 자료**: 자치구 지도 시각화용 GeoJSON  
- **온열질환 발생 데이터**: 폭염 피해와 고령층 위험성 설명용 배경 자료  

SQLite에서는 `GROUP BY`, `JOIN`, `CASE WHEN`을 활용해 자치구별 분석 테이블을 구축했습니다.
""")

st.code("""
-- 자치구별 쉼터 공급 집계
SELECT district, COUNT(*) AS shelter_count, SUM(capacity) AS total_capacity
FROM shelters
GROUP BY district;

-- 독거노인 수요 데이터와 쉼터 공급 데이터 결합
SELECT *
FROM elderly_district e
JOIN shelter_district s
ON e.district = s.district;

-- 개선 유형 분류
CASE WHEN ... THEN '개선 우선지역'
""", language="sql")

st.divider()


# ============================================================
# 4. 객관 기준 계산
# ============================================================

st.header("4. 개선 우선지역을 어떻게 정했는가?")

df = district_summary.copy()

numeric_cols = [
    "elderly_total",
    "elderly_80_plus_rate",
    "vulnerable_elderly_rate",
    "shelter_count",
    "total_capacity",
    "shelters_per_1000",
    "elderly_per_shelter",
    "capacity_rate"
]

for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

elderly_cut = df["elderly_total"].quantile(0.6)
shelter_cut = df["shelters_per_1000"].quantile(0.4)
capacity_cut = df["capacity_rate"].quantile(0.4)
old_cut = df["elderly_80_plus_rate"].quantile(0.6)

df["high_demand"] = df["elderly_total"] >= elderly_cut
df["low_shelter_access"] = df["shelters_per_1000"] <= shelter_cut
df["low_capacity"] = df["capacity_rate"] <= capacity_cut
df["high_old_rate"] = df["elderly_80_plus_rate"] >= old_cut

df["objective_priority_score"] = (
    df["high_demand"].astype(int) * 3
    + df["low_shelter_access"].astype(int) * 3
    + df["low_capacity"].astype(int) * 3
    + df["high_old_rate"].astype(int) * 1
)


def classify_region(row):
    if row["high_demand"] and row["low_shelter_access"] and row["low_capacity"]:
        return "개선 우선지역"
    elif row["high_demand"] and row["low_capacity"]:
        return "수용능력 부족지역"
    elif row["high_demand"] and row["low_shelter_access"]:
        return "쉼터 접근성 부족지역"
    elif row["high_old_rate"] and row["low_capacity"]:
        return "고령 취약성 주의지역"
    else:
        return "상대적 안정지역"


df["objective_priority_type"] = df.apply(classify_region, axis=1)

criteria_df = pd.DataFrame({
    "기준": [
        "독거노인 수 상위 40%",
        "1,000명당 쉼터 수 하위 40%",
        "쉼터 수용률 하위 40%",
        "80세 이상 비율 상위 40%"
    ],
    "기준값": [
        f"{elderly_cut:,.2f}명 이상",
        f"{shelter_cut:,.2f}개 이하",
        f"{capacity_cut:,.2f}% 이하",
        f"{old_cut:,.2f}% 이상"
    ],
    "의미": [
        "수요 높음",
        "접근성 부족",
        "수용능력 부족",
        "고령 취약성 높음"
    ]
})

st.dataframe(criteria_df, use_container_width=True)

criteria_count = pd.Series({
    "수요 높음": df["high_demand"].sum(),
    "접근성 부족": df["low_shelter_access"].sum(),
    "수용능력 부족": df["low_capacity"].sum(),
    "고령 취약성 높음": df["high_old_rate"].sum()
})

st.subheader("기준별 해당 자치구 수")
st.bar_chart(criteria_count)

st.info("쉼터 개수만으로 부족 여부를 판단하지 않고, 수요·접근성·수용능력·고령 취약성 4개 기준을 종합했습니다.")

st.divider()


# ============================================================
# 5. 핵심 지표 카드
# ============================================================

st.header("5. 서울시 전체 핵심 지표")

c1, c2, c3 = st.columns(3)
c1.metric("전체 독거노인 수", fmt_int(df["elderly_total"].sum()))
c2.metric("80세 이상 독거노인 수", fmt_int(df["elderly_80_plus"].sum()))
c3.metric("전체 무더위쉼터 수", fmt_int(df["shelter_count"].sum()))

c4, c5, c6 = st.columns(3)
c4.metric("총 수용가능인원", fmt_int(df["total_capacity"].sum()))
c5.metric("평균 수용률", fmt_percent(df["capacity_rate"].mean()))
c6.metric("개선 우선 검토지역 수", fmt_int((df["objective_priority_score"] >= 6).sum()))

st.divider()


# ============================================================
# 6. 수요-공급 버블 산점도
# ============================================================

st.header("6. 독거노인 수요와 쉼터 수용능력은 일치하는가?")

bubble_df = df[["district", "elderly_total", "total_capacity", "shelter_count"]].copy()

st.scatter_chart(
    bubble_df,
    x="elderly_total",
    y="total_capacity",
    size="shelter_count"
)

st.info("X축은 독거노인 수, Y축은 무더위쉼터 총 수용가능인원, 점 크기는 쉼터 수입니다. 오른쪽 아래에 가까운 지역은 독거노인 수요는 높지만 수용가능인원이 낮은 개선 검토 지역입니다.")

st.divider()


# ============================================================
# 7. 객관 기준선 산점도
# ============================================================

st.header("7. 개선 우선지역 판단 기준선")

line_df = df[["district", "elderly_total", "capacity_rate"]].copy()

st.scatter_chart(
    line_df,
    x="elderly_total",
    y="capacity_rate"
)

st.info(f"독거노인 수 기준선은 {fmt_int(elderly_cut)}명 이상, 수용률 기준선은 {fmt_percent(capacity_cut)} 이하입니다. 오른쪽 아래 영역은 수요는 높지만 수용능력이 부족한 개선 우선 검토 영역입니다.")

st.divider()


# ============================================================
# 8. 자치구별 공급 진단 지도
# ============================================================

st.header("8. 자치구별 쉼터 공급 진단 지도")

map_metric = st.selectbox(
    "지도에서 볼 지표를 선택하세요.",
    ["shelter_count", "capacity_rate", "shelters_per_1000"],
    format_func=lambda x: {
        "shelter_count": "무더위쉼터 수",
        "capacity_rate": "쉼터 수용률",
        "shelters_per_1000": "독거노인 1,000명당 쉼터 수"
    }[x]
)

legend = {
    "shelter_count": "무더위쉼터 수",
    "capacity_rate": "쉼터 수용률",
    "shelters_per_1000": "독거노인 1,000명당 쉼터 수"
}[map_metric]

draw_district_map(df, map_metric, legend)

st.divider()


# ============================================================
# 9. TOP 5
# ============================================================

st.header("9. 최종 개선 우선지역 TOP 5")

top5 = df.sort_values(
    ["objective_priority_score", "elderly_total", "capacity_rate"],
    ascending=[False, False, True]
).head(5)

top5_table = top5[[
    "district",
    "elderly_total",
    "shelter_count",
    "total_capacity",
    "shelters_per_1000",
    "capacity_rate",
    "elderly_80_plus_rate",
    "objective_priority_type",
    "objective_priority_score"
]].copy()

st.dataframe(top5_table, use_container_width=True)

st.subheader("TOP 5 우선순위 점수")
score_chart = top5.set_index("district")[["objective_priority_score"]]
st.bar_chart(score_chart)

st.subheader("TOP 5 지역은 어떤 기준에서 취약한가?")

cause_chart = top5.set_index("district")[[
    "high_demand",
    "low_shelter_access",
    "low_capacity",
    "high_old_rate"
]].astype(int)

cause_chart = cause_chart.rename(columns={
    "high_demand": "수요 높음",
    "low_shelter_access": "접근성 부족",
    "low_capacity": "수용능력 부족",
    "high_old_rate": "고령 취약성 높음"
})

st.bar_chart(cause_chart)

for _, row in top5.iterrows():
    reasons = []
    if row["high_demand"]:
        reasons.append("수요 높음")
    if row["low_shelter_access"]:
        reasons.append("접근성 부족")
    if row["low_capacity"]:
        reasons.append("수용능력 부족")
    if row["high_old_rate"]:
        reasons.append("고령 취약성 높음")

    st.markdown(f"**{row['district']}**: {', '.join(reasons)} → {row['objective_priority_type']}")

st.divider()


# ============================================================
# 10. 무더위쉼터 위치 지도
# ============================================================

st.header("10. 무더위쉼터 위치 지도")

show_shelter_map = st.checkbox("무더위쉼터 위치 지도 보기", value=False)

if show_shelter_map:
    selected = st.selectbox("자치구 선택", ["전체"] + sorted(shelters["district"].dropna().unique().tolist()))

    shelter_map_df = shelters.dropna(subset=["latitude", "longitude"]).copy()

    if selected != "전체":
        shelter_map_df = shelter_map_df[shelter_map_df["district"] == selected]

    if len(shelter_map_df) > 800:
        st.warning("쉼터가 많아 상위 800개만 표시합니다. 자치구를 선택하면 더 안정적으로 볼 수 있습니다.")
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
    st.warning("쉼터 위치 지도는 무거울 수 있어 선택 시에만 불러옵니다.")

st.divider()


# ============================================================
# 11. 개선 방안
# ============================================================

st.header("11. 개선 방안: 취약 기준에 따른 맞춤 대응")

policy_df = pd.DataFrame({
    "유형": [
        "접근성 부족 포함 지역",
        "수용능력 부족 포함 지역",
        "고령 취약성 높은 지역"
    ],
    "판단 기준": [
        "독거노인 수 대비 1,000명당 쉼터 수 부족",
        "독거노인 수 대비 총 수용가능인원 부족",
        "80세 이상 독거노인 비율 높음"
    ],
    "개선 방향": [
        "신규 무더위쉼터 지정, 공공시설·주민센터·복지관 활용, 생활권 내 분산 배치",
        "기존 쉼터 수용인원 확대, 경로당·복지관 운영 강화, 폭염특보 시 운영시간·수용공간 보완",
        "폭염특보 시 전화·방문 안내, 고령 독거노인 이동 지원 검토, 복지관·경로당 연계 보호체계 강화"
    ]
})

st.dataframe(policy_df, use_container_width=True)

st.success("핵심: 무더위쉼터 개선은 단순 증설이 아니라, 취약 기준별 맞춤 대응이 필요합니다.")

st.divider()


# ============================================================
# 12. 최종 결론 지도
# ============================================================

st.header("12. 최종 결론: 서울시 자치구별 개선 우선순위 지도")

draw_district_map(df, "objective_priority_score", "최종 개선 우선순위 점수")

st.info("색이 진한 자치구일수록 수요, 접근성, 수용능력, 고령 취약성을 종합했을 때 개선 우선순위가 높은 지역입니다.")
