import streamlit as st
import sys
import os
import tempfile
from pathlib import Path

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

st.title("🧹 Markdown Formatting Fixer")

st.markdown("""
This tool fixes formatting issues in Markdown files using Gemini AI.
Upload your Markdown files and the tool will clean them up and provide downloadable results.
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
    key="gemini_key_option"
)

if api_key_option == "Enter API key manually":
    st.session_state.gemini_api_key = st.text_input(
        "Enter your Gemini API key:", 
        value=st.session_state.gemini_api_key,
        type="password",
        help="Your API key will not be stored permanently, only for this session."
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
            from src.markdown_fixer import MarkdownFixer
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
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'prompts', 'markdown_prompt.txt')
        
        default_prompt = """You are a master editor focused on improving the formatting and readability of raw, poorly formatted markdown content. You will be provided with markdown text that may have formatting issues, inconsistencies, or structural problems.

Your task is to clean up and fix the markdown formatting while preserving ALL of the original content and meaning. Focus on:

1. Fixing heading structures (proper hierarchy of #, ##, ###)
2. Ensuring proper spacing between paragraphs
3. Fixing list formatting (bullets, numbering)
4. Properly formatting code blocks, tables, and quotes
5. Fixing obvious spelling or grammar errors
6. Maintaining all original hyperlinks
7. Preserving all original content (don't remove any information)

Return ONLY the cleaned markdown with no additional explanations, comments, or discussions.

Here's the markdown content to clean:

{markdown_content}"""
        
        prompt_template = default_prompt
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
                st.success("Loaded prompt template from prompts/markdown_prompt.txt")
            except Exception as e:
                st.warning(f"Could not read prompt template file: {str(e)}. Using default prompt.")
        else:
            st.info("Using default prompt template. To customize, create a file at 'prompts/markdown_prompt.txt'.")
        
        # Option to view/edit prompt template
        show_prompt = st.checkbox("Show/Edit Prompt Template")
        if show_prompt:
            prompt_template = st.text_area("Prompt Template", prompt_template, height=300)
            st.info("Note: The placeholder '{markdown_content}' will be replaced with the uploaded markdown content.")
        
        # File uploader widget
        uploaded_files = st.file_uploader("Upload Markdown files", type=["md"], accept_multiple_files=True)
        
        if uploaded_files:
            if st.button("Fix Markdown Formatting"):
                # Initialize MarkdownFixer
                with st.spinner("Initializing Gemini..."):
                    try:
                        fixer = MarkdownFixer(st.session_state.gemini_api_key)
                        st.success("Gemini API initialized successfully")
                    except Exception as e:
                        st.error(f"Error initializing Gemini API: {str(e)}")
                        st.stop()
                
                # Create temporary directory for output
                output_dir = tempfile.mkdtemp()
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Track successful fixes
                successful_files = []
                
                # Process each uploaded file
                for i, uploaded_file in enumerate(uploaded_files):
                    file_progress = (i / len(uploaded_files))
                    progress_bar.progress(file_progress)
                    status_text.text(f"Processing {uploaded_file.name}... ({i+1}/{len(uploaded_files)})")
                    
                    try:
                        # Read the content of the uploaded file
                        content = uploaded_file.getvalue().decode('utf-8')
                        
                        # Fix markdown formatting
                        with st.spinner(f"Fixing formatting for {uploaded_file.name}..."):
                            cleaned_markdown = fixer.fix_markdown_with_gemini(content, prompt_template)
                            
                            if cleaned_markdown:
                                # Create the fixed filename with _fixed suffix
                                base_name, ext = os.path.splitext(uploaded_file.name)
                                fixed_filename = f"{base_name}_fixed{ext}"
                                
                                # Save to output directory
                                output_path = os.path.join(output_dir, fixed_filename)
                                with open(output_path, 'w', encoding='utf-8') as f:
                                    f.write(cleaned_markdown)
                                st.success(f"Successfully fixed formatting for {uploaded_file.name}")
                                successful_files.append((uploaded_file.name, fixed_filename))
                            else:
                                st.warning(f"No changes made to {uploaded_file.name}")
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                
                # Complete the progress bar
                progress_bar.progress(1.0)
                status_text.text("Processing complete!")
                
                # Display results
                if successful_files:
                    st.subheader("Fixed Markdown Files")
                    
                    # Check if any files were processed
                    md_files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
                    
                    if md_files:
                        # Create ZIP archive for download
                        import zipfile
                        import io
                        
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            for file_name in md_files:
                                file_path = os.path.join(output_dir, file_name)
                                if os.path.isfile(file_path):
                                    zip_file.write(file_path, file_name)
                        
                        # Provide download link for the ZIP file
                        zip_buffer.seek(0)
                        st.download_button(
                            label="Download All Fixed Files (ZIP)",
                            data=zip_buffer,
                            file_name="fixed_markdown_files.zip",
                            mime="application/zip",
                            key="download_all_md"
                        )
                        
                        # Show preview of each file with diff
                        for original_name, fixed_name in successful_files:
                            fixed_path = os.path.join(output_dir, fixed_name)
                            try:
                                with open(fixed_path, 'r', encoding='utf-8') as f:
                                    fixed_content = f.read()
                                
                                # Find the original file in uploaded_files
                                original_content = None
                                for uploaded_file in uploaded_files:
                                    if uploaded_file.name == original_name:
                                        original_content = uploaded_file.getvalue().decode('utf-8')
                                        break
                                
                                with st.expander(f"{original_name} → {fixed_name}"):
                                    # Show tabs for original, fixed, and diff
                                    tab1, tab2 = st.tabs(["Fixed Version", "Original Version"])
                                    
                                    with tab1:
                                        st.markdown(fixed_content[:1000] + "..." if len(fixed_content) > 1000 else fixed_content)
                                    
                                    with tab2:
                                        if original_content:
                                            st.markdown(original_content[:1000] + "..." if len(original_content) > 1000 else original_content)
                                        else:
                                            st.warning("Original content not available for comparison")
                                    
                                    # Individual file download
                                    st.download_button(
                                        label=f"Download {fixed_name}",
                                        data=fixed_content,
                                        file_name=fixed_name,
                                        mime="text/markdown",
                                        key=f"download_fixed_{fixed_name}"
                                    )
                            except Exception as e:
                                st.error(f"Error reading {fixed_name}: {str(e)}")
                    else:
                        st.warning("No files were processed successfully.")
                else:
                    st.warning("No files were successfully fixed.")
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
