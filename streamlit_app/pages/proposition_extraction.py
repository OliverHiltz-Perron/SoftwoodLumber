import streamlit as st
import sys
import os
import tempfile
import json
import glob
import logging
import datetime
import time
from pathlib import Path
from backend.proposition_extractor import PropositionExtractionService

# Add the parent directory to sys.path so we can import from backend/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import utilities for shared file storage
from streamlit_app.utils import (
    advanced_file_selector, 
    save_json_file, 
    get_all_files_by_type,
    FIXED_MARKDOWN_DIR,
    PROPOSITIONS_DIR
)

# Import the backend processing functions
from backend.proposition_extractor import (
    setup_logging,
    read_file_content,
    extract_filename,
    find_text_for_proposition,
    call_gemini,
    process_file,
    save_proposition_results,
    get_default_prompt_template
)

st.set_page_config(
    page_title="Proposition Extractor - Softwood Lumber",
    page_icon="🌲",
    layout="wide"
)

st.title("📋 Proposition Extractor")

st.markdown("""
This tool extracts key propositions from documents related to the softwood lumber industry.
Upload your Markdown files, and the tool will identify important statements and claims about wood, timber, lumber, or forestry products.
""")

# Check for required environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize session state for API key if not already set
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

# API Key input section
st.subheader("API Key Configuration")
api_key_option = st.radio(
    "Choose Gemini API key source:",
    ["Use key from .env file", "Enter API key manually"],
    index=0 if st.session_state.gemini_api_key else 1,
    key="prop_gemini_key_option"
)

if api_key_option == "Enter API key manually":
    st.session_state.gemini_api_key = st.text_input(
        "Enter your Gemini API key:", 
        value=st.session_state.gemini_api_key,
        type="password",
        help="Your API key will not be stored permanently, only for this session.",
        key="prop_gemini_key_input"
    )
else:
    # Try to get from .env file
    if not st.session_state.gemini_api_key:
        st.warning("⚠️ GEMINI_API_KEY not found in .env file. You can enter it manually instead.")

# Check if we have a valid API key to proceed
if st.session_state.gemini_api_key:
    # Try importing the required modules
    with st.spinner("Loading required modules..."):
        try:
            import google.generativeai as genai
            modules_loaded = True
        except ImportError as e:
            modules_loaded = False
            st.error(f"Failed to import required modules: {str(e)}")
            st.markdown("""
            Make sure you have installed all required dependencies:
            ```
            pip install -r requirements.txt
            ```
            """)
    
    if modules_loaded:
        # Initialize logging
        log_file_path = setup_logging()
        
        # Load prompt template - adjust paths to match your structure
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prompts', 'Proposition.md')
        
        prompt_template = None
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
                st.success("Loaded prompt template from prompts/Proposition.md")
            except Exception as e:
                st.warning(f"Could not read prompt template file: {str(e)}. Using default prompt.")
        
        if not prompt_template:
            prompt_template = get_default_prompt_template()
            st.info("Using default proposition extraction prompt. To customize, create prompts/Proposition.md.")
        
        # Option to view/edit prompt template
        show_prompt = st.checkbox("Show/Edit Prompt Template", key="prop_show_prompt")
        if show_prompt:
            prompt_template = st.text_area("Prompt Template", prompt_template, height=300, key="prop_prompt_template")
            st.info("Note: The placeholder '{content}' will be replaced with the markdown content.")
        
        # Model selection
        model_options = [
            "gemini-2.5-flash-preview-04-17",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-pro"
        ]
        model_name = st.selectbox("Select Gemini Model", model_options)
        
        # File selection tabs
        source_tab = st.radio("Select File Source", ["Upload Files", "Use Existing Files"])
        
        files_to_process = []
        
        if source_tab == "Upload Files":
            # File uploader widget
            uploaded_files = st.file_uploader("Upload Markdown files", type=["md"], accept_multiple_files=True)
            
            if uploaded_files:
                # Create a temporary directory for the uploaded files
                temp_dir = tempfile.mkdtemp()
                
                # Save the uploaded files to the temp directory
                for uploaded_file in uploaded_files:
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    files_to_process.append(file_path)
                
                if files_to_process:
                    st.success(f"Loaded {len(files_to_process)} files for processing")
        else:
            # Use existing markdown files
            st.subheader("Select Existing Files")
            
            # Radio button to choose file source
            file_source = st.radio(
                "Select which markdown files to use:",
                ["Fixed Markdown Files", "Raw Markdown Files", "Select Individual Files"]
            )
            
            if file_source == "Fixed Markdown Files":
                # Get all fixed markdown files
                fixed_md_files = get_all_files_by_type("fixed_markdown")
                
                if fixed_md_files:
                    for file_path, file_name, _ in fixed_md_files:
                        files_to_process.append(file_path)
                    st.success(f"Found {len(files_to_process)} fixed markdown files for processing")
                else:
                    st.warning("No fixed markdown files found. Process some files with the Markdown Fixer first.")
            
            elif file_source == "Raw Markdown Files":
                # Get all raw markdown files
                raw_md_files = get_all_files_by_type("markdown")
                
                if raw_md_files:
                    for file_path, file_name, _ in raw_md_files:
                        files_to_process.append(file_path)
                    st.success(f"Found {len(files_to_process)} raw markdown files for processing")
                else:
                    st.warning("No raw markdown files found. Upload some files first.")
            
            elif file_source == "Select Individual Files":
                # Allow user to select multiple files
                with st.expander("Select Files"):
                    all_md_files = get_all_files_by_type("markdown") + get_all_files_by_type("fixed_markdown")
                    
                    if not all_md_files:
                        st.warning("No markdown files found in any directory.")
                    else:
                        # Group files by directory
                        files_by_dir = {}
                        for file_path, file_name, dir_name in all_md_files:
                            if dir_name not in files_by_dir:
                                files_by_dir[dir_name] = []
                            files_by_dir[dir_name].append((file_path, file_name))
                        
                        # Create checkboxes for each file
                        selected_files = []
                        
                        for dir_name, files in files_by_dir.items():
                            st.subheader(f"{dir_name}")
                            
                            for file_path, file_name in files:
                                if st.checkbox(file_name, key=f"select_{file_path}"):
                                    selected_files.append(file_path)
                        
                        if selected_files:
                            files_to_process = selected_files
                            st.success(f"Selected {len(files_to_process)} files for processing")
        
        # Process button and output area
        if files_to_process:
            temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.1, 
                                  help="Lower values produce more deterministic outputs")
            
            max_tokens = st.number_input("Max Output Tokens", min_value=1000, max_value=100000, value=65536, 
                                       help="Maximum number of tokens for Gemini response")
            
            if st.button("Extract Propositions"):
                # Initialize Gemini
                try:
                    genai.configure(api_key=st.session_state.gemini_api_key)
                    model = genai.GenerativeModel(model_name)
                    st.success(f"Gemini {model_name} initialized successfully")
                except Exception as e:
                    st.error(f"Error initializing Gemini API: {str(e)}")
                    st.stop()
                
                # Create progress display
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Initialize the JSON results structure
                results = []
                metadata = {
                    "documentId": "metadata",
                    "generatedDate": datetime.datetime.now().isoformat(),
                    "tool": "Streamlit Proposition Extractor",
                    "model": model_name,
                    "generationParams": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens
                    },
                    "type": "metadata"
                }
                results.append(metadata)
                
                # Process each file
                success_count = 0
                error_count = 0
                
                # Create callbacks for progress updates
                def update_status(text):
                    status_text.text(text)
                
                def update_progress(value):
                    progress_bar.progress(value)
                
                for i, file_path in enumerate(files_to_process):
                    # Update progress
                    progress = (i / len(files_to_process))
                    update_progress(progress)
                    update_status(f"Processing {os.path.basename(file_path)}... ({i+1}/{len(files_to_process)})")
                    
                    try:
                        if process_file(
                            file_path, 
                            prompt_template, 
                            model_name, 
                            st.session_state.gemini_api_key, 
                            results,
                            status_callback=update_status,
                            progress_callback=update_progress,
                            temperature=temperature,
                            max_tokens=max_tokens
                        ):
                            success_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        logging.exception(f"Error processing {file_path}: {str(e)}")
                        st.error(f"Error processing {os.path.basename(file_path)}: {str(e)}")
                
                # Complete the progress bar
                progress_bar.progress(1.0)
                status_text.text(f"Processing complete! {success_count} files processed successfully, {error_count} failed.")
                
                # Save results
                combined_json_path = save_proposition_results(results)
                
                # Display results
                if len(results) > 1:  # More than just metadata
                    st.subheader("Extracted Propositions")
                    
                    # Read the combined JSON for display
                    with open(combined_json_path, 'r', encoding='utf-8') as f:
                        json_content = f.read()
                    
                    # Provide download link for the combined JSON
                    st.download_button(
                        label="Download All Propositions (JSON)",
                        data=json_content,
                        file_name=os.path.basename(combined_json_path),
                        mime="application/json",
                        key="download_all_json"
                    )
                    
                    # Display results for each document
                    for doc in results:
                        if doc.get("documentId") != "metadata":
                            with st.expander(f"{doc['filename']} - {len(doc.get('propositions', []))} propositions"):
                                if doc.get("status") == "NOT_RELEVANT":
                                    st.info("This document was not relevant to the wood industry.")
                                else:
                                    # Display each proposition
                                    for prop in doc.get("propositions", []):
                                        st.markdown(f"**Proposition {prop['id']}**: {prop['text']}")
                                        st.markdown(f"*Source context:* {prop['sourceText']}")
                                        st.divider()
                                        
                                # Add download link for individual file
                                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "propositions")
                                doc_json_path = os.path.join(output_dir, f"{os.path.splitext(doc['filename'])[0]}_propositions.json")
                                if os.path.exists(doc_json_path):
                                    with open(doc_json_path, 'r', encoding='utf-8') as f:
                                        doc_json_content = f.read()
                                    
                                    st.download_button(
                                        label=f"Download propositions for {doc['filename']}",
                                        data=doc_json_content,
                                        file_name=f"{os.path.splitext(doc['filename'])[0]}_propositions.json",
                                        mime="application/json",
                                        key=f"download_json_{doc['documentId']}"
                                    )
                else:
                    st.warning("No propositions were extracted from any documents.")
else:
    st.error("Please provide a valid Gemini API key to proceed.")
    
    # Add information about how to get an API key
    st.markdown("""
    ### How to get a Gemini API Key
    
    1. Go to the [Google AI Studio](https://makersuite.google.com/)
    2. Sign in with your Google account
    3. Create or access your API key in the settings
    4. Copy the key and paste it above
    
    You can either enter the key manually each time or add it to a `.env` file in the project root:
    ```
    GEMINI_API_KEY=your_api_key_here
    ```
    """)