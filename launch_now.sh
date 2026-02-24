#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 yolo26_complete_system.py
