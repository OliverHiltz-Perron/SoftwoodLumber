import streamlit as st
import sys
import os
import tempfile
import json
from pathlib import Path

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

st.title("🔄 Markdown to JSON Converter")

st.markdown("""
This tool converts Markdown files to structured JSON data.
Upload your Markdown files and the tool will create JSON records with metadata.
""")

# Check for required environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize session state for API key if not already set
if 'gemini_api_key' not in st.session_state:
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# API Key input section
st.subheader("API Key Configuration")
api_key_option = st.radio(
    "Choose Gemini API key source:",
    ["Use key from .env file", "Enter API key manually"],
    index=0 if st.session_state.gemini_api_key else 1,
    key="json_gemini_key_option"
)

if api_key_option == "Enter API key manually":
    st.session_state.gemini_api_key = st.text_input(
        "Enter your Gemini API key:", 
        value=st.session_state.gemini_api_key,
        type="password",
        help="Your API key will not be stored permanently, only for this session.",
        key="json_gemini_key_input"
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
            from src.markdown_to_json import MarkdownProcessor
            import google.generativeai as genai
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
        # Load prompt template
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'prompts', 'markdown_to_json.txt')
        
        prompt_template = None
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
                st.success("Loaded prompt template from prompts/markdown_to_json.txt")
            except Exception as e:
                st.warning(f"Could not read prompt template file: {str(e)}. Using default prompt.")
        
        if not prompt_template:
            prompt_template = """You are to help convert the provided markdown content into a structured JSON document with the following fields:

1. Article Title: The title of the article, report or document
2. File_ID: Leave this blank, it will be filled in by the system
3. File_name: Leave this blank, it will be filled in by the system
4. Author: The author(s) of the document
5. Author_organization: The organization(s) associated with the author(s)
6. Publication year: The year the document was published
7. Keywords: A list of keywords that accurately represent the content
8. TLDR_summary: A concise summary of the document in 2-3 sentences
9. Focus_area: The primary subject or topic areas of the document as a list
10. Participating company/organization names: Any companies or organizations mentioned in the document as participants or stakeholders, as a list
11. Hyperlinks_Internal: Any internal hyperlinks in the document
12. Hyperlinks_External: Any external hyperlinks in the document
13. Hyperlink_Other: Any other hyperlinks that don't clearly fall into internal or external

Format your response as a valid, properly formatted JSON object."""
            st.info("Using default markdown to JSON prompt. To customize, create prompts/markdown_to_json.txt.")
        
        # Option to view/edit prompt template
        show_prompt = st.checkbox("Show/Edit Prompt Template", key="json_show_prompt")
        if show_prompt:
            prompt_template = st.text_area("Prompt Template", prompt_template, height=300, key="json_prompt_template")
        
        # Model selection
        model_options = [
            "gemini-2.0-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-pro"
        ]
        model_name = st.selectbox("Select Gemini Model", model_options, key="json_model_name")
        
        # File uploader widget
        uploaded_files = st.file_uploader("Upload Markdown files", type=["md"], accept_multiple_files=True)
        
        if uploaded_files:
            if st.button("Convert to JSON"):
                # Initialize MarkdownProcessor
                with st.spinner(f"Initializing MarkdownProcessor with {model_name}..."):
                    try:
                        processor = MarkdownProcessor(st.session_state.gemini_api_key)
                        # Override the model name
                        processor.model = genai.GenerativeModel(model_name)
                        st.success(f"MarkdownProcessor initialized with {model_name}")
                    except Exception as e:
                        st.error(f"Error initializing MarkdownProcessor: {str(e)}")
                        st.stop()
                
                # Create temporary directory for output
                output_dir = tempfile.mkdtemp()
                
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
                        # Read the content of the uploaded file
                        content = uploaded_file.getvalue().decode('utf-8')
                        
                        # Extract filename with no extension
                        base_name = os.path.splitext(uploaded_file.name)[0]
                        
                        # Save markdown content to a temporary file
                        temp_file_path = os.path.join(output_dir, uploaded_file.name)
                        with open(temp_file_path, "w", encoding='utf-8') as f:
                            f.write(content)
                        
                        # Output JSON path
                        output_json_path = os.path.join(output_dir, f"{base_name}.json")
                        
                        # Convert markdown to JSON
                        with st.spinner(f"Converting {uploaded_file.name} to JSON..."):
                            # Using our processor instance directly
                            processor.process_markdown_file(temp_file_path, output_json_path, prompt_template)
                            
                            # Check if JSON was created
                            if os.path.exists(output_json_path):
                                st.success(f"Successfully converted {uploaded_file.name} to JSON")
                                successful_files.append((uploaded_file.name, f"{base_name}.json"))
                            else:
                                st.warning(f"Failed to create JSON for {uploaded_file.name}")
                    
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                
                # Complete the progress bar
                progress_bar.progress(1.0)
                status_text.text("Processing complete!")
                
                # Display results
                if successful_files:
                    st.subheader("Generated JSON Files")
                    
                    # Create ZIP archive for download
                    import zipfile
                    import io
                    
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for _, json_name in successful_files:
                            json_path = os.path.join(output_dir, json_name)
                            if os.path.isfile(json_path):
                                zip_file.write(json_path, json_name)
                    
                    # Provide download link for the ZIP file
                    zip_buffer.seek(0)
                    st.download_button(
                        label="Download All JSON Files (ZIP)",
                        data=zip_buffer,
                        file_name="json_files.zip",
                        mime="application/zip",
                        key="download_all_json_zip"
                    )
                    
                    # Show preview of each JSON file
                    for md_name, json_name in successful_files:
                        json_path = os.path.join(output_dir, json_name)
                        try:
                            with open(json_path, 'r', encoding='utf-8') as f:
                                json_content = json.load(f)
                            
                            with st.expander(f"{md_name} → {json_name}"):
                                # Show formatted JSON
                                st.json(json_content)
                                
                                # Format for download
                                json_str = json.dumps(json_content, indent=2)
                                
                                # Individual file download
                                st.download_button(
                                    label=f"Download {json_name}",
                                    data=json_str,
                                    file_name=json_name,
                                    mime="application/json",
                                    key=f"download_json_{json_name}"
                                )
                        except Exception as e:
                            st.error(f"Error reading {json_name}: {str(e)}")
                else:
                    st.warning("No files were successfully converted to JSON.")
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
