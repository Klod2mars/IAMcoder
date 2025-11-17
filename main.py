#!/usr/bin/env python3
"""
AIHomeCoder - Point d'entrée principal
"""
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from presentation.cli import main

if __name__ == "__main__":
    main()

