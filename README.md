# ATC-Voice

atc-voice-dashboard/
│── README.md
│── .gitignore
│── requirements.txt      # Python dependencies
│── src/                  # Core source code
│   ├── data_ingestion/   # Scripts to fetch/stream ATC audio (LiveATC, etc.)
│   ├── preprocessing/    # Audio cleaning, segmentation
│   ├── speech_to_text/   # STT pipeline (Whisper, Vosk, or Azure Speech SDK)
│   ├── nlp_analysis/     # Keyword spotting, topic modeling, anomaly detection
│   ├── dashboard/        # Streamlit/Dash app for visualization
│   └── utils/            # Helper functions (logging, config)
│── notebooks/            # Jupyter/EDA experiments
│── data/                 # Sample data (small clips, transcripts)
│── tests/                # Unit tests
│── docs/                 # Project docs & capstone deliverables

