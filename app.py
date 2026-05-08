import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time

# Page config
st.set_page_config(
    page_title="Logistik Real-Time Dashboard",
    page_icon="🚚",
    layout="wide"
)

# Koneksi database menggunakan st.secrets
def get_db_connection():
    return psycopg2.connect(st.secrets["database_url"])

# Fungsi ambil KPI
def fetch_otd_rate():
    conn = get_db_connection()
    query = """
        SELECT 
            COUNT(CASE WHEN status = 'delivered' AND delivered_at <= eta THEN 1 END)::float 
            / NULLIF(COUNT(CASE WHEN status = 'delivered' THEN 1 END), 0) as otd_rate
        FROM shipments
        WHERE created_at >= NOW() - INTERVAL '1 hour'
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df['otd_rate'][0] if not df.empty else 0

def fetch_avg_wait():
    conn = get_db_connection()
    query = """
        SELECT AVG(EXTRACT(epoch FROM (loaded_at - arrived_at))/60) as avg_wait
        FROM shipments
        WHERE created_at >= NOW() - INTERVAL '1 hour'
        AND loaded_at IS NOT NULL AND arrived_at IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df['avg_wait'][0] if not df.empty and df['avg_wait'][0] else 0

def fetch_throughput():
    conn = get_db_connection()
    query = """
        SELECT warehouse_code, COUNT(*) as total
        FROM shipments
        WHERE created_at >= NOW() - INTERVAL '1 hour'
        GROUP BY warehouse_code
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def fetch_recent_shipments():
    conn = get_db_connection()
    query = """
        SELECT shipment_id, status, warehouse_code, 
               TO_CHAR(created_at, 'HH24:MI:SS') as created_time
        FROM shipments
        ORDER BY created_at DESC
        LIMIT 10
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Custom CSS
st.markdown("""
<style>
    .big-font { font-size: 30px !important; font-weight: bold; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   padding: 20px; border-radius: 10px; color: white; }
    .warning { background-color: #ff6b6b; padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🚚 Real-Time Logistics Dashboard")
st.caption(f"Last update: {datetime.now().strftime('%H:%M:%S')} | Auto-refresh every 30 seconds")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    auto_refresh = st.checkbox("Auto Refresh (30s)", value=True)
    if st.button("🔄 Refresh Now"):
        st.rerun()
    
    st.divider()
    st.info("💡 **Alert:** Waiting time >30 menit akan memicu notifikasi")

# Main metrics
col1, col2, col3 = st.columns(3)

with col1:
    otd = fetch_otd_rate()
    st.metric("📦 On-Time Delivery Rate", f"{otd:.1%}", 
              delta="Target 85%" if otd < 0.85 else "Above Target")

with col2:
    wait = fetch_avg_wait()
    delta_color = "inverse" if wait > 30 else "normal"
    st.metric("⏱️ Avg Waiting Time", f"{wait:.1f} min", 
              delta="⚠️ HIGH" if wait > 30 else "Normal", 
              delta_color=delta_color)
    
    if wait > 30:
        st.markdown('<div class="warning">🚨 ALERT: Waiting time exceeds 30 minutes! Tambah shift picking!</div>', 
                    unsafe_allow_html=True)

with col3:
    throughput_df = fetch_throughput()
    total = throughput_df['total'].sum() if not throughput_df.empty else 0
    st.metric("🏭 Warehouse Throughput", f"{total} shipments/hour")

# Charts
col_ch1, col_ch2 = st.columns(2)

with col_ch1:
    st.subheader("📊 Throughput per Warehouse")
    if not throughput_df.empty:
        fig = px.bar(throughput_df, x='warehouse_code', y='total', 
                     title="Shipments Last Hour", color='warehouse_code')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available")

with col_ch2:
    st.subheader("🚛 Recent Shipments")
    recent = fetch_recent_shipments()
    if not recent.empty:
        st.dataframe(recent, use_container_width=True, hide_index=True)
    else:
        st.info("No recent shipments")

# Auto refresh
if auto_refresh:
    time.sleep(30)
    st.rerun()
