import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
from utils.database import (
    fetch_realtime_metrics, fetch_warehouse_throughput, 
    fetch_realtime_status, get_trend_analysis, save_kpi_snapshot
)
from utils.data_simulator import run_simulation
import time

# Page config
st.set_page_config(
    page_title="Logistik Real-Time Dashboard",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .warning-box {
        background-color: #ff6b6b;
        padding: 15px;
        border-radius: 8px;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🚚 Logistics Real-Time Operations Dashboard")
st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Auto-refresh every 30 seconds")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=True)
    
    if st.button("🔄 Manual Refresh"):
        st.rerun()
    
    if st.button("📊 Generate Mock Data"):
        with st.spinner("Generating simulation data..."):
            run_simulation()
        st.success("Data generated successfully!")
        time.sleep(1)
        st.rerun()
    
    st.divider()
    st.header("📈 Filters")
    warehouse_filter = st.multiselect(
        "Warehouse",
        options=['All', 'WH01', 'WH02', 'WH03'],
        default=['All']
    )
    
    st.divider()
    st.info("💡 **Insight**: Deteksi lonjakan waktu tunggu >30 menit untuk trigger penambahan shift")

# Main content
col1, col2, col3 = st.columns(3)

# Fetch data
metrics = fetch_realtime_metrics()
throughput_df = fetch_warehouse_throughput()
realtime_status = fetch_realtime_status()
trend_data = get_trend_analysis(7)

# Metrics
with col1:
    otd_rate = metrics['otd_rate'][0]
    delta_otd = "+12%" if otd_rate > 0.85 else "-5%"
    st.metric(
        "📦 On-Time Delivery Rate (Last Hour)",
        f"{otd_rate:.1%}",
        delta=delta_otd,
        help="Persentase pengiriman yang sampai tepat waktu"
    )

with col2:
    avg_wait = metrics['avg_wait_minutes'][0]
    wait_color = "inverse" if avg_wait > 30 else "normal"
    st.metric(
        "⏱️ Average Waiting Time",
        f"{avg_wait:.1f} minutes",
        delta="⚠️ High >30 mins" if avg_wait > 30 else "✅ Normal",
        delta_color=wait_color
    )
    
    if avg_wait > 30:
        st.markdown('<div class="warning-box">🚨 Alert! Average waiting time exceeds 30 minutes! Consider adding picking shift.</div>', unsafe_allow_html=True)

with col3:
    total_throughput = throughput_df['total_shipments'].sum() if not throughput_df.empty else 0
    st.metric(
        "🏭 Warehouse Throughput (Last Hour)",
        f"{total_throughput} shipments",
        delta="per hour"
    )

# Charts row 1
col_ch1, col_ch2 = st.columns(2)

with col_ch1:
    st.subheader("📊 Warehouse Performance")
    if not throughput_df.empty:
        fig = px.bar(
            throughput_df,
            x='warehouse_code',
            y='total_shipments',
            color='completed_shipments',
            title="Throughput per Warehouse",
            labels={'total_shipments': 'Total Shipments', 'warehouse_code': 'Warehouse'},
            text='total_shipments'
        )
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for the last hour")

with col_ch2:
    st.subheader("📈 Real-Time Shipment Status")
    if not realtime_status.empty:
        status_counts = realtime_status['status'].value_counts()
        fig = go.Figure(data=[go.Pie(
            labels=status_counts.index,
            values=status_counts.values,
            hole=.3,
            marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        )])
        fig.update_layout(title="Distribution by Status")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active shipments")

# Trends
st.subheader("📉 KPI Trends (Last 7 Days)")
if not trend_data.empty:
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=trend_data['hour'],
        y=trend_data['avg_otd'],
        name='OTD Rate',
        line=dict(color='#00ff87', width=2),
        yaxis='y1'
    ))
    
    fig.add_trace(go.Scatter(
        x=trend_data['hour'],
        y=trend_data['avg_wait'],
        name='Wait Time (min)',
        line=dict(color='#ff6b6b', width=2, dash='dot'),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title="Weekly Performance Trends",
        xaxis_title="Date",
        yaxis=dict(title="OTD Rate", tickformat='.0%'),
        yaxis2=dict(title="Wait Time (minutes)", overlaying='y', side='right'),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Recent shipments table
st.subheader("🚛 Recent Shipments (Last 24 Hours)")
if not realtime_status.empty:
    st.dataframe(
        realtime_status,
        column_config={
            "shipment_id": "Shipment ID",
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=['pending', 'loaded', 'in_transit', 'delivered'],
                width="small"
            ),
            "hours_in_transit": st.column_config.NumberColumn(
                "Hours in Transit",
                format="%.1f h"
            ),
            "created_at": st.column_config.DatetimeColumn(
                "Created At",
                format="DD/MM/YY HH:mm"
            )
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.info("No recent shipments")

# Auto-refresh logic
if auto_refresh:
    time.sleep(30)
    st.rerun()

# Footer
st.divider()
st.caption("""
**Dashboard Features:**
- ✅ Real-time OTD monitoring
- ⚠️ Automatic alert for waiting time >30 minutes
- 📊 Warehouse throughput tracking
- 📈 Weekly trend analysis
- 🔄 Auto-refresh every 30 seconds
""")

@st.cache_data
def export_daily_report():
    """Generate Excel report untuk email"""
    import io
    import xlsxwriter
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: Daily Metrics
        metrics_df = fetch_realtime_metrics()
        metrics_df.to_excel(writer, sheet_name='Daily KPIs', index=False)
        
        # Sheet 2: Warehouse Performance
        throughput_df = fetch_warehouse_throughput()
        throughput_df.to_excel(writer, sheet_name='Warehouse Report', index=False)
        
        # Sheet 3: Trend Analysis (last 30 days)
        trend_30d = get_trend_analysis(30)
        trend_30d.to_excel(writer, sheet_name='Monthly Trends', index=False)
    
    return output.getvalue()

# Di sidebar
with st.sidebar:
    if st.button("📧 Export Daily Report"):
        excel_data = export_daily_report()
        st.download_button(
            label="Download Excel Report",
            data=excel_data,
            file_name=f"logistics_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.success("Report generated! Download ready.")
