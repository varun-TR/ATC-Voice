#!/usr/bin/env python3
"""
ATC Communications Detection Script
Wrapper to run the main logext.py from the correct location
"""

import sys
import os
from pathlib import Path

# Change to the data_ingestion directory for proper execution
current_dir = Path(__file__).parent
data_ingestion_dir = current_dir / "src" / "data_ingestion"

if __name__ == "__main__":
    try:
        # Change to the data_ingestion directory
        os.chdir(data_ingestion_dir)
        
        # Execute the logext.py script directly
        exec(open('logext.py').read())
    except Exception as e:
        print(f"❌ Error running logext: {e}")
        sys.exit(1)
