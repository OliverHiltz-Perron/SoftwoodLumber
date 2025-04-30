# pages/pdf_to_markdown.py

import streamlit as st
import os
import sys
import time
import glob
# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llamaparse_service import LlamaParseService
from streamlit_app.utils import display_shared_data_status, advanced_file_selector

st.set_page_config(
    page_title="PDF to Markdown Converter",
    page_icon="📄",
    layout="wide"
)

# Display shared data status in sidebar
display_shared_data_status()

st.title("📄 PDF to Markdown Converter")

st.markdown("""
This tool converts PDF documents (and other formats) to clean Markdown format using LlamaParse.

**Supported formats:**
- PDF (.pdf)
- Word Documents (.doc, .docx)
- PowerPoint Presentations (.ppt, .pptx)
- HTML Files (.html)
- ZIP Archives (containing any of the above)
""")

# Initialize the LlamaParseService
@st.cache_resource
def get_llama_parse_service():
    try:
        return LlamaParseService()
    except ValueError as e:
        st.error(f"Error initializing LlamaParse: {str(e)}")
        st.info("Please set up your LLAMA_CLOUD_API_KEY in the .env file.")
        return None

llama_parse_service = get_llama_parse_service()

if llama_parse_service:
    # Set up the output directory
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "markdown")
    os.makedirs(output_dir, exist_ok=True)
    
    # Input selection method
    input_method = st.radio(
        "Choose input method:",
        ["Upload File", "Select Existing File", "Process Directory"]
    )
    
    if input_method == "Upload File":
        uploaded_file = st.file_uploader(
            "Upload a document to convert", 
            type=llama_parse_service.get_supported_extensions()[:-1]  # Exclude .zip from display
        )
        
        # Also allow ZIP files
        uploaded_zip = st.file_uploader(
            "Or upload a ZIP archive containing multiple documents", 
            type=["zip"]
        )
        
        if uploaded_file is not None:
            st.info(f"Processing {uploaded_file.name}...")
            
            # Save uploaded file to temporary file
            temp_file = os.path.join(tempfile.gettempdir(), uploaded_file.name)
            with open(temp_file, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            if st.button("Convert to Markdown"):
                with st.spinner("Converting file to Markdown..."):
                    try:
                        created_files = llama_parse_service.process_file(temp_file, output_dir)
                        
                        if created_files:
                            st.success(f"Conversion complete! Created {len(created_files)} Markdown file(s).")
                            
                            for file_path in created_files:
                                filename = os.path.basename(file_path)
                                with open(file_path, "r", encoding="utf-8") as f:
                                    file_content = f.read()
                                
                                with st.expander(f"Preview: {filename}"):
                                    st.markdown(file_content[:1000] + "..." if len(file_content) > 1000 else file_content)
                                    
                                    st.download_button(
                                        label=f"Download {filename}",
                                        data=file_content,
                                        file_name=filename,
                                        mime="text/markdown"
                                    )
                        else:
                            st.warning("No Markdown files were created. The document may be empty or unsupported.")
                    except Exception as e:
                        st.error(f"Error during conversion: {str(e)}")
                    finally:
                        # Clean up
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
        
        elif uploaded_zip is not None:
            st.info(f"Processing ZIP archive: {uploaded_zip.name}...")
            
            # Save uploaded ZIP to temporary file
            temp_file = os.path.join(tempfile.gettempdir(), uploaded_zip.name)
            with open(temp_file, "wb") as f:
                f.write(uploaded_zip.getbuffer())
            
            if st.button("Extract and Convert to Markdown"):
                with st.spinner("Extracting and converting files..."):
                    try:
                        created_files = llama_parse_service.process_zip(temp_file, output_dir)
                        
                        if created_files:
                            st.success(f"Conversion complete! Created {len(created_files)} Markdown file(s).")
                            
                            for file_path in created_files:
                                filename = os.path.basename(file_path)
                                with open(file_path, "r", encoding="utf-8") as f:
                                    file_content = f.read()
                                
                                with st.expander(f"Preview: {filename}"):
                                    st.markdown(file_content[:1000] + "..." if len(file_content) > 1000 else file_content)
                        else:
                            st.warning("No Markdown files were created. The ZIP archive may not contain supported documents.")
                    except Exception as e:
                        st.error(f"Error during conversion: {str(e)}")
                    finally:
                        # Clean up
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
    
    elif input_method == "Select Existing File":
        file_path = advanced_file_selector(
            "Select a file to convert:",
            file_types=llama_parse_service.get_supported_extensions()
        )
        
        if file_path:
            st.info(f"Selected file: {os.path.basename(file_path)}")
            
            if st.button("Convert to Markdown"):
                with st.spinner("Converting file to Markdown..."):
                    try:
                        if file_path.lower().endswith('.zip'):
                            created_files = llama_parse_service.process_zip(file_path, output_dir)
                        else:
                            created_files = llama_parse_service.process_file(file_path, output_dir)
                        
                        if created_files:
                            st.success(f"Conversion complete! Created {len(created_files)} Markdown file(s).")
                            
                            for file_path in created_files:
                                filename = os.path.basename(file_path)
                                with open(file_path, "r", encoding="utf-8") as f:
                                    file_content = f.read()
                                
                                with st.expander(f"Preview: {filename}"):
                                    st.markdown(file_content[:1000] + "..." if len(file_content) > 1000 else file_content)
                        else:
                            st.warning("No Markdown files were created. The file may be empty or unsupported.")
                    except Exception as e:
                        st.error(f"Error during conversion: {str(e)}")
    
    elif input_method == "Process Directory":
        st.info("Select a directory containing documents to convert.")
        
        # Directory selection - would need implementation in utils.py
        # For now, provide a text input
        dir_path = st.text_input("Enter directory path:")
        
        if dir_path and os.path.isdir(dir_path):
            st.info(f"Selected directory: {dir_path}")
            
            if st.button("Process Directory"):
                with st.spinner("Processing files in directory..."):
                    try:
                        created_files = llama_parse_service.process_directory(dir_path, output_dir)
                        
                        if created_files:
                            st.success(f"Conversion complete! Created {len(created_files)} Markdown file(s).")
                            
                            for file_path in created_files:
                                filename = os.path.basename(file_path)
                                with st.expander(f"Preview: {filename}"):
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        st.markdown(f.read()[:1000] + "...")
                        else:
                            st.warning("No Markdown files were created. The directory may not contain supported documents.")
                    except Exception as e:
                        st.error(f"Error during processing: {str(e)}")
        elif dir_path:
            st.error(f"Directory not found: {dir_path}")

    # Display recently converted files
    st.subheader("Recently Converted Files")
    
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
            st.info("No converted files yet.")
else:
    st.error("LlamaParse service is not available. Please check your API key configuration.")