#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.15"
# dependencies = [
#   "edge-tts>=7.3.1",
#   "jsonschema>=4.23",
#   "numpy>=1.26",
#   "pillow>=13.0.0",
#   "playwright>=1.45",
#   "pymupdf>=1.24",
#   "pyyaml>=6.0",
#   "python-pptx>=1.0",
#   "scipy>=1.11",
#   "static-ffmpeg>=3.0",
#   "tzdata>=2025.2",
# ]
# ///
"""slide2video: turn a slide deck into narrated study videos. Run with --help."""
import sys

from lv.cli import main

if __name__ == "__main__":
    sys.exit(main())
