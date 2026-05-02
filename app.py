import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

st.set_page_config(page_title="Index Simulator", layout="wide")

DB_URL = st.secrets["DATABASE_URL"]

@st.cache_data
def load_constituents():
    engine = create_engine(DB_URL)
    return pd.read_sql("SELECT * FROM index_constituents", engine)

@st.cache_data
def load_returns():
    engine = create_engine(DB_URL)
    return pd.read_sql("SELECT * FROM index_returns", engine)

@st.cache_data
def load_factors():
    engine = create_engine(DB_URL)
    return pd.read_sql("SELECT * FROM stock_factors", engine)

df          = load_constituents()
returns_df  = load_returns()
factors_df  = load_factors()

METHODOLOGIES = sorted(df["methodology"].unique())
QUARTERS      = sorted(df["rebal_date"].unique(), reverse=True)

METHOD_DESC = {
    "Market Cap Weighted":  "Larger companies get higher weight. Mirrors how Nifty 50 works.",
    "Sector Balanced":      "Each sector gets equal representation. Prevents banking/IT from dominating.",
    "Momentum":             "Picks top performers from last 6 months. Trend-following strategy.",
    "Low Volatility":       "Picks the most stable stocks. Defensive, lower-risk strategy.",
    "Quality Momentum":     "Combines Sharpe ratio and 6M returns. High quality + rising stocks.",
    "Low Beta":             "Stocks least sensitive to market moves. Ideal in bear markets.",
    "Mean Reversion":       "Picks oversold stocks (low RSI). Contrarian bet on recovery.",
}

# ── Sidebar ──
st.sidebar.title("Index Simulator")
page = st.sidebar.radio("Navigate", [
    "Home",
    "Constituents",
    "Performance",
    "Factor Explorer",
    "Build Your Index"
])

# ════════════════════════════════
# PAGE 1 — HOME
# ════════════════════════════════
if page == "Home":
    st.title("Equity Index Reconstitution Simulator")
    st.markdown("**NSE Top 20 stocks · 7 methodologies · 2025 quarterly rebalancing**")
    st.markdown("---")

    st.subheader("What is this?")
    st.markdown("""
    This tool simulates how a financial index provider like **Morningstar** constructs and 
    reconstitutes equity indexes. Every quarter, stocks are evaluated against a set of rules 
    and the index membership is updated — this is called **reconstitution**.
    
    We built 7 indexes on 20 NSE stocks, each using a different methodology to select and 
    weight constituents. You can explore who's in each index, compare their performance, 
    and even build your own.
    """)

    st.subheader("7 Index Methodologies")
    cols = st.columns(2)
    for i, (method, desc) in enumerate(METHOD_DESC.items()):
        cols[i % 2].info(f"**{method}**\n\n{desc}")

    st.subheader("Database Stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Indexes",       df["methodology"].nunique())
    c2.metric("Quarterly Snapshots", df["rebal_date"].nunique())
    c3.metric("Stocks Tracked",      df["ticker"].nunique())
    c4.metric("Total Rows",          len(df))

# ════════════════════════════════
# PAGE 2 — CONSTITUENTS
# ════════════════════════════════
elif page == "Constituents":
    st.title("Index Constituents")
    st.markdown("See which stocks are in each index at each quarterly rebalancing date.")

    col1, col2 = st.columns(2)
    methodology = col1.selectbox("Index Methodology", METHODOLOGIES)
    quarter     = col2.selectbox("Quarter", QUARTERS)

    filtered = df[(df["methodology"] == methodology) & (df["rebal_date"] == quarter)]

    st.markdown(f"**About this index:** {METHOD_DESC.get(methodology, '')}")
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    c1.metric("Constituents",    len(filtered))
    c2.metric("Sectors covered", filtered["sector"].nunique())
    c3.metric("Top sector",      filtered.groupby("sector")["weight"].sum().idxmax())

    st.subheader("Constituent List")
    st.dataframe(
        filtered[["company","sector","weight","market_cap_cr"]]
        .sort_values("weight", ascending=False)
        .reset_index(drop=True),
        use_container_width=True
    )

    st.subheader("Sector Allocation")
    st.markdown("How much of the index is in each sector?")
    sector_weights = filtered.groupby("sector")["weight"].sum().sort_values(ascending=False)
    st.bar_chart(sector_weights)

    st.subheader("Turnover vs Previous Quarter")
    idx = QUARTERS.index(quarter)
    if idx < len(QUARTERS) - 1:
        prev_quarter = QUARTERS[idx + 1]
        prev = set(df[(df["methodology"] == methodology) & (df["rebal_date"] == prev_quarter)]["ticker"])
        curr = set(filtered["ticker"])
        added   = curr - prev
        removed = prev - curr
        a, b = st.columns(2)
        a.success(f"**Added:** {', '.join([df[df['ticker']==t]['company'].values[0] for t in added]) if added else 'None'}")
        b.error(f"**Removed:** {', '.join([df[df['ticker']==t]['company'].values[0] for t in removed]) if removed else 'None'}")
    else:
        st.info("No previous quarter to compare.")

# ════════════════════════════════
# PAGE 3 — PERFORMANCE
# ════════════════════════════════
elif page == "Performance":
    st.title("Index Performance")
    st.markdown("Cumulative returns for all 7 indexes from Jan 2025 onwards.")

    returns_df["date"] = pd.to_datetime(returns_df["date"])
    pivot = returns_df.pivot(index="date", columns="methodology", values="cumulative_return")

    st.subheader("Cumulative Return — All Indexes")
    st.line_chart(pivot)

    st.subheader("Final Returns (End of Period)")
    final = returns_df.groupby("methodology")["cumulative_return"].last().sort_values(ascending=False).reset_index()
    final.columns = ["Methodology", "Cumulative Return"]
    final["Return %"] = ((final["Cumulative Return"] - 1) * 100).round(2).astype(str) + "%"

    for _, row in final.iterrows():
        color = "normal" if row["Cumulative Return"] >= 1 else "inverse"
        st.metric(row["Methodology"], row["Return %"])

    st.subheader("Risk Metrics")
    st.markdown("Annualised risk and return statistics per index.")
    risk_rows = []
    for method in METHODOLOGIES:
        m_ret = returns_df[returns_df["methodology"] == method]["cumulative_return"].pct_change().dropna()
        vol   = m_ret.std() * np.sqrt(252)
        total = returns_df[returns_df["methodology"] == method]["cumulative_return"].iloc[-1] - 1
        sharpe = (m_ret.mean() / m_ret.std()) * np.sqrt(252) if m_ret.std() != 0 else 0
        drawdown = (m_ret + 1).cumprod()
        max_dd = ((drawdown / drawdown.cummax()) - 1).min()
        risk_rows.append({
            "Methodology": method,
            "Total Return %": round(total * 100, 2),
            "Annualised Vol %": round(vol * 100, 2),
            "Sharpe Ratio": round(sharpe, 2),
            "Max Drawdown %": round(max_dd * 100, 2)
        })
    risk_df = pd.DataFrame(risk_rows).sort_values("Total Return %", ascending=False)
    st.dataframe(risk_df, use_container_width=True)

    st.subheader("Constituent Overlap Between Indexes")
    st.markdown("How many stocks are shared between any two indexes in the latest quarter?")
    latest_q = QUARTERS[0]
    overlap_matrix = pd.DataFrame(index=METHODOLOGIES, columns=METHODOLOGIES, dtype=int)
    for m1 in METHODOLOGIES:
        for m2 in METHODOLOGIES:
            s1 = set(df[(df["methodology"] == m1) & (df["rebal_date"] == latest_q)]["ticker"])
            s2 = set(df[(df["methodology"] == m2) & (df["rebal_date"] == latest_q)]["ticker"])
            overlap_matrix.loc[m1, m2] = len(s1 & s2)
    st.dataframe(overlap_matrix, use_container_width=True)

# ════════════════════════════════
# PAGE 4 — FACTOR EXPLORER
# ════════════════════════════════
elif page == "Factor Explorer":
    st.title("Factor Explorer")
    st.markdown("Analyse every stock across all computed financial factors.")

    quarter = st.selectbox("Select Quarter", sorted(factors_df["rebal_date"].unique(), reverse=True))
    f = factors_df[factors_df["rebal_date"] == quarter].copy()

    st.subheader("All Stock Factors")
    st.markdown("""
    - **mom_6m** — 6 month price return. Higher = stronger momentum.
    - **volatility** — annualised price volatility. Lower = more stable.
    - **rsi** — Relative Strength Index. Below 50 = oversold, above 50 = overbought.
    - **beta** — sensitivity to market. Above 1 = amplifies market moves.
    - **sharpe** — risk-adjusted return. Higher = better return per unit of risk.
    """)

    st.dataframe(
        f[["company","sector","mom_6m","volatility","rsi","beta","sharpe"]]
        .sort_values("sharpe", ascending=False)
        .reset_index(drop=True),
        use_container_width=True
    )

    st.subheader("Factor Distribution by Sector")
    factor = st.selectbox("Choose factor", ["mom_6m","volatility","rsi","beta","sharpe"])
    sector_avg = f.groupby("sector")[factor].mean().sort_values(ascending=False)
    st.bar_chart(sector_avg)

# ════════════════════════════════
# PAGE 5 — BUILD YOUR INDEX
# ════════════════════════════════
elif page == "Build Your Index":
    st.title("Build Your Own Index")
    st.markdown("Mix factors using the sliders below. We'll rank all 20 stocks by your formula and show you the resulting index.")

    st.subheader("Set Factor Weights")
    st.markdown("Drag the sliders to decide how much each factor matters. Values can be negative for contrarian bets.")

    col1, col2 = st.columns(2)
    w_mom    = col1.slider("Momentum (6M Return)",   -1.0, 1.0, 0.3, 0.1)
    w_sharpe = col1.slider("Sharpe Ratio",           -1.0, 1.0, 0.3, 0.1)
    w_vol    = col2.slider("Volatility (lower=better)", -1.0, 1.0, -0.2, 0.1)
    w_beta   = col2.slider("Beta (lower=defensive)", -1.0, 1.0, -0.1, 0.1)
    w_rsi    = col2.slider("RSI (lower=oversold)",   -1.0, 1.0, 0.1, 0.1)
    n_stocks = st.slider("Number of stocks in index", 5, 20, 10)

    quarter  = st.selectbox("Quarter", sorted(factors_df["rebal_date"].unique(), reverse=True))
    f = factors_df[factors_df["rebal_date"] == quarter].copy()

    # Normalise each factor to 0-1 range
    for col in ["mom_6m","sharpe","volatility","beta","rsi"]:
        min_v, max_v = f[col].min(), f[col].max()
        if max_v != min_v:
            f[f"n_{col}"] = (f[col] - min_v) / (max_v - min_v)
        else:
            f[f"n_{col}"] = 0.5

    f["custom_score"] = (
        w_mom    * f["n_mom_6m"]    +
        w_sharpe * f["n_sharpe"]    +
        w_vol    * f["n_volatility"] +
        w_beta   * f["n_beta"]      +
        w_rsi    * f["n_rsi"]
    )

    custom_index = f.nlargest(n_stocks, "custom_score").copy()
    custom_index["weight"] = round(1 / len(custom_index), 4)

    st.markdown("---")
    st.subheader("Your Custom Index")
    c1, c2, c3 = st.columns(3)
    c1.metric("Stocks",           len(custom_index))
    c2.metric("Sectors covered",  custom_index["sector"].nunique())
    c3.metric("Avg Sharpe",       round(custom_index["sharpe"].mean(), 2))

    st.dataframe(
        custom_index[["company","sector","custom_score","mom_6m","volatility","sharpe","beta","weight"]]
        .sort_values("custom_score", ascending=False)
        .reset_index(drop=True),
        use_container_width=True
    )

    st.subheader("Sector Allocation")
    sector_w = custom_index.groupby("sector")["weight"].sum().sort_values(ascending=False)
    st.bar_chart(sector_w)

    st.subheader("How does it compare to existing indexes?")
    latest_q = QUARTERS[0]
    overlap_rows = []
    for method in METHODOLOGIES:
        existing_tickers = set(df[(df["methodology"] == method) & (df["rebal_date"] == latest_q)]["ticker"])
        custom_tickers   = set(custom_index["ticker"])
        overlap = len(existing_tickers & custom_tickers)
        overlap_rows.append({"Methodology": method, "Stocks in common": overlap, "Out of": n_stocks})
    st.dataframe(pd.DataFrame(overlap_rows), use_container_width=True)
