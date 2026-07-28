import os
import sys

# Add src folder to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.main import main

if __name__ == "__main__":
    main()