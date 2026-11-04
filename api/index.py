"""Vercel Serverless Function entry point for FixPilot AI."""

import os
import sys

# Ensure project root is in sys.path so 'fixpilot' module resolves cleanly
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fixpilot.server import FixPilotRequestHandler


class handler(FixPilotRequestHandler):
    """Vercel Serverless Function HTTP Handler."""
    pass
