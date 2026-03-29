#!/usr/bin/env python3
"""
Memory Monitor for ATC Voice System
Monitors system memory and provides warnings/cleanup when memory is low
"""

import psutil
import time
import sys
import gc
import os

def get_memory_info():
    """Get current memory usage information."""
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return {
        'total_mb': memory.total / (1024 * 1024),
        'available_mb': memory.available / (1024 * 1024),
        'percent_used': memory.percent,
        'swap_percent': swap.percent,
        'swap_used_mb': swap.used / (1024 * 1024)
    }

def check_memory_health():
    """Check if system memory is healthy."""
    info = get_memory_info()
    
    # Critical if less than 500MB available or swap > 80%
    if info['available_mb'] < 500 or info['swap_percent'] > 80:
        return 'critical', info
    # Warning if less than 1GB available or swap > 60%
    elif info['available_mb'] < 1024 or info['swap_percent'] > 60:
        return 'warning', info
    else:
        return 'healthy', info

def force_garbage_collection():
    """Force Python garbage collection."""
    gc.collect()

def main():
    print("🔍 ATC Voice System Memory Monitor")
    print("=" * 50)
    print("Monitoring system memory...")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    warning_count = 0
    critical_count = 0
    
    while True:
        try:
            status, info = check_memory_health()
            
            if status == 'critical':
                critical_count += 1
                print(f"🚨 CRITICAL: Low memory detected!")
                print(f"   Available: {info['available_mb']:.0f} MB")
                print(f"   Memory used: {info['percent_used']:.1f}%")
                print(f"   Swap used: {info['swap_percent']:.1f}%")
                
                # Force garbage collection
                force_garbage_collection()
                print("   ♻️  Forced garbage collection")
                
                if critical_count > 3:
                    print("⚠️  System has been in critical state for too long!")
                    print("   Consider:")
                    print("   1. Restarting the system")
                    print("   2. Adding more RAM or swap space")
                    print("   3. Reducing concurrent processes")
                
            elif status == 'warning':
                warning_count += 1
                if warning_count % 6 == 0:  # Print every minute (10s * 6)
                    print(f"⚠️  Warning: Memory getting low")
                    print(f"   Available: {info['available_mb']:.0f} MB")
                    print(f"   Memory used: {info['percent_used']:.1f}%")
                    print(f"   Swap used: {info['swap_percent']:.1f}%")
                
            else:
                # Reset counters when healthy
                if warning_count > 0 or critical_count > 0:
                    print(f"✅ Memory back to healthy levels")
                    print(f"   Available: {info['available_mb']:.0f} MB")
                warning_count = 0
                critical_count = 0
            
            time.sleep(10)  # Check every 10 seconds
            
        except KeyboardInterrupt:
            print("\n\n🛑 Memory monitor stopped")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error monitoring memory: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

