import os
import psycopg2
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import streamlit as st

# Konfigurasi Supabase (gunakan st.secrets untuk Streamlit Cloud)
SUPABASE_URL = st.secrets["supabase_url"]
SUPABASE_KEY = st.secrets["supabase_key"]
DB_URL = st.secrets["database_url"]

@st.cache_resource
def get_db_connection():
    """Membuat koneksi database"""
    return psycopg2.connect(DB_URL)

def fetch_realtime_metrics():
    """Ambil KPI real-time"""
    conn = get_db_connection()
    query = """
        WITH hourly_shipments AS (
            SELECT 
                *,
                EXTRACT(epoch FROM (loaded_at - arrived_at))/60 AS wait_minutes
            FROM shipments
            WHERE created_at >= NOW() - INTERVAL '1 hour'
        )
        SELECT 
            COALESCE(
                COUNT(CASE WHEN status = 'delivered' AND delivered_at <= eta THEN 1 END)::float 
                / NULLIF(COUNT(CASE WHEN status = 'delivered' THEN 1 END), 0),
                0
            ) AS otd_rate,
            COALESCE(AVG(wait_minutes), 0) AS avg_wait_minutes
        FROM hourly_shipments
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def fetch_warehouse_throughput():
    """Hitung throughput gudang per jam"""
    conn = get_db_connection()
    query = """
        SELECT 
            warehouse_code,
            COUNT(*) as total_shipments,
            COUNT(CASE WHEN status = 'delivered' THEN 1 END) as completed_shipments,
            NOW()::TIME as current_time
        FROM shipments
        WHERE created_at >= NOW() - INTERVAL '1 hour'
        GROUP BY warehouse_code
        ORDER BY total_shipments DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def fetch_realtime_status():
    """Ambil status real-time semua shipment"""
    conn = get_db_connection()
    query = """
        SELECT 
            shipment_id,
            status,
            warehouse_code,
            CASE 
                WHEN status = 'in_transit' THEN 
                    EXTRACT(epoch FROM (NOW() - created_at))/3600
                ELSE NULL
            END as hours_in_transit,
            created_at
        FROM shipments
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 20
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def insert_shipment_webhook(shipment_data):
    """Insert shipment dari webhook/API"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO shipments (shipment_id, status, eta, warehouse_code, distance_km)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        shipment_data['shipment_id'],
        shipment_data['status'],
        shipment_data['eta'],
        shipment_data['warehouse_code'],
        shipment_data.get('distance_km', 0)
    ))
    
    conn.commit()
    cur.close()
    conn.close()
    return True

def save_kpi_snapshot():
    """Simpan snapshot KPI untuk trending"""
    conn = get_db_connection()
    metrics = fetch_realtime_metrics()
    throughput = fetch_warehouse_throughput()
    
    total_throughput = throughput['total_shipments'].sum()
    
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO kpi_history (otd_rate, avg_wait_minutes, warehouse_throughput)
        VALUES (%s, %s, %s)
    """, (metrics['otd_rate'][0], metrics['avg_wait_minutes'][0], total_throughput))
    
    conn.commit()
    cur.close()
    conn.close()

def get_trend_analysis(days=7):
    """Ambil data trend untuk analisis mingguan"""
    conn = get_db_connection()
    query = f"""
        SELECT 
            DATE_TRUNC('hour', timestamp) as hour,
            AVG(otd_rate) as avg_otd,
            AVG(avg_wait_minutes) as avg_wait,
            AVG(warehouse_throughput) as avg_throughput
        FROM kpi_history
        WHERE timestamp >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE_TRUNC('hour', timestamp)
        ORDER BY hour DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df
