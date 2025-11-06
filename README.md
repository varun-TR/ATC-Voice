# 🛫 CATSR (ATC Voice) Live Communications Dashboard

## 📌 Project Overview
This project is part of the **GMU DAEN Capstone (Fall 2025)** and focuses on building an **Air Traffic Control (ATC) Voice Communications Dashboard**.  
The system ingests live or recorded ATC audio, converts it into text using Speech-to-Text (STT) models, applies Natural Language Processing (NLP) for analysis, and visualizes insights in an interactive dashboard.

<img width="1613" height="812" alt="image" src="https://github.com/user-attachments/assets/f876c232-bd39-477b-ac7d-d5b78e5f695c" />


---

## 🎯 Objectives
- Ingest and process **ATC audio recordings** (e.g., LiveATC streams).  
- Apply **Speech-to-Text (STT)** models such as Whisper, Vosk, or Azure Speech SDK.  
- Perform **NLP analysis** (keyword spotting, call sign detection, anomaly detection).  
- Develop a **real-time dashboard** to visualize:
  - Transcripts
  - Communication timelines
  - Flight activity summaries
  - Alerts/anomalies  

---

## 🏗️ Repository Structure
atc-voice-dashboard/
│── README.md

│── .gitignore

│── requirements.txt # Python dependencies

│── src/ 

│ ├── data_ingestion/ # Scripts to fetch/stream ATC audio (LiveATC, etc.)

│ ├── preprocessing/ # Audio cleaning, segmentation

│ ├── speech_to_text/ # STT pipeline (Whisper, Vosk, or Azure Speech SDK)

│ ├── nlp_analysis/ # Keyword spotting, topic modeling, anomaly detection

│ ├── dashboard/ # Streamlit app for visualization
│ │   └── app.py
│ ├── pipeline/  # Simple, stable API for processing modules (re-exports)
│ └── utils/ # Helper functions (logging, config)

│── notebooks/ # Jupyter/EDA experiments

│── data/ # Sample data (small clips, transcripts)

│── tests/ # Unit tests

│── docs/ # Project docs & capstone deliverables


---

## ⚙️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/atc-voice-dashboard.git
   cd atc-voice-dashboard
   
## Create a virtual environment & activate it:

python3 -m venv venv
source venv/bin/activate   # On macOS/Linux

venv\Scripts\activate      # On Windows


## 🧰 Tech Stack

Programming: Python

Audio Processing: pydub, librosa (TBD)

Speech-to-Text: OpenAI Whisper / Vosk / Azure Speech SDK (TBD)

NLP: Hugging Face Transformers, spaCy (TBD)

Dashboard: Streamlit

Data Handling: Pandas, NumPy

Optional Deployment: Docker (TBD)


## 📊 Deliverables

✅ Final Project Report

✅ Capstone Showcase Presentation

✅ GitHub Repository (this repo)

✅ Working Dashboard Prototype

## 🚀 Quick Start

**Run the dashboard with your existing data:**
```bash
./run_dashboard_simple.sh
```

This will:
- ✅ Use your existing transcription data (`categorized_transcription_results.json`)
- ✅ Use your existing communication logs (`atc_communications.txt`)
- ✅ Display live analytics and visualizations
- ✅ Show all requested features: categorization, daily counts, statistics, patterns

**Or manually:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
pip install streamlit pandas numpy plotly

# Run dashboard
streamlit run src/dashboard/app.py
```

**Access:** http://localhost:8501

## 📊 Dashboard Features

The dashboard displays:
- **Communication Categorization**: Frequency handoffs, heading vectors, altitude clearances, emergency declarations, miscellaneous
- **Daily Analytics**: Communication counts, statistics, trends
- **Category Analysis**: Distribution charts and breakdowns
- **Pattern Analysis**: Hourly patterns, flight activity, timing analysis
- **Live Data**: Reads from your existing data files automatically

## 📜 License

This project is released under the Apache 2.0 License unless otherwise specified by the partner.

