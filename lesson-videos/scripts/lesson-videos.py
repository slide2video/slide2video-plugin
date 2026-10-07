#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "edge-tts>=7.2.8",
#   "numpy>=1.26",
#   "pillow>=10.0",
#   "playwright>=1.45",
#   "pymupdf>=1.24",
#   "python-pptx>=1.0",
#   "scipy>=1.11",
#   "static-ffmpeg>=3.0",
# ]
# ///
"""lesson-videos: turn a slide deck into narrated study videos. Run with --help."""
import sys

from lv.cli import main

if __name__ == "__main__":
    sys.exit(main())
