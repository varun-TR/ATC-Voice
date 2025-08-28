# ATC-Voice

Project Overview: ATC voice → text → analysis → dashboard.

Data Source: LiveATC (or provided sample recordings).

Pipeline:

Ingest audio

Clean & preprocess

Convert speech → text (STT model)

NLP analysis (e.g., call signs, commands, alerts)

Dashboard visualization (flight timeline, sentiment, anomalies)

Tech Stack:

Python (data pipelines, STT, NLP)

Streamlit or Dash (dashboard)

How to Run: pip install -r requirements.txt && streamlit run src/dashboard/app.py
