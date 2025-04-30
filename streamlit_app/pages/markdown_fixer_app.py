# pages/markdown_fixer_app.py

import streamlit as st
import os
import sys
import time
import glob
import tempfile

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.markdown_fixer_service import MarkdownFixerService
from streamlit_app.utils import display_shared_data_status, advanced_file_selector

st.set_page_config(
    page_title="Markdown Fixer",
    page_icon="🔧",
    layout="wide"
)

# Display shared data status in sidebar
display_shared_data_status()

st.title("🔧 Markdown Fixer")

st.markdown("""
This tool cleans and improves markdown formatting using the Gemini API.

**Features:**
- Fixes formatting issues in Markdown files
- Improves readability and structure
- Works with Markdown files from any source, including those converted from PDFs
""")

# Initialize the MarkdownFixerService
@st.cache_resource
def get_markdown_fixer_service():
    try:
        return MarkdownFixerService()
    except ValueError as e:
        st.error(f"Error initializing Markdown Fixer: {str(e)}")
        st.info("Please set up your GEMINI_API_KEY in the .env file.")
        return None

markdown_fixer_service = get_markdown_fixer_service()

if markdown_fixer_service:
    # Set up the output directory
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fixed_markdown")
    os.makedirs(output_dir, exist_ok=True)
    
    # Input selection method
    input_method = st.radio(
        "Choose input method:",
        ["Upload Markdown File", "Select Existing Markdown File", "Process Directory"]
    )
    
    if input_method == "Upload Markdown File":
        uploaded_file = st.file_uploader(
            "Upload a markdown file to fix", 
            type=["md"]
        )
        
        if uploaded_file is not None:
            st.info(f"Processing {uploaded_file.name}...")
            
            # Save uploaded file to temporary file
            temp_file = os.path.join(tempfile.gettempdir(), uploaded_file.name)
            with open(temp_file, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            if st.button("Fix Markdown"):
                with st.spinner("Fixing markdown formatting..."):
                    try:
                        # Read original content for comparison
                        with open(temp_file, "r", encoding="utf-8") as f:
                            original_content = f.read()
                        
                        # Fix the markdown
                        output_path = os.path.join(output_dir, uploaded_file.name)
                        success = markdown_fixer_service.process_markdown_file(temp_file, output_path)
                        
                        if success:
                            st.success(f"Successfully fixed markdown formatting!")
                            
                            # Read the fixed content
                            with open(output_path, "r", encoding="utf-8") as f:
                                fixed_content = f.read()
                            
                            # Display comparison
                            col1, col2 = st.columns(2)
                            with col1:
                                st.subheader("Original Markdown")
                                st.text_area("", original_content, height=400)
                            
                            with col2:
                                st.subheader("Fixed Markdown")
                                st.text_area("", fixed_content, height=400)
                            
                            # Download button
                            st.download_button(
                                label=f"Download Fixed Markdown",
                                data=fixed_content,
                                file_name=uploaded_file.name,
                                mime="text/markdown"
                            )
                        else:
                            st.warning("No significant changes were made to the markdown.")
                    except Exception as e:
                        st.error(f"Error during markdown fixing: {str(e)}")
                    finally:
                        # Clean up
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
    
    elif input_method == "Select Existing Markdown File":
        file_path = advanced_file_selector(
            "Select a markdown file to fix:",
            file_types=[".md"]
        )
        
        if file_path:
            st.info(f"Selected file: {os.path.basename(file_path)}")
            
            if st.button("Fix Markdown"):
                with st.spinner("Fixing markdown formatting..."):
                    try:
                        # Read original content for comparison
                        with open(file_path, "r", encoding="utf-8") as f:
                            original_content = f.read()
                        
                        # Fix the markdown
                        output_path = os.path.join(output_dir, os.path.basename(file_path))
                        success = markdown_fixer_service.process_markdown_file(file_path, output_path)
                        
                        if success:
                            st.success(f"Successfully fixed markdown formatting!")
                            
                            # Read the fixed content
                            with open(output_path, "r", encoding="utf-8") as f:
                                fixed_content = f.read()
                            
                            # Display comparison
                            col1, col2 = st.columns(2)
                            with col1:
                                st.subheader("Original Markdown")
                                st.text_area("", original_content, height=400)
                            
                            with col2:
                                st.subheader("Fixed Markdown")
                                st.text_area("", fixed_content, height=400)
                            
                            # Download button
                            st.download_button(
                                label=f"Download Fixed Markdown",
                                data=fixed_content,
                                file_name=os.path.basename(file_path),
                                mime="text/markdown"
                            )
                        else:
                            st.warning("No significant changes were made to the markdown.")
                    except Exception as e:
                        st.error(f"Error during markdown fixing: {str(e)}")
    
    elif input_method == "Process Directory":
        st.info("Select a directory containing markdown files to fix.")
        
        # Directory selection - would need implementation in utils.py
        # For now, provide a text input
        dir_path = st.text_input("Enter directory path:")
        
        if dir_path and os.path.isdir(dir_path):
            st.info(f"Selected directory: {dir_path}")
            
            if st.button("Process Directory"):
                with st.spinner("Processing files in directory..."):
                    try:
                        processed_files = markdown_fixer_service.process_directory(dir_path, output_dir)
                        
                        if processed_files:
                            st.success(f"Processing complete! Fixed {len(processed_files)} markdown file(s).")
                            
                            for file_path in processed_files:
                                filename = os.path.basename(file_path)
                                with st.expander(f"Preview: {filename}"):
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        st.markdown(f.read()[:1000] + "...")
                        else:
                            st.warning("No markdown files were processed. The directory may not contain markdown files.")
                    except Exception as e:
                        st.error(f"Error during processing: {str(e)}")
        elif dir_path:
            st.error(f"Directory not found: {dir_path}")

    # Display recently fixed files
    st.subheader("Recently Fixed Files")
    
    if os.path.exists(output_dir):
        md_files = glob.glob(os.path.join(output_dir, "*.md"))
        
        if md_files:
            # Sort by modification time (newest first)
            md_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            for file_path in md_files[:5]:  # Show 5 most recent files
                filename = os.path.basename(file_path)
                mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
                
                with st.expander(f"{filename} (Last modified: {mod_time})"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    
                    st.markdown(file_content[:1000] + "..." if len(file_content) > 1000 else file_content)
                    
                    st.download_button(
                        label=f"Download {filename}",
                        data=file_content,
                        file_name=filename,
                        mime="text/markdown"
                    )
        else:
            st.info("No fixed files yet.")
else:
    st.error("Markdown Fixer service is not available. Please check your API key configuration.")