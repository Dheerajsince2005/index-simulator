%%writefile app.py

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql+psycopg2://postgres.bcjeavbglnibwprviiej:Dheeraj20053872@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"

@st.cache_data
def load_data():
    engine = create_engine(DB_URL)
    df = pd.read_sql("SELECT * FROM index_constituents", engine)
    return df

df = load_data()

st.title("Equity Index Reconstitution Simulator")
st.caption("NSE Top 20 stocks across 4 index methodologies — 2025")

# ── Filters ──
col1, col2 = st.columns(2)
methodology = col1.selectbox("Index Methodology", df["methodology"].unique())
quarter     = col2.selectbox("Quarter", sorted(df["rebal_date"].unique(), reverse=True))

filtered = df[(df["methodology"] == methodology) & (df["rebal_date"] == quarter)]

# ── Section 1: Constituents ──
st.subheader("Index Constituents")
st.dataframe(
    filtered[["company","sector","weight","market_cap_cr"]].reset_index(drop=True),
    use_container_width=True
)

# ── Section 2: Sector Allocation ──
st.subheader("Sector Allocation")
sector_weights = filtered.groupby("sector")["weight"].sum().reset_index()
st.bar_chart(sector_weights.set_index("sector"))

# ── Section 3: Methodology Comparison ──
st.subheader("Methodology Comparison — Same Quarter")
latest = df[df["rebal_date"] == quarter]
comparison = latest.groupby(["methodology","sector"])["weight"].sum().unstack(fill_value=0)
st.dataframe(comparison, use_container_width=True)

# ── Section 4: Turnover ──
st.subheader("Constituent Turnover Across Quarters")
turnover_data = []
for method in df["methodology"].unique():
    method_df = df[df["methodology"] == method].sort_values("rebal_date")
    quarters = sorted(method_df["rebal_date"].unique())
    for i in range(1, len(quarters)):
        prev = set(method_df[method_df["rebal_date"] == quarters[i-1]]["ticker"])
        curr = set(method_df[method_df["rebal_date"] == quarters[i]]["ticker"])
        turnover_data.append({
            "methodology": method,
            "quarter": quarters[i],
            "additions": len(curr - prev),
            "deletions": len(prev - curr)
        })
turnover_df = pd.DataFrame(turnover_data)
if not turnover_df.empty:
    st.dataframe(turnover_df, use_container_width=True)