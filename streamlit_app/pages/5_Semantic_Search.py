import streamlit as st
import sys
import os
import tempfile
import pandas as pd
import numpy as np
import json
from copy import deepcopy

# Add the parent directory to sys.path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the utilities for shared file storage
from streamlit_app.utils import save_uploaded_file, save_json_file, advanced_file_selector, display_shared_data_status
from streamlit_app.utils import PROPOSITIONS_DIR, ENHANCED_PROPS_DIR

st.title("🔍 Semantic Search")

# Display shared data status in sidebar
display_shared_data_status()

st.markdown("""
This tool performs semantic search to find similar propositions in your database.
Upload a JSON file with propositions to find the most semantically similar matches.
""")

# Try importing the required modules
with st.spinner("Loading required modules..."):
    try:
        # Import the necessary components
        import torch
        import torch.nn.functional as F
        from transformers import AutoTokenizer, AutoModel
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
        
        This feature requires:
        - torch
        - transformers
        - pandas
        - numpy
        """)

if modules_loaded:
    # Sidebar for model loading status and additional options
    with st.sidebar:
        st.header("Model Status")
        model_status = st.empty()
        
        # Check if using GPU is available
        gpu_available = torch.cuda.is_available()
        device_info = f"{'GPU' if gpu_available else 'CPU'} ({torch.cuda.get_device_name(0) if gpu_available else 'N/A'})"
        st.info(f"Using device: {device_info}")
        
        # Advanced options
        st.header("Advanced Options")
        use_gpu = st.checkbox("Use GPU (if available)", value=gpu_available)
        max_length = st.slider("Max Token Length", min_value=128, max_value=1024, value=512, step=128)
        prefix = st.selectbox("Embedding Prefix", ["search_document:", "search_query:"], index=0)
        similarity_threshold = st.slider("Similarity threshold:", 0.0, 1.0, 0.6, 0.05)
        top_k = st.slider("Number of closest matches to include", min_value=1, max_value=10, value=3)
    
    # Define the functions (directly from the provided QueryJson.py)
    def mean_pooling(model_output, attention_mask):
        """
        Perform mean pooling on token embeddings
        """
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def create_embedding(text, model, tokenizer, max_length, prefix, device):
        """
        Create embedding for text
        """
        # Add prefix to text
        prefixed_text = f"{prefix} {text}"
        
        # Tokenize
        inputs = tokenizer(
            [prefixed_text],
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors='pt'
        ).to(device)
        
        # Generate embedding
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Pool and normalize
        embedding = mean_pooling(outputs, inputs['attention_mask'])
        embedding = F.normalize(embedding, p=2, dim=1)
        
        return embedding.cpu().numpy()[0]

    def find_similar_propositions(query_embedding, all_embeddings, all_propositions, threshold=0.5, top_k=4):
        """
        Find the most similar propositions based on cosine similarity
        """
        # Calculate cosine similarity
        similarities = np.dot(all_embeddings, query_embedding)
        
        # Get indices of propositions that meet the threshold, sorted by similarity
        matching_indices = np.where(similarities >= threshold)[0]
        
        # If no matches meet the threshold, get top k regardless of threshold
        if len(matching_indices) == 0:
            top_indices = np.argsort(similarities)[-top_k:][::-1]
        else:
            # Sort by similarity (highest first) and take top k
            sorted_indices = matching_indices[np.argsort(similarities[matching_indices])[::-1]]
            top_indices = sorted_indices[:top_k]
        
        # Create result list
        results = []
        for idx in top_indices:
            results.append({
                'text': all_propositions[idx]['text'],
                'id': all_propositions[idx]['id'],
                'similarity': float(similarities[idx])
            })
        
        return results
    
    # Function to initialize model and tokenizer
    @st.cache_resource
    def load_model_and_tokenizer():
        tokenizer = AutoTokenizer.from_pretrained("nomic-ai/nomic-embed-text-v2-moe")
        model = AutoModel.from_pretrained("nomic-ai/nomic-embed-text-v2-moe", trust_remote_code=True)
        return tokenizer, model
    
    # Option to use either uploaded file or existing file
    st.subheader("Select Propositions Source")
    source_option = st.radio(
        "Choose propositions source:",
        ["Upload new JSON file", "Use existing file (any type)"]
    )
    
    # Variable to hold the proposition data
    data = None
    uploaded_file = None
    file_path = None
    
    if source_option == "Upload new JSON file":
        # Upload JSON file with propositions
        uploaded_file = st.file_uploader("Upload propositions JSON file", type=["json"])
        
        if uploaded_file:
            try:
                # Save the uploaded file to shared storage
                file_path = save_uploaded_file(uploaded_file, PROPOSITIONS_DIR)
                st.success(f"File '{uploaded_file.name}' saved to shared storage")
                
                # Load the JSON data
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                st.error(f"Error processing uploaded file: {str(e)}")
    else:
        # Select ANY existing file (from any directory)
        file_path = advanced_file_selector(
            "Select any JSON file:", 
            file_types=["json", "propositions", "enhanced_propositions"]
        )
        
        if file_path:
            try:
                # Load the JSON data
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                st.success(f"Loaded {os.path.basename(file_path)} from shared storage")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")
    
    # Load the propositions_rows.csv file for the database to search
    propositions_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'propositions_rows.csv')
    
    # Variables to store the database
    df = None
    
    # First, check if propositions_rows.csv exists
    if os.path.exists(propositions_path):
        try:
            df = pd.read_csv(propositions_path)
            st.success(f"Successfully loaded propositions database with {len(df)} rows")
            
            # Show a preview of the dataset
            with st.expander("Preview of propositions database"):
                st.write(df.head())
                st.info(f"Columns: {', '.join(df.columns)}")
                
                # Check if required columns exist
                required_columns = ['text', 'embeddings']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    st.error(f"Missing required columns: {', '.join(missing_columns)}")
                    st.stop()
        except Exception as e:
            st.error(f"Error loading propositions database: {str(e)}")
            st.stop()
    else:
        st.error(f"Could not find propositions_rows.csv in project root")
        st.info("Please ensure the propositions_rows.csv file is in the project root directory")
        st.stop()
    
    # Process propositions when button is clicked
    if data is not None and df is not None and st.button("Process Propositions"):
        # Check the structure of the JSON
        if isinstance(data, dict) and "propositions" in data:
            # Single document format
            documents = [data]
        elif isinstance(data, list):
            # Multiple documents format
            documents = data
        else:
            st.error("Invalid JSON format. Expected a list of documents or a single document with propositions.")
            st.stop()
        
        # Count the total propositions
        total_props = sum(len(doc.get("propositions", [])) for doc in documents)
        st.info(f"Found {len(documents)} documents with a total of {total_props} propositions")
    
        # Load model and tokenizer
        with st.spinner("Loading embedding model..."):
            try:
                model_status.info("Loading model...")
                tokenizer, model = load_model_and_tokenizer()
                
                # Move model to GPU if available and requested
                device = torch.device('cuda' if torch.cuda.is_available() and use_gpu else 'cpu')
                model = model.to(device)
                model.eval()
                
                model_status.success("Model loaded successfully")
            except Exception as e:
                model_status.error(f"Error loading model: {str(e)}")
                st.error(f"Failed to load embedding model: {str(e)}")
                st.stop()
        
        # Create a list of all propositions across all documents
        with st.spinner("Creating list of all propositions..."):
            all_propositions = []
            for document in documents:
                if 'propositions' in document and document['propositions']:
                    all_propositions.extend(document['propositions'])
            
            st.success(f"Collected {len(all_propositions)} propositions for processing")
        
        # Create embeddings for all propositions
        with st.spinner("Creating embeddings for all propositions..."):
            # Set up progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_embeddings = []
            for i, prop in enumerate(all_propositions):
                # Update progress
                progress = (i / len(all_propositions))
                progress_bar.progress(progress)
                status_text.text(f"Creating embedding for {prop.get('id', f'Proposition {i+1}')} ({i+1}/{len(all_propositions)})")
                
                # Create embedding
                embedding = create_embedding(
                    text=prop['text'],
                    model=model,
                    tokenizer=tokenizer,
                    max_length=max_length,
                    prefix=prefix,
                    device=device
                )
                all_embeddings.append(embedding)
            
            # Convert to numpy array for faster calculations
            all_embeddings = np.array(all_embeddings)
            
            # Complete the progress
            progress_bar.progress(1.0)
            status_text.text("Embeddings created successfully!")
        
        # Process each document and find similar propositions
        with st.spinner("Finding similar propositions for each proposition..."):
            # Reset progress tracking
            progress_bar = st.progress(0)
            status_text.empty()
            
            # Track total propositions processed
            total_processed = 0
            
            # Process each document
            for doc_idx, document in enumerate(documents):
                if 'propositions' not in document or not document['propositions']:
                    continue
                
                # Process each proposition in this document
                for prop_idx, prop in enumerate(document['propositions']):
                    # Update progress
                    total_processed += 1
                    progress = (total_processed / total_props)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing {prop.get('id', f'Proposition {total_processed}')} ({total_processed}/{total_props})")
                    
                    # Get the index of this proposition in all_propositions
                    current_idx = next((i for i, p in enumerate(all_propositions) 
                                      if p['id'] == prop['id']), None)
                    
                    if current_idx is None:
                        continue
                    
                    # Get the embedding for this proposition
                    query_embedding = all_embeddings[current_idx]
                    
                    # Create a mask to exclude the current proposition from candidates
                    mask = np.ones(len(all_embeddings), dtype=bool)
                    mask[current_idx] = False
                    
                    # Find similar propositions (excluding self)
                    similar_props = find_similar_propositions(
                        query_embedding=query_embedding,
                        all_embeddings=all_embeddings[mask],
                        all_propositions=[p for i, p in enumerate(all_propositions) if i != current_idx],
                        threshold=similarity_threshold,
                        top_k=top_k
                    )
                    
                    # Add the results to the proposition
                    documents[doc_idx]['propositions'][prop_idx]['closest_values'] = similar_props
            
            # Complete the progress
            progress_bar.progress(1.0)
            status_text.text("Processing complete!")
        
        # Save the enhanced JSON to the shared storage
        output_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_enhanced.json"
        if len(documents) == 1:
            # If there was just one document, save it directly
            output_path = save_json_file(documents[0], output_filename, "enhanced_propositions")
        else:
            # Otherwise save the full list
            output_path = save_json_file(documents, output_filename, "enhanced_propositions")
        
        st.success(f"Enhanced propositions saved to shared storage as '{output_filename}'")
        
        # Provide download button
        with open(output_path, "r") as f:
            st.download_button(
                label="Download Enhanced Propositions JSON",
                data=f.read(),
                file_name=output_filename,
                mime="application/json"
            )
        
        # Display a preview of the results
        st.subheader("Preview of Enhanced Propositions")
        
        # Choose a document to preview
        if len(documents) > 1:
            doc_to_preview = st.selectbox(
                "Select a document to preview:",
                options=[doc.get("documentId", f"Document {i+1}") for i, doc in enumerate(documents)]
            )
            preview_doc = next((doc for doc in documents if doc.get("documentId") == doc_to_preview), documents[0])
        else:
            preview_doc = documents[0]
        
        # Display document info
        st.markdown(f"**Document ID:** {preview_doc.get('documentId', 'Unknown')}")
        st.markdown(f"**Filename:** {preview_doc.get('filename', 'Unknown')}")
        
        # Display a subset of propositions
        propositions = preview_doc.get("propositions", [])
        preview_count = min(5, len(propositions))
        
        for i in range(preview_count):
            proposition = propositions[i]
            with st.expander(f"{proposition.get('id', f'Proposition {i+1}')}"):
                st.markdown(f"**Text:** {proposition.get('text', '')}")
                st.markdown(f"**Source:** {proposition.get('sourceText', '')}")
                
                # Show closest values
                if "closest_values" in proposition and proposition["closest_values"]:
                    st.markdown("**Closest Values:**")
                    for j, match in enumerate(proposition["closest_values"]):
                        st.markdown(f"{j+1}. **ID:** {match.get('id', 'Unknown')}  *Similarity: {match.get('similarity', 0):.4f}*")
                        st.markdown(f"   {match.get('text', '')}")
        
        if len(propositions) > preview_count:
            st.info(f"+ {len(propositions) - preview_count} more propositions (download the JSON to see all)")
    
    # Option to browse and view existing enhanced proposition files from ANY directory
    st.subheader("Browse Any Existing Files")
    view_file = advanced_file_selector(
        "Select any file to view:", 
        file_types=["all"]
    )
    
    if view_file:
        try:
            file_ext = os.path.splitext(view_file)[1].lower()
            
            if file_ext == '.json':
                # JSON file
                with open(view_file, 'r', encoding='utf-8') as f:
                    view_data = json.load(f)
                
                st.success(f"Loaded {os.path.basename(view_file)}")
                
                # Display JSON structure based on content
                if isinstance(view_data, dict) and "propositions" in view_data:
                    # Single document format with propositions
                    st.markdown(f"**Document ID:** {view_data.get('documentId', 'Unknown')}")
                    st.markdown(f"**Filename:** {view_data.get('filename', 'Unknown')}")
                    
                    # Show propositions
                    propositions = view_data.get("propositions", [])
                    st.markdown(f"**Contains {len(propositions)} propositions**")
                    
                    # Show the first few propositions
                    preview_count = min(3, len(propositions))
                    for i in range(preview_count):
                        with st.expander(f"Proposition {i+1}"):
                            st.json(propositions[i])
                    
                else:
                    # Generic JSON
                    st.json(view_data)
            elif file_ext == '.md':
                # Markdown file
                with open(view_file, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                st.success(f"Loaded {os.path.basename(view_file)}")
                st.markdown(md_content)
            else:
                # Other file type
                with open(view_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                st.success(f"Loaded {os.path.basename(view_file)}")
                st.text(content[:1000] + "..." if len(content) > 1000 else content)
            
            # Provide download button
            with open(view_file, "r", encoding='utf-8') as f:
                st.download_button(
                    label=f"Download {os.path.basename(view_file)}",
                    data=f.read(),
                    file_name=os.path.basename(view_file),
                    mime="application/octet-stream"
                )
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
else:
    st.warning("Please install the required dependencies to use this feature.")
