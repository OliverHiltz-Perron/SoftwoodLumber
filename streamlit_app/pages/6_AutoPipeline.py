import streamlit as st
import sys
import os
import json
import tempfile
import time
from pathlib import Path
import subprocess
import datetime
import logging
import shutil

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import utilities for shared file storage
from streamlit_app.utils import (
    advanced_file_selector, 
    save_json_file,
    save_markdown_file,
    get_all_files_by_type,
    MARKDOWN_DIR,
    FIXED_MARKDOWN_DIR,
    PROPOSITIONS_DIR,
    ENHANCED_PROPS_DIR
)

# Import tools from our source directory
try:
    from src.markdown_fixer import MarkdownFixer
    from src.Propositions import extract_filename, find_text_for_proposition, read_file_content
    markdown_fixer_imported = True
except ImportError:
    markdown_fixer_imported = False

st.set_page_config(
    page_title="Automated Pipeline - Softwood Lumber",
    page_icon="🌲",
    layout="wide"
)

st.title("🚀 Automated Processing Pipeline")

st.markdown("""
## Complete PDF-to-Propositions Pipeline

This tool automates the entire document processing workflow:
1. **PDF to Markdown Conversion** - Convert PDF files to markdown format
2. **Markdown Fixing** - Clean up and standardize markdown formatting
3. **Proposition Extraction** - Identify key claims and statements about softwood lumber
4. **Proposition Embedding** - Generate embeddings for semantic search

Upload your PDF files to begin the automated process.
""")

# Setup logging
def