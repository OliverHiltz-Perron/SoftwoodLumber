#!/usr/bin/env python3
import streamlit as st
import os
import sys
import json
import tempfile
import logging
from dotenv import load_dotenv
import time
import pandas as pd

# Import the propositions module
from propositions import setup_logging, read_file_content, PROMPT_FILENAME, process_content

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Markdown Embeddings Generator 📝",
    page_icon="📝",
    layout="wide"
)

# Custom CSS for branding
st.markdown("""
<style>
    /* Primary branding color */
    :root {
        --primary-color: #7fbc41;
        --text-on-primary: #FFFFFF;
    }
    
    /* Header styling */
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* Make the title stand out with branding */
    h1 {
        color: var(--primary-color);
        padding: 1rem 0;
    }
    
    /* Style the app container */
    .reportview-container {
        background-color: #f9f9f9;
    }
    
    /* Style buttons with brand green */
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

def get_asset_path(filename):
    # Check if the file exists in different possible locations
    possible_locations = [
        os.path.join("assets", filename),  # /assets/filename
        os.path.join("src", "assets", filename),  # /src/assets/filename
        os.path.join("src", filename),  # /src/filename
        filename  # /filename (root directory)
    ]
    
    for location in possible_locations:
        if os.path.exists(location):
            return location
    
    # If file not found, return None
    return None

# Load and display logo if available
logo_path = get_asset_path("SLB-LOGO.PNG")
if logo_path:
    st.image(logo_path, width=200)

# Title and description with emoji
st.title("Markdown Embeddings Generator 📝")
st.markdown("""
<div style="background-color: #7fbc41; padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
    <p style="color: white; margin: 0; font-size: 1.1rem;">
        This tool processes clean markdown files to extract propositions and generate word embeddings.
        Simply upload a markdown file to get started.
    </p>
</div>
""", unsafe_allow_html=True)

# Create sidebar for configuration
if logo_path:
    st.sidebar.image(logo_path, width=150)

st.sidebar.title("Configuration")
st.sidebar.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# API key input section in sidebar
st.sidebar.markdown("""
<div style="background-color: #7fbc41; padding: 0.5rem; border-radius: 0.3rem; margin-bottom: 0.5rem;">
    <p style="color: white; margin: 0; font-weight: bold;">API Keys</p>
</div>
""", unsafe_allow_html=True)

# Load key from .env if available
gemini_key_default = os.getenv("GEMINI_API_KEY", "")
gemini_key = st.sidebar.text_input("Gemini API Key", value=gemini_key_default, type="password")

# Show intermediate results option
st.sidebar.markdown("""
<div style="background-color: #7fbc41; padding: 0.5rem; border-radius: 0.3rem; margin: 1.5rem 0 0.5rem 0;">
    <p style="color: white; margin: 0; font-weight: bold;">Options</p>
</div>
""", unsafe_allow_html=True)

show_intermediate = st.sidebar.checkbox("Show intermediate results", value=True)

# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="text-align: center; color: #666666; font-size: 0.8rem;">
    <p>Markdown Embeddings Generator</p>
    <p>Powered by propositions.py</p>
</div>
""", unsafe_allow_html=True)

# Ensure prompts directory exists
prompts_dir = "prompts"
if not os.path.exists(prompts_dir):
    os.makedirs(prompts_dir, exist_ok=True)

# Set up prompt file if it doesn't exist
proposition_prompt_path = os.path.join(prompts_dir, "Proposition.md")
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

# Main content area - File upload section
st.markdown("""
<div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 0.5rem; border: 1px solid #e9ecef; margin: 1rem 0;">
    <h3 style="color: #7fbc41; margin-top: 0;">Markdown Upload 📄</h3>
    <p>Please upload a clean markdown file to begin processing.</p>
</div>
""", unsafe_allow_html=True)

# File upload with styled container
uploaded_file = st.file_uploader("Upload a markdown file", type=["md", "markdown", "txt"])

# Set up logging for the Streamlit app
def setup_streamlit_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("streamlit_app.log"),
            logging.StreamHandler(sys.stderr)
        ]
    )

# Process the markdown file
def process_markdown_file(file_content, doc_id, show_intermediate):
    if not gemini_key:
        st.error("Gemini API key is required")
        return None
    
    # Set environment variables for the subprocess
    os.environ["GEMINI_API_KEY"] = gemini_key
    
    # Set up logging
    setup_streamlit_logging()
    logging.info(f"Processing markdown with document ID: {doc_id}")
    
    # Get the current directory for relative paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get the prompt template path
    prompt_path = os.path.join(current_dir, "prompts", "Proposition.md")
    
    # If not found in current directory, try looking in parent directory
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(current_dir, "..", "prompts", "Proposition.md")
    
    logging.info(f"Using prompt template at: {prompt_path}")
    prompt_template = read_file_content(prompt_path)
    
    if prompt_template is None:
        logging.error(f"Failed to read prompt template")
        st.error("Failed to read proposition prompt template")
        return None
    
    # Show the markdown content if intermediate results are enabled
    if show_intermediate:
        with st.expander("Markdown Content", expanded=False):
            st.markdown(file_content)
    
    # Process the content
    try:
        result = process_content(file_content, doc_id, prompt_template)
        logging.info(f"Processing complete. Extracted {len(result.get('propositions', []))} propositions")
        return result
    except Exception as e:
        logging.exception(f"Error processing content: {e}")
        st.error(f"Error processing content: {str(e)}")
        return None

# Process button
if uploaded_file is not None:
    # Read the file content
    file_content = uploaded_file.getvalue().decode("utf-8")
    
    # Extract document ID from filename (first 10 characters or entire filename without extension)
    doc_id = os.path.splitext(uploaded_file.name)[0]
    if len(doc_id) > 10:
        doc_id = doc_id[:10]
    
    st.write(f"Document ID: **{doc_id}**")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        process_button = st.button("Generate Embeddings 📊", use_container_width=True)
    
    if process_button:
        with st.spinner("Processing markdown... This may take a minute or two."):
            # Process the file
            result = process_markdown_file(file_content, doc_id, show_intermediate)
            
            if result:
                st.success("Processing complete!")
                
                # Display the propositions
                if show_intermediate:
                    with st.expander("Extracted Propositions", expanded=True):
                        # Create a DataFrame for easier viewing
                        if 'propositions' in result and result['propositions']:
                            propositions_data = []
                            for prop in result['propositions']:
                                propositions_data.append({
                                    'ID': prop.get('id', ''),
                                    'Proposition': prop.get('cleanText', ''),
                                    'Source Text': prop.get('sourceText', '')
                                })
                            st.dataframe(pd.DataFrame(propositions_data))
                        else:
                            st.info("No propositions were extracted or the content was not relevant.")
                
                # Format the result as JSON for download
                result_json = json.dumps(result, indent=2)
                
                # Create a download button for the result
                st.download_button(
                    label="Download JSON Result",
                    data=result_json,
                    file_name=f"{doc_id}_propositions.json",
                    mime="application/json"
                )
else:
    st.info("Please upload a markdown file to begin processing")

# Footer
st.markdown("---")
st.markdown("""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem 0;">
    <div style="color: #666666; font-size: 0.8rem;">
        Markdown Embeddings Generator 📝
    </div>
    <div style="color: #7fbc41; font-weight: bold; font-size: 0.9rem;">
        © 2025
    </div>
</div>
""", unsafe_allow_html=True)