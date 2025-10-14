#!/bin/bash

# ATC Voice Data Verification Script

echo "🔍 ATC Voice Data Verification"
echo "=============================="

cd /home/atc_voice/ATC-Voice

echo ""
echo "📊 Data File Status:"
echo "-------------------"

# Check transcription results
if [ -f "src/data/logs/transcripts/transcription_results.json" ]; then
    ORIGINAL_COUNT=$(python3 -c "
import json
with open('src/data/logs/transcripts/transcription_results.json', 'r') as f:
    data = json.load(f)
print(len(data['items']))
")
    echo "✅ Raw transcriptions: $ORIGINAL_COUNT items"
else
    echo "❌ Raw transcriptions: File not found"
fi

# Check categorized results
if [ -f "src/data/logs/transcripts/categorized_transcription_results.json" ]; then
    CATEGORIZED_COUNT=$(python3 -c "
import json
with open('src/data/logs/transcripts/categorized_transcription_results.json', 'r') as f:
    data = json.load(f)
print(len(data['items']))
")
    echo "✅ Categorized transcriptions: $CATEGORIZED_COUNT items"
else
    echo "❌ Categorized transcriptions: File not found"
fi

# Check communications
if [ -f "src/data/logs/atc_communications.txt" ]; then
    COMM_COUNT=$(wc -l < src/data/logs/atc_communications.txt)
    echo "✅ Communications: $COMM_COUNT entries"
else
    echo "❌ Communications: File not found"
fi

echo ""
echo "🔍 Duplicate Check:"
echo "------------------"

# Check for duplicates in categorized data
python3 -c "
import json
with open('src/data/logs/transcripts/categorized_transcription_results.json', 'r') as f:
    data = json.load(f)

items = data['items']
chunk_nums = [item.get('chunk_number') for item in items]
unique_chunks = set(chunk_nums)

print(f'Total items: {len(items)}')
print(f'Unique chunk numbers: {len(unique_chunks)}')

if len(unique_chunks) == len(items):
    print('✅ No duplicates detected')
else:
    print(f'❌ Duplicates detected: {len(items) - len(unique_chunks)} duplicate items')
    
    # Find duplicate chunk numbers
    from collections import Counter
    chunk_counts = Counter(chunk_nums)
    duplicates = [chunk for chunk, count in chunk_counts.items() if count > 1]
    print(f'Duplicate chunk numbers: {duplicates}')
"

echo ""
echo "📈 Category Distribution:"
echo "-------------------------"
python3 -c "
import json
import pandas as pd

with open('src/data/logs/transcripts/categorized_transcription_results.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data['items'])
print(df['category'].value_counts().to_string())
"

echo ""
echo "✈️ Airline Distribution:"
echo "------------------------"
python3 -c "
import json
import pandas as pd

with open('src/data/logs/transcripts/categorized_transcription_results.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data['items'])
print(df['airline'].value_counts().to_string())
"

echo ""
echo "✅ Verification complete!"
