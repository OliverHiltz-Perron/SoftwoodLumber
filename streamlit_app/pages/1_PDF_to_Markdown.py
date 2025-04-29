import streamlit as st
import sys
import os
import tempfile
from pathlib import Path

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the utilities for shared file storage
from streamlit_app.utils import save_uploaded_file, save_markdown_file, advanced_file_selector, display_shared_data_status
from streamlit_app.utils import MARKDOWN_DIR

st.title("📄 PDF to Markdown Converter")

# Display shared data status in sidebar
display_shared_data_status()

st.markdown("""
This tool converts PDF documents to clean Markdown format using LlamaParse.
Upload your PDF files and the tool will process them using LlamaParse.
""")

# Check for required environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize session state for API key if not already set
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.getenv("LLAMA_CLOUD_API_KEY", "")

# API Key input section
st.subheader("API Key Configuration")
api_key_option = st.radio(
    "Choose API key source:",
    ["Use key from .env file", "Enter API key manually"],
    index=0 if st.session_state.api_key else 1
)

if api_key_option == "Enter API key manually":
    st.session_state.api_key = st.text_input(
        "Enter your LlamaParse API key:", 
        value=st.session_state.api_key,
        type="password",
        help="Your API key will not be stored permanently, only for this session."
    )
else:
    # Try to get from .env file
    if not st.session_state.api_key:
        st.warning("⚠️ LLAMA_CLOUD_API_KEY not found in .env file. You can enter it manually instead.")

# Check if we have a valid API key to proceed
if st.session_state.api_key:
    # Try importing the required modules
    with st.spinner("Loading required modules..."):
        try:
            from llama_cloud_services import LlamaParse
            from llama_index.core import SimpleDirectoryReader
            from src.llamaparse_converter import process_and_save
            modules_loaded = True
        except ImportError as e:
            modules_loaded = False
            import_error = str(e)
            st.error(f"Failed to import required modules: {import_error}")
            st.markdown("""
            Make sure you have installed all required dependencies:
            ```
            pip install -r requirements.txt
            ```
            """)
    
    if modules_loaded:
        # File uploader widget
        uploaded_files = st.file_uploader("Upload PDF files", type=["pdf", "docx", "doc", "pptx", "ppt", "html"], accept_multiple_files=True)
        
        if uploaded_files:
            if st.button("Convert to Markdown"):
                # Initialize LlamaParse
                with st.spinner("Initializing LlamaParse..."):
                    try:
                        parser = LlamaParse(
                            api_key=st.session_state.api_key,
                            result_type="markdown",
                            verbose=True
                        )
                        file_extractor = {
                            ".pdf": parser,
                            ".docx": parser,
                            ".doc": parser,
                            ".pptx": parser,
                            ".ppt": parser,
                            ".html": parser
                        }
                        st.success("LlamaParse initialized successfully")
                    except Exception as e:
                        st.error(f"Error initializing LlamaParse: {str(e)}")
                        st.stop()
                
                # Create temporary directories for processing
                temp_dir = tempfile.mkdtemp()
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Track successful conversions
                successful_files = []
                
                # Process each uploaded file
                for i, uploaded_file in enumerate(uploaded_files):
                    file_progress = (i / len(uploaded_files))
                    progress_bar.progress(file_progress)
                    status_text.text(f"Processing {uploaded_file.name}... ({i+1}/{len(uploaded_files)})")
                    
                    try:
                        # Save the uploaded file to the temporary directory
                        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(temp_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Process the file with LlamaParse
                        with st.spinner(f"Converting {uploaded_file.name}..."):
                            reader = SimpleDirectoryReader(
                                input_files=[temp_file_path],
                                file_extractor=file_extractor
                            )
                            documents = reader.load_data()
                            
                            if documents:
                                # Use a temporary directory for process_and_save
                                temp_output_dir = tempfile.mkdtemp()
                                process_and_save(documents, temp_output_dir)
                                
                                # Save the generated markdown files to our shared storage
                                for markdown_file in os.listdir(temp_output_dir):
                                    if markdown_file.endswith('.md'):
                                        markdown_path = os.path.join(temp_output_dir, markdown_file)
                                        with open(markdown_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                        
                                        # Save to our shared storage
                                        saved_path = save_markdown_file(content, markdown_file)
                                        successful_files.append((markdown_file, saved_path))
                                
                                st.success(f"Successfully converted {uploaded_file.name}")
                            else:
                                st.warning(f"No content extracted from {uploaded_file.name}")
                    
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                
                # Complete the progress bar
                progress_bar.progress(1.0)
                status_text.text("Processing complete!")
                
                # Display results
                if successful_files:
                    st.subheader("Generated Markdown Files")
                    
                    # Check if any markdown files were created
                    if successful_files:
                        # Create ZIP archive for download
                        import zipfile
                        import io
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for file_name, file_path in successful_files:
                                if os.path.isfile(file_path):
                                    zip_file.write(file_path, file_name)
                        
                        # Provide download link for the ZIP file
                        zip_buffer.seek(0)
                        st.download_button(
                            label="Download All Markdown Files (ZIP)",
                            data=zip_buffer,
                            file_name="markdown_files.zip",
                            mime="application/zip",
                            key="download_all"
                        )
                        
                        # Show info about storage
                        st.success(f"All files have been saved to the shared storage and can be accessed from other tools.")
                        
                        # Show preview of each file
                        for file_name, file_path in successful_files:
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                with st.expander(f"{file_name}"):
                                    st.markdown(content[:500] + "..." if len(content) > 500 else content)
                                    
                                    # Individual file download
                                    st.download_button(
                                        label=f"Download {file_name}",
                                        data=content,
                                        file_name=file_name,
                                        mime="text/markdown",
                                        key=f"download_{file_name}"
                                    )
                            except Exception as e:
                                st.error(f"Error reading {file_name}: {str(e)}")
                    else:
                        st.warning("No markdown files were generated. The conversion might have failed.")
                else:
                    st.warning("No files were successfully converted.")
        
        # Option to browse existing markdown files
        st.subheader("Browse Existing Markdown Files")
        selected_file = advanced_file_selector("Select a markdown file to view:", file_types=["markdown"])
        
        if selected_file:
            try:
                with open(selected_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                st.markdown("### File Preview")
                st.markdown(content[:1000] + "..." if len(content) > 1000 else content)
                
                # Download button
                st.download_button(
                    label=f"Download {os.path.basename(selected_file)}",
                    data=content,
                    file_name=os.path.basename(selected_file),
                    mime="text/markdown"
                )
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
else:
    st.error("Please provide a valid LlamaParse API key to proceed.")
    
    # Add information about how to get an API key
    st.markdown("""
    ### How to get a LlamaParse API Key
    
    1. Sign up for an account at [LlamaIndex](https://cloud.llamaindex.ai/)
    2. Navigate to your account settings
    3. Generate a new API key
    4. Copy the key and paste it above
    
    You can either enter the key manually each time or add it to a `.env` file in the project root:
    ```
    LLAMA_CLOUD_API_KEY=your_api_key_here
    ```
    """)
