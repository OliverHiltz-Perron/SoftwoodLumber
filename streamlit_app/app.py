import streamlit as st
import sys
import os
import json

# Add the parent directory to sys.path so we can import from src/ and backend/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import utilities for shared file storage
from streamlit_app.utils import display_shared_data_status, advanced_file_selector

# Import backend services
from backend.proposition_extractor import PropositionExtractionService

st.set_page_config(
    page_title="Softwood Lumber Analysis Tool",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize backend services
proposition_service = PropositionExtractionService()

# Display shared data status in sidebar
display_shared_data_status()

# Display the homepage content
st.title("🌲 Softwood Lumber Analysis Suite")

st.markdown("""
Welcome to the Softwood Lumber Analysis Tool! This application provides several 
utilities for analyzing documents related to the softwood lumber industry.

### Available Tools
- **PDF to Markdown**: Convert PDF documents to clean Markdown format
- **Markdown Fixer**: Fix formatting issues in Markdown files
- **Proposition Extractor**: Extract key propositions from documents
- **JSON Converter**: Convert Markdown files to structured JSON data
- **Semantic Search**: Find semantically similar text using embeddings

### Getting Started
Select a tool from the sidebar to begin your analysis.

### Unified File System
This app maintains a centralized file storage system allowing seamless workflow between tools.
Files processed in any tool can be accessed directly by any other tool without downloading and re-uploading.
""")

# Check if .env file exists
env_file_exists = os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
if not env_file_exists:
    st.warning("⚠️ No .env file detected. Some features may require API keys.")

# Display information about the data directories
st.subheader("Data Storage")

# Get the data directory path
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Check if the directories exist
if os.path.exists(data_dir):
    st.success("✅ Data storage system is set up and ready to use.")
    
    # Display the directory structure
    st.code(f"""
    data/
    ├── markdown/            # Raw markdown from PDF conversion
    ├── fixed_markdown/      # Markdown after formatting fixes
    ├── json/                # JSON files from markdown conversion
    ├── propositions/        # Extracted propositions
    └── enhanced_propositions/   # Propositions with semantic search results
    """)
    
    st.info("All files stored in these directories can be accessed from any tool in the app.")
else:
    st.error("❌ Data storage system is not set up correctly.")

# Add a universal file browser to the homepage
st.subheader("File Browser")
st.markdown("Browse and preview any file processed by any tool in the app.")

view_file = advanced_file_selector("Select any file to view:", file_types=["all"])

if view_file:
    try:
        file_ext = os.path.splitext(view_file)[1].lower()
        
        if file_ext == '.json':
            # JSON file
            with open(view_file, 'r', encoding='utf-8') as f:
                view_data = json.load(f)
            
            st.success(f"Loaded {os.path.basename(view_file)}")
            
            # Display as formatted JSON
            with st.expander("View JSON Content"):
                st.json(view_data)
                
        elif file_ext == '.md':
            # Markdown file
            with open(view_file, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            st.success(f"Loaded {os.path.basename(view_file)}")
            
            # Display as markdown
            with st.expander("View Markdown Content"):
                st.markdown(md_content)
                
        else:
            # Other file type
            with open(view_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            st.success(f"Loaded {os.path.basename(view_file)}")
            
            # Display as text
            with st.expander("View File Content"):
                st.text(content[:2000] + "..." if len(content) > 2000 else content)
        
        # Provide download button
        with open(view_file, "r", encoding='utf-8') as f:
            st.download_button(
                label=f"Download {os.path.basename(view_file)}",
                data=f.read(),
                file_name=os.path.basename(view_file),
                mime="application/octet-stream"
            )
            
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")