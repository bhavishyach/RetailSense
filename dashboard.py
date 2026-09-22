import streamlit as st
import psycopg2
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import os

st.set_page_config(
    page_title="RetailSense AI Dashboard",
    page_icon="📊",
    layout="wide"
)

st_autorefresh(interval=5000, key="dashboardrefresh")

st.markdown("""
<style>

.block-container{
    padding-top:2rem;
    padding-bottom:2rem;
}

.dashboard-header{
    background:linear-gradient(135deg,#FFE5F1,#FFD6EA,#FFC7E3);
    border-radius:25px;
    padding:20px;
    text-align:center;
    box-shadow:0px 8px 25px rgba(0,0,0,0.10);
    margin-bottom:35px;
}

.big-title{
    font-size:34px;
    font-weight:900;
    color:#E91E63;
    margin:0;
    letter-spacing:-1px;
}

.subtitle{
    font-size:20px;
    color:#555555;
    margin-top:10px;
}

div[data-testid="stMetric"]{
    background:white;
    padding:22px;
    border-radius:18px;
    border:1px solid #F7D3E6;
    box-shadow:0px 5px 15px rgba(0,0,0,0.08);
}

h3{
    color:#E91E63;
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dashboard-header">

<div class="big-title">
🌸 RetailSense AI Dashboard
</div>

<div class="subtitle">
AI-powered Retail Data Enrichment Monitoring Dashboard
</div>

</div>
""", unsafe_allow_html=True)

conn = psycopg2.connect(
    dbname=os.getenv("PGDATABASE", "retailsense_gold"),
    user=os.getenv("PGUSER", "bhavishyachallagolla"),
    password=os.getenv("PGPASSWORD", "retailsense123"),
    host=os.getenv("PGHOST", "localhost"),
    port=os.getenv("PGPORT", "5432")
)

latest_query = """
SELECT *
FROM gold_pipeline_runs
ORDER BY run_timestamp DESC
LIMIT 1;
"""

df = pd.read_sql(latest_query, conn)

st.subheader("📊 Pipeline Overview")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "📦 Records Processed",
        int(df["total_records_processed"][0])
    )

with col2:
    st.metric(
        "❌ Failure Rate",
        f"{df['failure_rate'][0] * 100:.2f}%"
    )

with col3:
    st.metric(
        "⚡ AI Response Time",
        f"{df['avg_latency_ms'][0]:.3f}s"
    )

with col4:
    st.metric(
        "🎯 AI Accuracy",
        f"{df['avg_confidence_score'][0] * 100:.1f}%"
    )

with col5:
    st.metric(
        "💰 AI Cost / Record",
        f"${df['cost_estimate_usd'][0]:.4f}"
    )

st.divider()

left, right = st.columns(2)

with left:

    st.subheader("📈 AI Accuracy Trend")

    trend_query = """
    SELECT
    run_timestamp,
    avg_confidence_score
    FROM gold_pipeline_runs
    ORDER BY run_timestamp;
    """

    trend_df = pd.read_sql(trend_query, conn)

    trend_df = trend_df.set_index("run_timestamp")

    st.line_chart(trend_df["avg_confidence_score"])

with right:

    st.subheader("📉 Failure Rate Trend")

    failure_query = """
    SELECT
    run_timestamp,
    failure_rate
    FROM gold_pipeline_runs
    ORDER BY run_timestamp;
    """

    failure_df = pd.read_sql(failure_query, conn)

    failure_df = failure_df.set_index("run_timestamp")

    st.line_chart(failure_df["failure_rate"])

st.divider()

st.subheader("📊 Worst Performing Categories")

category_query = """
SELECT
category,
avg_confidence
FROM gold_category_metrics
ORDER BY avg_confidence ASC
LIMIT 10;
"""

category_df = pd.read_sql(category_query, conn)

st.bar_chart(
    category_df.set_index("category")
)

st.divider()

st.subheader("📋 Recent Pipeline Runs")

runs_query = """
SELECT *
FROM gold_pipeline_runs
ORDER BY run_timestamp DESC
LIMIT 10;
"""

runs_df = pd.read_sql(runs_query, conn)

st.dataframe(
    runs_df,
    hide_index=True,
    use_container_width=True
)

st.divider()

st.caption(
    "🌸 RetailSense AI • Built with Streamlit • PostgreSQL • Apache Airflow • Claude AI • ANNA (Chanakya Challagolla)"
)

conn.close()