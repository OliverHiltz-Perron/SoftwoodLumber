import streamlit as st
import tempfile
import os
import subprocess
import sys
import json
from dotenv import load_dotenv
import time
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Softwood Lumber Board Document Checker 🌲",
    page_icon="🌲",
    layout="wide"
)

# Title and description
# Custom CSS for SLB branding
st.markdown("""
<style>
    /* Primary SLB branding color */
    :root {
        --primary-color: #7fbc41;
        --text-on-primary: #FFFFFF;
    }
    
    /* Header styling */
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* Make the title stand out with SLB branding */
    h1 {
        color: var(--primary-color);
        padding: 1rem 0;
    }
    
    /* Style the app container */
    .reportview-container {
        background-color: #f9f9f9;
    }
    
    /* Style buttons with SLB green */
    .stButton>button {
        background-color: var(--primary-color);
        color: var(--text-on-primary);
        border: none;
    }
    
    .stButton>button:hover {
        background-color: #6da437;
        color: var(--text-on-primary);
    }
    
    /* Style progress bars */
    .stProgress > div > div > div {
        background-color: var(--primary-color);
    }
    
    /* Style info boxes */
    .stAlert {
        border-left-color: var(--primary-color);
    }
</style>
""", unsafe_allow_html=True)

# Load and display SLB logo
st.image("SLB-LOGO.PNG", width=200)

# Title and description with tree emoji
st.title("Softwood Lumber Board Document Checker 🌲")
st.markdown("""
<div style="background-color: #7fbc41; padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
    <p style="color: white; margin: 0; font-size: 1.1rem;">
        This tool analyzes documents related to the wood industry. Upload a document to extract key information, find related data in our database, and generate proper citations.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
This app processes documents through a pipeline:
1. Convert document to markdown using LlamaParse
2. Fix markdown formatting with Gemini AI
3. Extract propositions using Gemini AI
4. Find similar propositions in a database using nomic-v2 embeddings
5. Select best citations using OpenAI
""")
# Create sidebar for configuration
st.sidebar.image("SLB-LOGO.PNG", width=150)
st.sidebar.title("Configuration")
st.sidebar.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# API key input section in sidebar
st.sidebar.markdown("""
<div style="background-color: #7fbc41; padding: 0.5rem; border-radius: 0.3rem; margin-bottom: 0.5rem;">
    <p style="color: white; margin: 0; font-weight: bold;">API Keys</p>
</div>
""", unsafe_allow_html=True)

# Load keys from .env if available
llama_key_default = os.getenv("LLAMA_CLOUD_API_KEY", "")
gemini_key_default = os.getenv("GEMINI_API_KEY", "")
openai_key_default = os.getenv("OPENAI_API_KEY", "")

# Move API input fields to sidebar
llama_key = st.sidebar.text_input("LlamaParse API Key", value=llama_key_default, type="password")
gemini_key = st.sidebar.text_input("Gemini API Key", value=gemini_key_default, type="password")
openai_key = st.sidebar.text_input("OpenAI API Key", value=openai_key_default, type="password")

# Configuration options
st.sidebar.markdown("""
<div style="background-color: #7fbc41; padding: 0.5rem; border-radius: 0.3rem; margin: 1.5rem 0 0.5rem 0;">
    <p style="color: white; margin: 0; font-weight: bold;">Options</p>
</div>
""", unsafe_allow_html=True)

# Process flow control in sidebar (removing GPU option)
show_intermediate = st.sidebar.checkbox("Show intermediate results", value=True)

# The use_gpu variable still needs to be defined for the code to work
# but we'll hide it from the UI
use_gpu = True  # default to True, but hide from UI

# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; color: #666666; font-size: 0.8rem;">
    <p>Softwood Lumber Board</p>
    <p>Document Analysis Tool</p>
</div>
""", unsafe_allow_html=True)
# API key input section
# with st.expander("API Keys Configuration", expanded=True):
#     st.info("API keys are required for LlamaParse, Gemini AI, and OpenAI. They will be temporarily stored for this session only.")
    
#     # Load keys from .env if available
#     llama_key_default = os.getenv("LLAMA_CLOUD_API_KEY", "")
#     gemini_key_default = os.getenv("GEMINI_API_KEY", "")
#     openai_key_default = os.getenv("OPENAI_API_KEY", "")
    
#     llama_key = st.text_input("LlamaParse API Key", value=llama_key_default, type="password")
#     gemini_key = st.text_input("Gemini API Key", value=gemini_key_default, type="password")
#     openai_key = st.text_input("OpenAI API Key", value=openai_key_default, type="password")

# Hidden configuration - automatically create needed files and folders
prompts_dir = "prompts"
if not os.path.exists(prompts_dir):
    os.makedirs(prompts_dir, exist_ok=True)

# Set up prompt files without showing to user
markdown_prompt_path = os.path.join(prompts_dir, "markdown_prompt.txt")
proposition_prompt_path = os.path.join(prompts_dir, "Proposition.md")

# Create markdown prompt file if it doesn't exist
if not os.path.exists(markdown_prompt_path):
    markdown_prompt = """You are an expert in formatting Markdown documents. I will provide you with a Markdown document that has formatting issues due to conversion from another format. Your task is to clean up the Markdown formatting while preserving the content.

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

{markdown_content}"""
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(markdown_prompt_path), exist_ok=True)
    with open(markdown_prompt_path, "w", encoding="utf-8") as f:
        f.write(markdown_prompt)

# Create proposition prompt file if it doesn't exist
if not os.path.exists(proposition_prompt_path):
    proposition_prompt = """You are an expert analyst specializing in the wood industry. Your task is to extract comprehensive, self-contained propositions from text that relate to any aspect of the wood industry ecosystem. Here is the text you need to analyze: 

<text>
{content}
</text>

Analysis Process

Relevance Assessment:
Determine if the text contains information relevant to the wood industry (forestry, timber, manufacturing, construction, markets, sustainability, etc.). If NO relevant content exists, respond only with "NA".
Proposition Extraction Guidelines:
For relevant text, extract propositions following these strict requirements:

Each proposition must be completely self-contained with all necessary context
Include full identification of subjects (organizations, competitions, initiatives)
Specify exact names, dates, locations, and numerical data when present
Ensure propositions can stand independently without reference to other text
Capture complete cause-effect relationships
Include relevant qualifiers, conditions, and industry-specific context
Replace all pronouns and vague references with specific entities
Preserve industry terminology with sufficient context for understanding


Content Requirements:
Each proposition must:

Contain factual, objective information directly from the text
Include all relevant context needed for full understanding
Maintain the specific details that provide value (measurements, percentages, timeframes)
Fully identify all entities, organizations, and initiatives
Specify geographic regions, wood species, or market segments when mentioned
Avoid document-specific references (e.g., "As shown in Table 2")
Form grammatically complete statements


Output Format:
Present only the extracted propositions separated by semicolons. Include ONLY the propositions themselves or "NA" if the text is irrelevant. Do not include any commentary, numbering, or additional text.

Examples of Properly Formatted Propositions:
POOR: "The competition promotes sustainability."
GOOD: "The Timber in the City Competition sponsored by the Softwood Lumber Board promotes using sustainable timber construction methods to create healthy urban living environments."
POOR: "The report shows increased production last year."
GOOD: "The American Hardwood Export Council's 2023 industry report showed a 14% increase in hardwood production across North American mills between 2021-2022, with oak and maple accounting for 65% of total output."
POOR: "Companies are investing in new technology."
GOOD: "Leading wood processing companies including West Fraser and Canfor invested $3.2 billion in advanced sawmill technology in 2022 to improve yield efficiency by an average of 8% while reducing waste material by 12% compared to traditional processing methods."
POOR: "The regulations affect timber imports."
GOOD: "The European Union Timber Regulation (EUTR) implemented in January 2023 requires all imported wood products to undergo enhanced documentation proving legal harvesting, resulting in a 22% increase in compliance costs for North American exporters according to the International Wood Products Association."
Remember: Extract ONLY the propositions without any additional text, separating each with a semicolon. If the text is not relevant to the wood industry, respond only with "NA"."""
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(proposition_prompt_path), exist_ok=True)
    with open(proposition_prompt_path, "w", encoding="utf-8") as f:
        f.write(proposition_prompt)

# Hidden database configuration
database_path = os.path.join(os.getcwd(), "propositions_rows.csv")
threshold = 0.6
top_k = 3

# Main content area - File upload section
st.markdown("""
<div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 0.5rem; border: 1px solid #e9ecef; margin: 1rem 0;">
    <h3 style="color: #7fbc41; margin-top: 0;">Document Upload 📄</h3>
    <p>Please upload your document to begin analysis. Supported formats: PDF, DOCX, DOC, PPTX, PPT, or HTML.</p>
</div>
""", unsafe_allow_html=True)

# File upload with styled container
uploaded_file = st.file_uploader("Upload a document", 
                              type=["pdf", "docx", "doc", "pptx", "ppt", "html"])


# Execute pipeline function
def execute_pipeline(input_file, doc_id):
    if not llama_key or not gemini_key or not openai_key:
        st.error("LlamaParse, Gemini, and OpenAI API keys are all required")
        return None
    
    # Set environment variables for the subprocess
    env = os.environ.copy()
    env["LLAMA_CLOUD_API_KEY"] = llama_key
    env["GEMINI_API_KEY"] = gemini_key
    env["OPENAI_API_KEY"] = openai_key
    
    # Temporary files for intermediate results
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as markdown_file, \
         tempfile.NamedTemporaryFile(suffix=".md", delete=False) as fixed_markdown_file, \
         tempfile.NamedTemporaryFile(suffix=".json", delete=False) as propositions_file, \
         tempfile.NamedTemporaryFile(suffix=".json", delete=False) as queryjson_output_file, \
         tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as citations_file:
        
        markdown_path = markdown_file.name
        fixed_markdown_path = fixed_markdown_file.name
        propositions_path = propositions_file.name
        queryjson_output_path = queryjson_output_file.name
        citations_path = citations_file.name
        
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
                progress_bar.progress(0.2)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error("LlamaParse conversion failed")
                return None
            
            progress_bar.progress(0.2)
            
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
                progress_bar.progress(0.4)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error("Markdown fixing failed")
                return None
            
            progress_bar.progress(0.4)
            
            # Show intermediate result if enabled
            if show_intermediate:
                with open(fixed_markdown_path, 'r', encoding='utf-8') as f:
                    fixed_markdown_content = f.read()
                with st.expander("Fixed Markdown (Step 2)", expanded=False):
                    st.markdown(fixed_markdown_content)
            
            # Step 3: Extract propositions using Gemini AI
            st.write("Step 3: Extracting propositions...")
            
            propositions_cmd = f"python propositions.py -i \"{fixed_markdown_path}\" -o \"{propositions_path}\" --prompt \"{proposition_prompt_path}\" --doc-id \"{doc_id}\""
            process = subprocess.Popen(
                propositions_cmd, 
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while process.poll() is None:
                progress_bar.progress(0.6)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error("Proposition extraction failed")
                return None
            
            progress_bar.progress(0.6)
            
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
            
            queryjson_cmd = f"python QueryJson.py -i \"{propositions_path}\" -o \"{queryjson_output_path}\" -d \"{database_path}\" --threshold {threshold} --top_k {top_k} {gpu_flag}"
            process = subprocess.Popen(
                queryjson_cmd, 
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while process.poll() is None:
                progress_bar.progress(0.8)  # Indicate process is running
                time.sleep(1)
            
            returncode = process.wait()
            stdout, stderr = process.communicate()
            
            if returncode != 0:
                st.error("QueryJson processing failed")
                return None
            
            progress_bar.progress(0.8)
            
            # Show intermediate result if enabled
            if show_intermediate:
                with open(queryjson_output_path, 'r', encoding='utf-8') as f:
                    queryjson_output = json.load(f)
                with st.expander("Similar Propositions (Step 4)", expanded=False):
                    st.json(queryjson_output)
            
            # Step 5: Select best citations
            st.write("Step 5: Selecting best citations...")
            
            citation_cmd = f"python citation.py --input \"{queryjson_output_path}\" --output \"{citations_path}\""
            process = subprocess.Popen(
                citation_cmd, 
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
                st.error("Citation selection failed")
                st.error(f"Error: {stderr}")
                return None
            
            progress_bar.progress(1.0)
            
            # Read the QueryJson output and citations CSV
            with open(queryjson_output_path, 'r', encoding='utf-8') as f:
                queryjson_output = json.load(f)
                
            citations_df = pd.read_csv(citations_path)
                
            # Return both outputs
            return {
                "queryjson_output": queryjson_output,
                "citations_df": citations_df
            }
                
        finally:
            # Clean up temporary files
            for temp_file in [markdown_path, fixed_markdown_path, propositions_path, queryjson_output_path, citations_path]:
                try:
                    if os.path.exists(temp_file):
                        # Instead of trying to delete immediately, give processes time to release the file
                        # We'll try a few times with a delay between attempts
                        for attempt in range(3):
                            try:
                                os.unlink(temp_file)
                                break  # Success, exit the retry loop
                            except Exception:
                                # If failed, wait a moment before trying again
                                time.sleep(1)
                                if attempt == 2:  # Last attempt
                                    # Just log this to stderr but don't show to user
                                    print(f"Could not remove temporary file {temp_file}", file=sys.stderr)
                except Exception:
                    # Silently continue if cleanup fails - don't show errors to user
                    pass

# Process button
# Process button styling
# Process button
if uploaded_file is not None:
    # Save the uploaded file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix="." + uploaded_file.name.split(".")[-1]) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        input_filepath = tmp_file.name
    
    # Extract document ID from filename - first 10 characters
    doc_id = uploaded_file.name[:10]
    st.write(f"Document ID: **{doc_id}**")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        process_button = st.button("Process Document 🌲", use_container_width=True)
    
    if process_button:
        with st.spinner("Processing document... This may take several minutes depending on document size."):
            try:
                results = execute_pipeline(input_filepath, doc_id)
                
                if results:
                    st.success("Processing complete!")
                    
                    # Display QueryJson output
                    with st.expander("Query Results (Step 4)", expanded=False):
                        st.json(results["queryjson_output"])
                    
                    # Display Citations output
                    with st.expander("Citation Results (Step 5)", expanded=True):
                        st.dataframe(results["citations_df"])
                    
                    # Create a function to download both files
                    def download_all_files():
                        # Save both files to temporary locations
                        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as json_file, \
                             tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as csv_file, \
                             tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as zip_file:
                            
                            # Write the JSON results
                            json_path = json_file.name
                            with open(json_path, 'w', encoding='utf-8') as f:
                                json.dump(results["queryjson_output"], f, indent=2)
                            
                            # Write the CSV results
                            csv_path = csv_file.name
                            results["citations_df"].to_csv(csv_path, index=False)
                            
                            # Create a zip file containing both files
                            import zipfile
                            zip_path = zip_file.name
                            with zipfile.ZipFile(zip_path, 'w') as zipf:
                                zipf.write(json_path, arcname="query_results.json")
                                zipf.write(csv_path, arcname="best_citations.csv")
                            
                            # Read the zip file for download
                            with open(zip_path, 'rb') as f:
                                return f.read()
                            
                    # Create single download button for both files
                    st.download_button(
                        label="Download All Results",
                        data=download_all_files(),
                        file_name="document_analysis_results.zip",
                        mime="application/zip"
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
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 0;">
    <div style="color: #666666; font-size: 0.8rem;">
        Softwood Lumber Board Document Checker 🌲
    </div>
    <div style="color: #7fbc41; font-weight: bold; font-size: 0.9rem;">
        SLB &copy; 2025
    </div>
</div>
""", unsafe_allow_html=True)