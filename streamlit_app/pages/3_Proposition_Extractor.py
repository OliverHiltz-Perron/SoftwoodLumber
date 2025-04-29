import streamlit as st
import sys
import os
import tempfile
import json
import re
import glob
import logging
import datetime
import time
from pathlib import Path

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import utilities for shared file storage
from streamlit_app.utils import (
    advanced_file_selector, 
    save_json_file, 
    get_all_files_by_type,
    FIXED_MARKDOWN_DIR,
    PROPOSITIONS_DIR
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

# Setup logging
def setup_logging(log_file="proposition_extraction.log"):
    """Configure logging for the application."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    
    logging.info("="*50)
    logging.info(f"Starting proposition extraction")
    logging.info("="*50)
    
    return log_path

# Helper function to read file content
def read_file_content(filepath):
    """Reads the entire content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"Error: File not found at '{filepath}'")
        return None
    except Exception as e:
        st.error(f"Error reading file '{filepath}': {e}")
        return None

# Helper function to extract filename-based document ID
def extract_filename(filepath):
    """
    Extracts document ID from a filepath.
    Uses leading numbers from the filename, or first 10 characters if no numbers exist.
    """
    # Get just the base filename without extension
    base_name = os.path.basename(filepath)
    filename_without_ext = os.path.splitext(base_name)[0]
    
    # Extract leading numbers using regex
    leading_numbers = re.match(r'^(\d+)', filename_without_ext)
    
    if leading_numbers:
        # If there are leading numbers, use them as document ID
        doc_id = leading_numbers.group(1)
        logging.debug(f"Extracted document ID '{doc_id}' from filename '{base_name}'")
    else:
        # If no leading numbers, use first 10 characters (or all if < 10)
        doc_id = filename_without_ext[:10]
        logging.debug(f"No leading numbers found, using first 10 chars: '{doc_id}' from '{base_name}'")
    
    return doc_id

# Helper function to find original text for a proposition
def find_text_for_proposition(original_text, proposition):
    """Attempts to find the original text that led to a proposition.
    Returns a snippet of text containing the proposition source."""
    # Simple heuristic: Find sentences or paragraphs that contain key terms from the proposition
    
    # Split the proposition into significant words (excluding common words)
    common_words = {'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is', 'are', 'be'}
    significant_words = [word.lower() for word in proposition.split() if word.lower() not in common_words and len(word) > 3]
    
    # If no significant words, return a default message
    if not significant_words:
        return "Source context not identified"
    
    # Split the original text into paragraphs
    paragraphs = original_text.split('\n\n')
    
    best_match = None
    highest_score = 0
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        paragraph_lower = paragraph.lower()
        score = 0
        
        # Calculate how many significant words appear in this paragraph
        for word in significant_words:
            if word in paragraph_lower:
                score += 1
        
        # Calculate match percentage
        match_percentage = score / len(significant_words) if significant_words else 0
        
        # Update best match if this paragraph has a higher score
        if match_percentage > highest_score:
            highest_score = match_percentage
            best_match = paragraph
    
    # If we found a reasonable match
    if highest_score > 0.3 and best_match:
        # Truncate if too long
        if len(best_match) > 250:
            words = best_match.split()
            if len(words) > 50:
                best_match = ' '.join(words[:50]) + '...'
        return best_match.strip()
    
    return "Source context not clearly identified"

# Function to call Gemini API
def call_gemini(prompt_text, model_name, api_key, temperature=0.2, max_tokens=65536):
    """Sends the prompt to the specified Gemini model and returns the response."""
    try:
        # Configure the API key
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Initialize the Generative Model
        logging.info(f"Initializing Gemini model: {model_name}")
        model = genai.GenerativeModel(model_name)

        # Set generation config
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature
        }
        logging.debug(f"Generation config: {generation_config}")

        # Generate content
        prompt_length = len(prompt_text)
        logging.info(f"Sending prompt to Gemini (length: {prompt_length} characters)")
        
        start_time = datetime.datetime.now()
        response = model.generate_content(
            prompt_text,
            generation_config=generation_config
        )
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logging.info(f"Received response from Gemini in {duration:.2f} seconds")

        # Handle potential safety blocks or empty responses
        if not response.parts:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                error_msg = f"Call blocked due to safety settings. Reason: {response.prompt_feedback.block_reason}"
                logging.error(error_msg)
                st.error(f"Error: {error_msg}")
                return None
            else:
                logging.error("Received an empty response from the API")
                st.error("Error: Received an empty response from the API.")
                return None

        response_text = response.text
        logging.info(f"Received response of length: {len(response_text)} characters")
        return response_text

    except Exception as e:
        error_msg = f"An error occurred during the Gemini API call: {str(e)}"
        logging.exception(error_msg)
        st.error(error_msg)
        return None

# Function to process a single file
def process_file(file_path, prompt_template, model_name, api_key, all_results, status_text=None, progress_bar=None):
    """Process a single file and extract propositions."""
    # Get document ID from filename
    doc_id = extract_filename(file_path)
    logging.info(f"Processing file: {file_path} (ID: {doc_id})")
    
    if status_text:
        status_text.text(f"Processing: {os.path.basename(file_path)}")
    
    # Read the input markdown content
    input_content = read_file_content(file_path)
    if input_content is None:
        logging.error(f"Failed to read content from {file_path}")
        return False
    
    # Log file size and character count
    logging.info(f"File size: {os.path.getsize(file_path)} bytes, {len(input_content)} characters")
    
    # Create the final prompt
    try:
        placeholder = "{content}"
        if placeholder not in prompt_template:
            st.error(f"Placeholder '{placeholder}' not found in prompt template.")
            return False
            
        final_prompt = prompt_template.replace(placeholder, input_content)
    except Exception as e:
        st.error(f"An error formatting the prompt: {e}")
        return False
    
    # Call the Gemini API
    gemini_response = call_gemini(final_prompt, model_name, api_key)
    
    # Process and save the response
    if gemini_response:
        # Process the propositions for JSON format
        process_result = {
            "documentId": doc_id,
            "filename": os.path.basename(file_path),
            "processingDate": datetime.datetime.now().isoformat(),
            "propositions": []
        }
        
        # Check if the response is "NA" (not applicable)
        if gemini_response.strip() == "NA":
            logging.info(f"Document '{doc_id}' marked as not relevant to wood industry")
            if status_text:
                status_text.text(f"No propositions found for {doc_id} (not relevant to wood industry)")
            process_result["status"] = "NOT_RELEVANT"
            all_results.append(process_result)
            return True
        
        # Split the response by semicolons
        propositions = [p.strip() for p in gemini_response.split(';') if p.strip()]
        logging.info(f"Extracted {len(propositions)} propositions from {doc_id}")
        
        # Process each proposition
        for i, proposition in enumerate(propositions, 1):
            proposition_id = f"{doc_id}_{i}"
            source_text = find_text_for_proposition(input_content, proposition)
            
            process_result["propositions"].append({
                "id": proposition_id,
                "text": proposition,
                "sourceText": source_text
            })
            logging.debug(f"Added proposition {proposition_id}")
        
        process_result["status"] = "SUCCESS"
        process_result["count"] = len(propositions)
        all_results.append(process_result)
        
        if status_text:
            status_text.text(f"Processed {len(propositions)} propositions from {os.path.basename(file_path)}")
            
        return True
    else:
        logging.error(f"Failed to get response from Gemini for {doc_id}")
        
        error_result = {
            "documentId": doc_id,
            "filename": os.path.basename(file_path),
            "processingDate": datetime.datetime.now().isoformat(),
            "status": "ERROR",
            "propositions": []
        }
        all_results.append(error_result)
        return False

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
        
        # Load prompt template
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'prompts', 'Proposition.md')
        
        prompt_template = None
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
                st.success("Loaded prompt template from prompts/Proposition.md")
            except Exception as e:
                st.warning(f"Could not read prompt template file: {str(e)}. Using default prompt.")
        
        if not prompt_template:
            prompt_template = """You are analyzing a document to extract propositions related to the wood industry, lumber, timber, building with wood, or wood manufacturing.

A proposition is a declarative statement that makes a claim or assertion that can be judged as true or false. Focus on extracting key claims about wood, timber, lumber, or forestry products in construction, manufacturing, or industry.

For this task:
1. Extract ONLY propositions specifically related to wood, timber, lumber usage, or wood products.
2. Focus on statements of fact, industry trends, market conditions, technical properties, or forecasts.
3. Ignore statements that are purely descriptive and don't make clear claims.
4. Do not extract general statements that are not specifically about wood/timber/lumber.
5. Extract only complete, standalone propositions - not fragments or partial thoughts.
6. Use exact wording from the text, but make minor adjustments if needed for clarity.
7. Separate each distinct proposition with a semicolon (;).
8. If the document contains no relevant propositions about wood/lumber/timber, respond with "NA".

Here is the document to analyze:

{content}

Now extract the key propositions related to wood, timber, or lumber from this text:"""
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
                
                # Create output directory if it doesn't exist
                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "propositions")
                os.makedirs(output_dir, exist_ok=True)
                
                # Process each file
                success_count = 0
                error_count = 0
                
                for i, file_path in enumerate(files_to_process):
                    # Update progress
                    progress = (i / len(files_to_process))
                    progress_bar.progress(progress)
                    status_text.text(f"Processing {os.path.basename(file_path)}... ({i+1}/{len(files_to_process)})")
                    
                    try:
                        if process_file(
                            file_path, 
                            prompt_template, 
                            model_name, 
                            st.session_state.gemini_api_key, 
                            results,
                            status_text=status_text,
                            progress_bar=progress_bar
                        ):
                            success_count += 1
                            
                            # Save individual file result
                            doc_result = results[-1]  # Get the most recently added result
                            json_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_propositions.json"
                            output_path = os.path.join(output_dir, json_filename)
                            
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(doc_result, f, indent=2)
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        logging.exception(f"Error processing {file_path}: {str(e)}")
                        st.error(f"Error processing {os.path.basename(file_path)}: {str(e)}")
                
                # Complete the progress bar
                progress_bar.progress(1.0)
                status_text.text(f"Processing complete! {success_count} files processed successfully, {error_count} failed.")
                
                # Save the combined results JSON
                combined_json_filename = f"extracted_propositions_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                combined_json_path = os.path.join(output_dir, combined_json_filename)
                
                with open(combined_json_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2)
                
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
                        file_name=combined_json_filename,
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
