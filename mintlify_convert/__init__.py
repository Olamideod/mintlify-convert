"""
Mintlify Convert - Convert MDX documentation to Mintlify format
"""

__version__ = "2.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .converter import MintlifyConverter
from .cli import main
from .navigation import generate_enhanced_mint_json
from .utils import process_file, process_directory

__all__ = [
    "MintlifyConverter",
    "main",
    "generate_enhanced_mint_json", 
    "process_file",
    "process_directory",
]
