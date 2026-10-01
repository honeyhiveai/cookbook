import sys
from pathlib import Path

# The provider is a single module at the cookbook root, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
