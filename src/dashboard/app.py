import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import re
import time
import shutil
import psutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache

# Set page config
st.set_page_config(
    page_title="ATC Voice Communications Dashboard",
    page_icon="🛫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# File paths
BASE_DIR = Path(".")
TRANSCRIPTIONS_FILE = BASE_DIR / "src" / "data" / "logs" / "transcripts" / "categorized_transcription_results.json"
COMMUNICATIONS_FILE = BASE_DIR / "src" / "data" / "logs" / "atc_communications.txt"

@st.cache_data(ttl=10)  # Reduced cache for 10 seconds for better responsiveness
def load_transcription_data() -> Optional[pd.DataFrame]:
    """Load and parse transcription data from JSON file."""
    try:
        if not TRANSCRIPTIONS_FILE.exists():
            return None
        
        with open(TRANSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'items' not in data:
            return None
        
        df = pd.DataFrame(data['items'])
        
        # Convert timestamp to datetime
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
        df['date'] = df['timestamp_utc'].dt.date
        df['hour'] = df['timestamp_utc'].dt.hour
        df['day_of_week'] = df['timestamp_utc'].dt.day_name()
        
        # Extract flight number from transcription text
        df['flight_number'] = df['raw_transcription'].apply(extract_flight_number)
        
        return df
    
    except Exception as e:
        st.error(f"Error loading transcription data: {e}")
        return None

@st.cache_data(ttl=10)  # Reduced cache for 10 seconds for better responsiveness
def load_communication_logs() -> Optional[pd.DataFrame]:
    """Load and parse communication detection logs."""
    try:
        if not COMMUNICATIONS_FILE.exists():
            return None
        
        with open(COMMUNICATIONS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse log entries
        log_entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse timestamp and message
            if line.startswith('[') and ']' in line:
                timestamp_str = line[1:line.find(']')]
                message = line[line.find(']') + 2:]
                
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Only include communication detection entries
                    if 'Communication detected' in message:
                        # Extract dBFS value
                        dbfs_match = re.search(r'\(dBFS: ([-\d.]+)\)', message)
                        dbfs = float(dbfs_match.group(1)) if dbfs_match else None
                        
                        log_entries.append({
                            'timestamp': timestamp,
                            'message': message,
                            'dbfs': dbfs,
                            'date': timestamp.date(),
                            'hour': timestamp.hour,
                            'day_of_week': timestamp.strftime('%A')
                        })
                
                except ValueError:
                    continue
        
        if not log_entries:
            return None
        
        return pd.DataFrame(log_entries)
    
    except Exception as e:
        st.error(f"Error loading communication logs: {e}")
        return None

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_disk_usage():
    """Get disk usage information for the VM."""
    try:
        # Get disk usage for the root directory
        disk_usage = shutil.disk_usage('/')
        
        # Convert bytes to GB
        total_gb = disk_usage.total / (1024**3)
        used_gb = disk_usage.used / (1024**3)
        free_gb = disk_usage.free / (1024**3)
        
        # Calculate percentage
        used_percent = (used_gb / total_gb) * 100
        free_percent = (free_gb / total_gb) * 100
        
        return {
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'used_percent': round(used_percent, 1),
            'free_percent': round(free_percent, 1)
        }
    except Exception as e:
        return {
            'total_gb': 0,
            'used_gb': 0,
            'free_gb': 0,
            'used_percent': 0,
            'free_percent': 0,
            'error': str(e)
        }


@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_audio_file_stats():
    """Get audio file statistics from the raw directory."""
    try:
        raw_dir = BASE_DIR / "src" / "data" / "raw"
        
        if not raw_dir.exists():
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'avg_size_mb': 0,
                'error': 'Raw audio directory not found'
            }
        
        # Get all audio files
        audio_files = list(raw_dir.glob("*.wav"))
        
        if not audio_files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'avg_size_mb': 0,
                'error': 'No audio files found'
            }
        
        # Calculate total size
        total_size_bytes = sum(f.stat().st_size for f in audio_files)
        total_size_mb = total_size_bytes / (1024 * 1024)
        avg_size_mb = total_size_mb / len(audio_files)
        
        return {
            'total_files': len(audio_files),
            'total_size_mb': round(total_size_mb, 2),
            'avg_size_mb': round(avg_size_mb, 2)
        }
    except Exception as e:
        return {
            'total_files': 0,
            'total_size_mb': 0,
            'avg_size_mb': 0,
            'error': str(e)
        }

@st.cache_data(ttl=10)  # Cache for 10 seconds - CPU changes frequently
def get_system_info():
    """Get system resource information."""
    try:
        # CPU usage - reduce interval to 0.1 seconds for faster response
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_used_gb = memory.used / (1024**3)
        memory_percent = memory.percent
        
        return {
            'cpu_percent': round(cpu_percent, 1),
            'memory_total_gb': round(memory_total_gb, 2),
            'memory_used_gb': round(memory_used_gb, 2),
            'memory_percent': round(memory_percent, 1)
        }
    except Exception as e:
        return {
            'cpu_percent': 0,
            'memory_total_gb': 0,
            'memory_used_gb': 0,
            'memory_percent': 0,
            'error': str(e)
        }


def extract_flight_number(text: str) -> str:
    if not text:
        return "Unknown"
    
    # Common flight number patterns
    patterns = [
        r'\b([A-Z]{2,3})\s*(\d{3,4})\b',  # AA1234, DL567
        r'\b([A-Z]+\d{2,4})\b',           # United1993
        r'\b(\d{3,4})\b'                  # Just numbers
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    return "Unknown"

@st.cache_data(ttl=10)  # Reduced cache for 10 seconds for better responsiveness
def calculate_stats(transcription_df: Optional[pd.DataFrame], communication_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """Calculate statistics from both data sources."""
    stats = {
        'total_transcriptions': 0,
        'total_communications': 0,
        'categories': {},
        'daily_transcriptions': {},
        'daily_communications': {},
        'hourly_pattern': {},
        'flight_stats': {},
        'duration_stats': {},
        'last_update': datetime.now()
    }
    
    # Transcription statistics
    if transcription_df is not None and not transcription_df.empty:
        stats['total_transcriptions'] = len(transcription_df)
        stats['categories'] = transcription_df['category'].value_counts().to_dict()
        stats['daily_transcriptions'] = transcription_df.groupby('date').size().to_dict()
        stats['hourly_pattern'] = transcription_df.groupby('hour').size().to_dict()
        
        # Flight statistics
        flight_counts = transcription_df['flight_number'].value_counts()
        stats['flight_stats'] = {
            'total_flights': flight_counts.nunique(),
            'avg_comms_per_flight': flight_counts.mean() if len(flight_counts) > 0 else 0,
            'max_comms_per_flight': flight_counts.max() if len(flight_counts) > 0 else 0
        }
        
        # Duration statistics
        if 'raw_duration_s' in transcription_df.columns:
            duration_series = transcription_df['raw_duration_s']
            stats['duration_stats'] = {
                'mean': duration_series.mean(),
                'median': duration_series.median(),
                'min': duration_series.min(),
                'max': duration_series.max(),
                'std': duration_series.std()
            }
    
    # Communication detection statistics
    if communication_df is not None and not communication_df.empty:
        stats['total_communications'] = len(communication_df)
        stats['daily_communications'] = communication_df.groupby('date').size().to_dict()
        
        # Audio level statistics
        if 'dbfs' in communication_df.columns:
            dbfs_series = communication_df['dbfs'].dropna()
            if len(dbfs_series) > 0:
                stats['audio_levels'] = {
                    'mean': dbfs_series.mean(),
                    'median': dbfs_series.median(),
                    'min': dbfs_series.min(),
                    'max': dbfs_series.max()
                }
    
    return stats

def main():
    st.title("🛫 ATC Voice Communications Dashboard")
    st.markdown("---")
    
    # Auto-refresh for live data
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh Communications", value=True, help="Automatically refresh communication data every 30 seconds")
    
    # Initialize session state for refresh timing
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    if auto_refresh:
        st.sidebar.info("🟢 Live monitoring active")
        current_time = time.time()
        time_since_refresh = current_time - st.session_state.last_refresh
        
        # Show countdown
        time_until_refresh = 30 - (time_since_refresh % 30)
        st.sidebar.info(f"Next refresh in: {int(time_until_refresh)}s")
        
        # Auto-refresh every 30 seconds using st.rerun
        if time_since_refresh >= 30:
            st.session_state.last_refresh = current_time
            st.sidebar.success("🔄 Refreshing data...")
            st.rerun()
    
    # Sidebar with data status
    st.sidebar.header("📊 Data Status")
    
    # Data source indicators
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if TRANSCRIPTIONS_FILE.exists():
            if auto_refresh:
                st.success(f"📝 Transcriptions: {TRANSCRIPTIONS_FILE.name}")
                st.caption("🟢 Live processing")
            else:
                st.info(f"📝 Transcriptions: {TRANSCRIPTIONS_FILE.name}")
                st.caption("⏸️ Manual refresh")
        else:
            st.error("📝 No transcription data")
    
    with col2:
        if COMMUNICATIONS_FILE.exists():
            if auto_refresh:
                st.success(f"🎙️ Communications: {COMMUNICATIONS_FILE.name}")
                st.caption("🟢 Live data")
            else:
                st.info(f"🎙️ Communications: {COMMUNICATIONS_FILE.name}")
                st.caption("⏸️ Manual refresh")
        else:
            st.error("🎙️ No communication logs")
    
    # Load data
    with st.spinner("Loading ATC data..."):
        transcription_df = load_transcription_data()
        communication_df = load_communication_logs()
    
    # Calculate statistics
    stats = calculate_stats(transcription_df, communication_df)
    
    st.sidebar.markdown(f"**Last Update:** {stats['last_update'].strftime('%H:%M:%S')}")
    
    # VM System Monitoring
    st.sidebar.markdown("---")
    st.sidebar.header("🖥️ VM System Status")
    
    # Get system information
    disk_info = get_disk_usage()
    system_info = get_system_info()
    audio_stats = get_audio_file_stats()
    
    # Disk space monitoring
    st.sidebar.subheader("💾 Disk Space")
    if 'error' not in disk_info:
        st.sidebar.metric(
            "Used Space", 
            f"{disk_info['used_gb']:.1f} GB",
            delta=f"{disk_info['used_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Free Space", 
            f"{disk_info['free_gb']:.1f} GB",
            delta=f"{disk_info['free_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Total Space", 
            f"{disk_info['total_gb']:.1f} GB"
        )
        
        # Disk usage progress bar
        disk_usage_percent = disk_info['used_percent']
        if disk_usage_percent > 90:
            st.sidebar.error(f"⚠️ Disk usage: {disk_usage_percent:.1f}%")
        elif disk_usage_percent > 80:
            st.sidebar.warning(f"⚠️ Disk usage: {disk_usage_percent:.1f}%")
        else:
            st.sidebar.success(f"✅ Disk usage: {disk_usage_percent:.1f}%")
    else:
        st.sidebar.error(f"❌ Disk info error: {disk_info['error']}")
    
    # System resources
    st.sidebar.subheader("⚡ System Resources")
    if 'error' not in system_info:
        st.sidebar.metric(
            "CPU Usage", 
            f"{system_info['cpu_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Memory Usage", 
            f"{system_info['memory_used_gb']:.1f} GB",
            delta=f"{system_info['memory_percent']:.1f}%"
        )
        st.sidebar.metric(
            "Total Memory", 
            f"{system_info['memory_total_gb']:.1f} GB"
        )
    else:
        st.sidebar.error(f"❌ System info error: {system_info['error']}")
    
    # Audio file statistics
    st.sidebar.subheader("🎵 Audio Files")
    if 'error' not in audio_stats:
        st.sidebar.metric(
            "Total Audio Files", 
            f"{audio_stats['total_files']:,}"
        )
        st.sidebar.metric(
            "Total Audio Size", 
            f"{audio_stats['total_size_mb']:.1f} MB"
        )
        st.sidebar.metric(
            "Avg File Size", 
            f"{audio_stats['avg_size_mb']:.1f} MB"
        )
    else:
        st.sidebar.error(f"❌ Audio stats error: {audio_stats['error']}")
    
    # Show data source file info
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Sources:**")
    st.sidebar.code(f"Transcriptions:\n{TRANSCRIPTIONS_FILE}")
    st.sidebar.code(f"Communications:\n{COMMUNICATIONS_FILE}")
    
    # Main dashboard
    if transcription_df is None and communication_df is None:
        st.warning("⚠️ No data available. Please ensure the data files exist and contain valid data.")
        return
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview", 
        "📈 Daily Analytics", 
        "🏷️ Categories",
        "📋 Detailed Stats", 
        "🔍 Pattern Analysis"
    ])
    
    with tab1:
        st.header("Dashboard Overview")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if auto_refresh:
                st.metric(
                    "Total Transcriptions", 
                    f"{stats['total_transcriptions']:,}",
                    delta=f"🟢 Live processing"
                )
            else:
                st.metric(
                    "Total Transcriptions", 
                    f"{stats['total_transcriptions']:,}",
                    delta=f"⏸️ Manual refresh"
                )
        
        with col2:
            if auto_refresh:
                st.metric(
                    "Communication Detections",
                    f"{stats['total_communications']:,}",
                    delta=f"🟢 Live monitoring"
                )
            else:
                st.metric(
                    "Communication Detections",
                    f"{stats['total_communications']:,}",
                    delta=f"⏸️ Manual refresh"
                )
        
        with col3:
            if stats['flight_stats']['total_flights'] > 0:
                st.metric(
                    "Unique Flights",
                    f"{stats['flight_stats']['total_flights']:,}",
                    delta=f"{stats['flight_stats']['avg_comms_per_flight']:.1f} avg/flight"
                )
            else:
                st.metric("Unique Flights", "0", delta="No data")
        
        with col4:
            if stats['categories']:
                top_category = max(stats['categories'], key=stats['categories'].get)
                st.metric(
                    "Top Category",
                    top_category,
                    delta=f"{stats['categories'][top_category]} comms"
                )
            else:
                st.metric("Top Category", "N/A", delta="No data")
        
        # Daily Communication Bar Graph
        st.subheader("📊 Daily Communication Counts")
        
        # Create combined daily data
        daily_data = []
        
        if stats['daily_transcriptions']:
            for date_str, count in stats['daily_transcriptions'].items():
                daily_data.append({
                    'Date': pd.to_datetime(date_str),
                    'Count': count,
                    'Type': 'Transcriptions'
                })
        
        if stats['daily_communications']:
            for date_str, count in stats['daily_communications'].items():
                daily_data.append({
                    'Date': pd.to_datetime(date_str),
                    'Count': count,
                    'Type': 'Communication Detections'
                })
        
        if daily_data:
            daily_df = pd.DataFrame(daily_data)
            
            # Create bar graph
            fig_daily_bar = px.bar(
                daily_df, 
                x='Date', 
                y='Count', 
                color='Type',
                title="Daily Communication Counts",
                labels={'Date': 'Date', 'Count': 'Number of Communications'},
                color_discrete_map={
                    'Transcriptions': '#1f77b4',
                    'Communication Detections': '#ff7f0e'
                }
            )
            
            # Format x-axis to show dates properly
            fig_daily_bar.update_xaxes(
                tickformat="%Y-%m-%d",
                tickangle=45
            )
            
            # Update layout
            fig_daily_bar.update_layout(
                height=500,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            st.plotly_chart(fig_daily_bar, use_container_width=True)
        else:
            st.info("No daily communication data available yet.")
        
        # Recent transcriptions table
        if transcription_df is not None and not transcription_df.empty:
            st.subheader("📋 Recent Transcriptions")
            recent_df = transcription_df.tail(10)[['timestamp_utc', 'flight_number', 'category', 'raw_transcription']]
            recent_df.columns = ['Timestamp', 'Flight', 'Category', 'Communication']
            st.dataframe(recent_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.header("Daily Analytics")
        
        if stats['daily_transcriptions'] or stats['daily_communications']:
            # Statistics tables
            col1, col2 = st.columns(2)
            
            with col1:
                if stats['daily_transcriptions']:
                    st.subheader("📝 Transcription Statistics")
                    daily_counts = list(stats['daily_transcriptions'].values())
                    stats_table = pd.DataFrame({
                        'Metric': ['Total Days', 'Min per Day', 'Max per Day', 'Average per Day', 'Median per Day'],
                        'Value': [
                            len(daily_counts),
                            f"{min(daily_counts):.0f}",
                            f"{max(daily_counts):.0f}",
                            f"{np.mean(daily_counts):.1f}",
                            f"{np.median(daily_counts):.1f}"
                        ]
                    })
                    st.dataframe(stats_table, use_container_width=True, hide_index=True)
            
            with col2:
                if stats['daily_communications']:
                    st.subheader("🎙️ Communication Detection Statistics")
                    comm_counts = list(stats['daily_communications'].values())
                    comm_stats_table = pd.DataFrame({
                        'Metric': ['Total Days', 'Min per Day', 'Max per Day', 'Average per Day', 'Median per Day'],
                        'Value': [
                            len(comm_counts),
                            f"{min(comm_counts):.0f}",
                            f"{max(comm_counts):.0f}",
                            f"{np.mean(comm_counts):.1f}",
                            f"{np.median(comm_counts):.1f}"
                        ]
                    })
                    st.dataframe(comm_stats_table, use_container_width=True, hide_index=True)
        
        else:
            st.info("No daily data available yet.")
    
    with tab3:
        # Simple test - just show the data directly
        if stats['categories']:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Category Distribution")
                
                # Pie chart
                categories_df = pd.DataFrame(list(stats['categories'].items()), 
                                           columns=['Category', 'Count'])
                
                fig_pie = px.pie(categories_df, values='Count', names='Category',
                               title="Communication Categories")
                fig_pie.update_layout(height=400)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.subheader("📈 Category Counts")
                
                # Bar chart
                fig_bar = px.bar(categories_df, x='Category', y='Count',
                               title="Communications by Category")
                fig_bar.update_layout(height=400)
                fig_bar.update_xaxes(tickangle=45)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Category details table
            st.subheader("📋 Category Details")
            category_details = []
            for category, count in stats['categories'].items():
                percentage = (count / stats['total_transcriptions']) * 100
                category_details.append({
                    'Category': category,
                    'Count': count,
                    'Percentage': f"{percentage:.1f}%",
                    'Avg per Day': f"{count / len(stats['daily_transcriptions']) if stats['daily_transcriptions'] else 0:.1f}"
                })
            
            category_df = pd.DataFrame(category_details)
            st.dataframe(category_df, use_container_width=True, hide_index=True)
        
        else:
            st.info("No category data available yet.")
    
    with tab4:
        st.header("Detailed Statistics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📝 Transcription Statistics")
            
            if stats['duration_stats']:
                duration_table = pd.DataFrame({
                    'Metric': ['Mean Duration', 'Median Duration', 'Min Duration', 'Max Duration', 'Std Deviation'],
                    'Value (seconds)': [
                        f"{stats['duration_stats']['mean']:.1f}",
                        f"{stats['duration_stats']['median']:.1f}",
                        f"{stats['duration_stats']['min']:.1f}",
                        f"{stats['duration_stats']['max']:.1f}",
                        f"{stats['duration_stats']['std']:.1f}"
                    ]
                })
                st.dataframe(duration_table, use_container_width=True, hide_index=True)
            
            if stats['flight_stats']['total_flights'] > 0:
                st.subheader("✈️ Flight Statistics")
                flight_table = pd.DataFrame({
                    'Metric': ['Total Flights', 'Avg Communications per Flight', 'Max Communications per Flight'],
                    'Value': [
                        f"{stats['flight_stats']['total_flights']:,}",
                        f"{stats['flight_stats']['avg_comms_per_flight']:.1f}",
                        f"{stats['flight_stats']['max_comms_per_flight']:.0f}"
                    ]
                })
                st.dataframe(flight_table, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("🎙️ Audio Level Statistics")
            
            if 'audio_levels' in stats:
                audio_table = pd.DataFrame({
                    'Metric': ['Mean dBFS', 'Median dBFS', 'Min dBFS', 'Max dBFS'],
                    'Value': [
                        f"{stats['audio_levels']['mean']:.1f}",
                        f"{stats['audio_levels']['median']:.1f}",
                        f"{stats['audio_levels']['min']:.1f}",
                        f"{stats['audio_levels']['max']:.1f}"
                    ]
                })
                st.dataframe(audio_table, use_container_width=True, hide_index=True)
            else:
                st.info("No audio level data available.")
        
        # Raw data preview
        if transcription_df is not None and not transcription_df.empty:
            st.subheader("📄 Raw Data Preview")
            st.dataframe(transcription_df.head(10), use_container_width=True)
    
    with tab5:
        st.header("Pattern Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if stats['hourly_pattern']:
                st.subheader("🕐 Hourly Activity Pattern")
                
                hourly_df = pd.DataFrame(list(stats['hourly_pattern'].items()), 
                                       columns=['Hour', 'Count'])
                hourly_df['Hour'] = hourly_df['Hour'].astype(int)
                hourly_df = hourly_df.sort_values('Hour')
                
                fig_hourly = px.bar(hourly_df, x='Hour', y='Count',
                                  title="Communications by Hour of Day")
                fig_hourly.update_layout(height=400)
                st.plotly_chart(fig_hourly, use_container_width=True)
        
        with col2:
            if transcription_df is not None and 'flight_number' in transcription_df.columns:
                st.subheader("✈️ Communications per Flight")
                
                flight_counts = transcription_df['flight_number'].value_counts().head(20)
                flight_df = pd.DataFrame({
                    'Flight': flight_counts.index,
                    'Communications': flight_counts.values
                })
                
                fig_flights = px.bar(flight_df, x='Flight', y='Communications',
                                   title="Top 20 Most Active Flights")
                fig_flights.update_layout(height=400)
                fig_flights.update_xaxes(tickangle=45)
                st.plotly_chart(fig_flights, use_container_width=True)
        
        # Communication intervals analysis
        if transcription_df is not None and not transcription_df.empty:
            st.subheader("⏱️ Communication Timing Analysis")
            
            # Sort by timestamp and calculate intervals
            sorted_df = transcription_df.sort_values('timestamp_utc')
            intervals = []
            
            for i in range(1, len(sorted_df)):
                interval = (sorted_df.iloc[i]['timestamp_utc'] - 
                           sorted_df.iloc[i-1]['timestamp_utc']).total_seconds()
                intervals.append(interval)
            
            if intervals:
                intervals_df = pd.DataFrame({'interval_seconds': intervals})
                # Filter out very long intervals (likely day breaks)
                filtered_intervals = intervals_df[intervals_df['interval_seconds'] < 3600]
                
                if len(filtered_intervals) > 0:
                    interval_stats = {
                        'Metric': ['Average Interval', 'Median Interval', 'Min Interval', 'Max Interval'],
                        'Value (seconds)': [
                            f"{filtered_intervals['interval_seconds'].mean():.1f}",
                            f"{filtered_intervals['interval_seconds'].median():.1f}",
                            f"{filtered_intervals['interval_seconds'].min():.1f}",
                            f"{filtered_intervals['interval_seconds'].max():.1f}"
                        ]
                    }
                    
                    interval_stats_df = pd.DataFrame(interval_stats)
                    st.dataframe(interval_stats_df, use_container_width=True, hide_index=True)
                    
                    # Interval histogram
                    fig_intervals = px.histogram(filtered_intervals, x='interval_seconds',
                                               nbins=50, title="Distribution of Communication Intervals")
                    fig_intervals.update_layout(height=300)
                    st.plotly_chart(fig_intervals, use_container_width=True)
    
    # Footer
    st.markdown("---")
    if auto_refresh:
        st.markdown(
            """
            <div style='text-align: center; color: #666;'>
                🛫 ATC Voice Communications Dashboard | 🟢 Live Processing Active (Communications + Transcriptions)
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style='text-align: center; color: #666;'>
                🛫 ATC Voice Communications Dashboard | ⏸️ Manual Refresh Mode
            </div>
            """, 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()