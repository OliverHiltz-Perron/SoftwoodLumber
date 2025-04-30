import streamlit as st
import tempfile
import os
import subprocess
import sys
import json
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Document Analysis Pipeline",
    page_icon="📄",
    layout="wide"
)

# Title and description
st.title("Document Analysis Pipeline")
st.markdown("""
This app processes documents through a pipeline:
1. Convert document to markdown using LlamaParse
2. Fix markdown formatting with Gemini AI
3. Extract propositions using Gemini AI
4. Find similar propositions in a database
""")

# API key input section
with st.expander("API Keys Configuration", expanded=True):
    st.info("API keys are required for LlamaParse and Gemini AI. They will be temporarily stored for this session only.")
    
    # Load keys from .env if available
    llama_key_default = os.getenv("LLAMA_CLOUD_API_KEY", "")
    gemini_key_default = os.getenv("GEMINI_API_KEY", "")
    
    llama_key = st.text_input("LlamaParse API Key", value=llama_key_default, type="password")
    gemini_key = st.text_input("Gemini API Key", value=gemini_key_default, type="password")

# Check for required directory and prompt files
with st.expander("System Setup", expanded=False):
    # Check for prompts directory
    prompts_dir = "prompts"
    if not os.path.exists(prompts_dir):
        if st.button("Create Prompts Directory"):
            os.makedirs(prompts_dir, exist_ok=True)
            st.success(f"Created {prompts_dir} directory")
        else:
            st.warning(f"The '{prompts_dir}' directory doesn't exist. Please create it or click the button above.")
    else:
        st.success(f"'{prompts_dir}' directory found")
    
    # Check for required prompt files
    markdown_prompt_path = os.path.join(prompts_dir, "markdown_prompt.txt")
    proposition_prompt_path = os.path.join(prompts_dir, "Proposition.md")
    
    if not os.path.exists(markdown_prompt_path):
        markdown_prompt = st.text_area("Create markdown_prompt.txt", 
                                      height=150,
                                      value="""You are an expert in formatting Markdown documents. I will provide you with a Markdown document that has formatting issues due to conversion from another format. Your task is to clean up the Markdown formatting while preserving the content.

Formatting issues to fix:
1. Remove unnecessary line breaks and merge paragraphs
2. Ensure proper heading structure (# for top-level heading, ## for second level, etc.)
3. Fix bullet point and numbered list formatting
4. Correct table formatting if tables exist
5. Fix any code block formatting issues
6. Remove redundant or repeated text
7. Fix any strange characters or encoding issues
8. Preserve emphasis (bold, italic) where appropriate
9. Remove strange formatting artifacts like excessive spaces or duplicate punctuation
10. Preserve the meaning and content of the document

Here is the Markdown content to fix:

{markdown_content}""")
        
        if st.button("Save markdown_prompt.txt"):
            os.makedirs(os.path.dirname(markdown_prompt_path), exist_ok=True)
            with open(markdown_prompt_path, "w", encoding="utf-8") as f:
                f.write(markdown_prompt)
            st.success(f"Saved {markdown_prompt_path}")
    else:
        st.success(f"'{markdown_prompt_path}' found")

    if not os.path.exists(proposition_prompt_path):
        proposition_prompt = st.text_area("Create Proposition.md", 
                                        height=150,
                                        value="""You are going to extract factual propositions from a document. A proposition is a claim that is either true or false, and that stands on its own.

A good proposition expresses a single thought, using clear and simple language, without complex structures (like negation or conditionals).

The most important thing is that propositions should be derived directly from the text - do not add new information or claims that aren't supported by the text.

For each proposition:
- Extract only factual claims (not opinions, questions, suggestions, section headers)
- Express each as a simple, clear statement
- Aim to preserve the original meaning
- Break complex statements into simpler ones
- Remove unnecessary context or conditionals
- Make the proposition standalone and context-independent

Format your answer as a semicolon-separated list of propositions. Do not include any additional text, explanations, or formatting.

Example:
Water boils at 100 degrees Celsius; Humans have 46 chromosomes; Penicillin was discovered by Alexander Fleming

If there are no substantive factual claims in the document, just respond with NA.

Here is the content:

{content}""")
        
        if st.button("Save Proposition.md"):
            os.makedirs(os.path.dirname(proposition_prompt_path), exist_ok=True)
            with open(proposition_prompt_path, "w", encoding="utf-8") as f:
                f.write(proposition_prompt)
            st.success(f"Saved {proposition_prompt_path}")
    else:
        st.success(f"'{proposition_prompt_path}' found")

# Database configuration for QueryJson
with st.expander("Database Configuration", expanded=False):
    st.info("Configure the database path for proposition similarity search")
    
    database_path = st.text_input(
        "Path to CSV database with pre-computed embeddings",
        value=os.path.join(os.getcwd(), "propositions_rows.csv")
    )
    
    threshold = st.slider("Similarity threshold", min_value=0.0, max_value=1.0, value=0.6, step=0.05)
    top_k = st.number_input("Number of top matches to return", min_value=1, max_value=10, value=3, step=1)

# File upload
uploaded_file = st.file_uploader("Upload a document (PDF, DOCX, DOC, PPTX, PPT, or HTML)", 
                               type=["pdf", "docx", "doc", "pptx", "ppt", "html"])

# Process flow control
show_intermediate = st.checkbox("Show intermediate results", value=True)
use_gpu = st.checkbox("Use GPU for QueryJson (if available)", value=True)

# Execute pipeline function
def execute_pipeline(input_file):
    if not llama_key or not gemini_key:
        st.error("Both LlamaParse and Gemini API keys are required")
        return None
    
    # Set environment variables for the subprocess
    env = os.environ.copy()
    env["LLAMA_CLOUD_API_KEY"] = llama_key
    env["GEMINI_API_KEY"] = gemini_key
    
    # Temporary files for intermediate results
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as markdown_file, \
         tempfile.NamedTemporaryFile(suffix=".md", delete=False) as fixed_markdown_file, \
         tempfile.NamedTemporaryFile(suffix=".json", delete=False) as propositions_file, \
         tempfile.NamedTemporaryFile(suffix=".json", delete=False) as final_output_file:
        
        markdown_path = markdown_file.name
        fixed_markdown_path = fixed_markdown_file.name
        propositions_path = propositions_file.name
        output_path = final_output_file.name
        
        try:
            # Step 1: Convert document to markdown using LlamaParse
            st.write("Step 1: Converting document to markdown...")
            progress_bar = st.progress(0)
            
            llamaparse_cmd = f"python llamaparse_converter.py -i \"{input_file}\" -o \"{markdown_path}\""
            process = subprocess.Popen(
                llamaparse_cmd, 
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor process
            while process.poll() is None:
                progress_bar.progress(0.25)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error(f"LlamaParse conversion failed: {stderr}")
                return None
            
            progress_bar.progress(0.25)
            
            # Show intermediate result if enabled
            if show_intermediate:
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
                with st.expander("Markdown Output (Step 1)", expanded=False):
                    st.markdown(markdown_content)
            
            # Step 2: Fix markdown formatting with Gemini AI
            st.write("Step 2: Fixing markdown formatting...")
            
            markdown_fixer_cmd = f"python markdown_fixer.py -i \"{markdown_path}\" -o \"{fixed_markdown_path}\" --prompt \"{markdown_prompt_path}\""
            process = subprocess.Popen(
                markdown_fixer_cmd, 
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while process.poll() is None:
                progress_bar.progress(0.5)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error(f"Markdown fixing failed: {stderr}")
                return None
            
            progress_bar.progress(0.5)
            
            # Show intermediate result if enabled
            if show_intermediate:
                with open(fixed_markdown_path, 'r', encoding='utf-8') as f:
                    fixed_markdown_content = f.read()
                with st.expander("Fixed Markdown (Step 2)", expanded=False):
                    st.markdown(fixed_markdown_content)
            
            # Step 3: Extract propositions using Gemini AI
            st.write("Step 3: Extracting propositions...")
            
            propositions_cmd = f"python propositions.py -i \"{fixed_markdown_path}\" -o \"{propositions_path}\" --prompt \"{proposition_prompt_path}\""
            process = subprocess.Popen(
                propositions_cmd, 
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while process.poll() is None:
                progress_bar.progress(0.75)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error(f"Proposition extraction failed: {stderr}")
                return None
            
            progress_bar.progress(0.75)
            
            # Show intermediate result if enabled
            if show_intermediate:
                with open(propositions_path, 'r', encoding='utf-8') as f:
                    propositions_content = json.load(f)
                with st.expander("Extracted Propositions (Step 3)", expanded=False):
                    st.json(propositions_content)
            
            # Step 4: Find similar propositions in database
            st.write("Step 4: Finding similar propositions...")
            
            # Add GPU flag if selected
            gpu_flag = "--use_gpu" if use_gpu else "--no_gpu"
            
            queryjson_cmd = f"python QueryJson.py -i \"{propositions_path}\" -o \"{output_path}\" -d \"{database_path}\" --threshold {threshold} --top_k {top_k} {gpu_flag}"
            process = subprocess.Popen(
                queryjson_cmd, 
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while process.poll() is None:
                progress_bar.progress(0.9)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error(f"QueryJson failed: {stderr}")
                return None
            
            progress_bar.progress(1.0)
            
            # Read the final output
            with open(output_path, 'r', encoding='utf-8') as f:
                final_output = json.load(f)
                
            return final_output
                
        finally:
            # Clean up temporary files
            for temp_file in [markdown_path, fixed_markdown_path, propositions_path, output_path]:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    st.warning(f"Error removing temporary file {temp_file}: {e}")

# Process button
if uploaded_file is not None:
    # Save the uploaded file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix="." + uploaded_file.name.split(".")[-1]) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        input_filepath = tmp_file.name
    
    if st.button("Process Document"):
        with st.spinner("Processing document... This may take several minutes depending on document size."):
            try:
                final_output = execute_pipeline(input_filepath)
                
                if final_output:
                    st.success("Processing complete!")
                    
                    # Display final output
                    with st.expander("Final Output", expanded=True):
                        st.json(final_output)
                    
                    # Provide download link
                    download_json = json.dumps(final_output, indent=2)
                    st.download_button(
                        label="Download Results as JSON",
                        data=download_json,
                        file_name="document_analysis_results.json",
                        mime="application/json"
                    )
            except Exception as e:
                st.error(f"An error occurred during processing: {str(e)}")
            finally:
                # Clean up the temporary input file
                if os.path.exists(input_filepath):
                    os.unlink(input_filepath)
else:
    st.info("Please upload a document to begin processing")

# Footer
st.markdown("---")
st.markdown("Document Analysis Pipeline Tool")