import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

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

def extract_flight_number(text: str) -> str:
    """Extract flight number from transcription text."""
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
        
        if time_since_refresh >= 30:  # Refresh every 30 seconds
            st.session_state.last_refresh = current_time
            st.rerun()
        
        # Show countdown
        time_until_refresh = 30 - (time_since_refresh % 30)
        st.sidebar.info(f"Next refresh in: {int(time_until_refresh)}s")
    
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
        
        # Recent activity charts
        col1, col2 = st.columns(2)
        
        with col1:
            if stats['daily_transcriptions']:
                st.subheader("📝 Daily Transcriptions")
                daily_df = pd.DataFrame(list(stats['daily_transcriptions'].items()), 
                                      columns=['Date', 'Count'])
                daily_df['Date'] = pd.to_datetime(daily_df['Date'])
                
                fig_daily = px.line(daily_df, x='Date', y='Count', 
                                  title="Transcriptions per Day")
                fig_daily.update_layout(height=300)
                st.plotly_chart(fig_daily, use_container_width=True)
        
        with col2:
            if stats['daily_communications']:
                st.subheader("🎙️ Daily Communications")
                comm_daily_df = pd.DataFrame(list(stats['daily_communications'].items()), 
                                           columns=['Date', 'Count'])
                comm_daily_df['Date'] = pd.to_datetime(comm_daily_df['Date'])
                
                fig_comm = px.line(comm_daily_df, x='Date', y='Count', 
                                 title="Communication Detections per Day")
                fig_comm.update_layout(height=300)
                st.plotly_chart(fig_comm, use_container_width=True)
        
        # Recent transcriptions table
        if transcription_df is not None and not transcription_df.empty:
            st.subheader("📋 Recent Transcriptions")
            recent_df = transcription_df.tail(10)[['timestamp_utc', 'flight_number', 'category', 'raw_transcription']]
            recent_df.columns = ['Timestamp', 'Flight', 'Category', 'Communication']
            st.dataframe(recent_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.header("Daily Analytics")
        
        if stats['daily_transcriptions'] or stats['daily_communications']:
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
        st.header("Communication Categories")
        
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