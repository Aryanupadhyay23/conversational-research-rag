import runpy
import os
import sys

# Set up project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Launch frontend app
if __name__ == "__main__" or "streamlit" in sys.modules:
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
    runpy.run_path(frontend_path, run_name="__main__")