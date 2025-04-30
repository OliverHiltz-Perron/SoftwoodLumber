import json
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import argparse
import sys
import os
import pandas as pd

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

def find_similar_propositions(query_embedding, db_embeddings, db_propositions, threshold=0.5, top_k=4):
    """
    Find the most similar propositions in the database based on cosine similarity
    """
    # Calculate cosine similarity
    similarities = np.dot(db_embeddings, query_embedding)
    
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
            'text': db_propositions[idx]['text'],
            'id': db_propositions[idx]['id'],
            'similarity': float(similarities[idx])
        })
    
    return results

def load_database_embeddings(csv_path):
    """
    Load pre-computed embeddings from CSV database
    """
    print(f"Loading database embeddings from {csv_path}...", file=sys.stderr)
    try:
        # Load the CSV
        df = pd.read_csv(csv_path)
        print(f"Successfully loaded database with {len(df)} rows", file=sys.stderr)
        
        # Check if required columns exist
        required_columns = ['text', 'embeddings', 'id']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            missing_cols_str = ', '.join(missing_columns)
            print(f"Warning: Missing required columns in database: {missing_cols_str}", file=sys.stderr)
            print("Creating placeholder columns for missing data", file=sys.stderr)
            
            # Create placeholder columns if they don't exist
            if 'id' not in df.columns:
                df['id'] = [f"db_row_{i}" for i in range(len(df))]
                
            if 'text' not in df.columns:
                print("Error: 'text' column must exist in database", file=sys.stderr)
                return None, None
                
            if 'embeddings' not in df.columns:
                print("Error: 'embeddings' column must exist in database", file=sys.stderr)
                return None, None
        
        # Convert embeddings from string to numpy arrays
        # Embeddings might be stored as strings like "[0.1, 0.2, 0.3, ...]"
        embeddings_list = []
        
        for emb_str in df['embeddings']:
            # Parse the embedding string into a numpy array
            try:
                # Try to parse as a Python list
                if isinstance(emb_str, str):
                    # Remove brackets and split by commas
                    values = emb_str.strip('[]').split(',')
                    # Convert to floats
                    emb = np.array([float(x.strip()) for x in values])
                    embeddings_list.append(emb)
                else:
                    # Already a proper format
                    embeddings_list.append(np.array(emb_str))
            except Exception as e:
                print(f"Error parsing embedding: {e}", file=sys.stderr)
                return None, None
        
        # Convert list of embeddings to a 2D numpy array
        db_embeddings = np.array(embeddings_list)
        
        # Create list of proposition dictionaries
        db_propositions = []
        for i, row in df.iterrows():
            db_propositions.append({
                'id': row['id'],
                'text': row['text']
            })
        
        print(f"Successfully loaded {len(db_embeddings)} embeddings from database", file=sys.stderr)
        return db_embeddings, db_propositions
        
    except Exception as e:
        print(f"Error loading database: {e}", file=sys.stderr)
        return None, None

def process_propositions_with_database(data, db_path, prefix="search_document:", threshold=0.6, top_k=3, max_length=512, use_gpu=None):
    """
    Process propositions in data, find similar propositions in the database, and add them to the JSON
    """
    # Determine device (CPU/GPU)
    if use_gpu is None:
        use_gpu = torch.cuda.is_available()
    
    device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}", file=sys.stderr)
    
    # Load model and tokenizer
    print("Loading model and tokenizer...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained("nomic-ai/nomic-embed-text-v2-moe")
    model = AutoModel.from_pretrained("nomic-ai/nomic-embed-text-v2-moe", trust_remote_code=True)
    model = model.to(device)
    model.eval()
    
    # Load database embeddings
    db_embeddings, db_propositions = load_database_embeddings(db_path)
    if db_embeddings is None or db_propositions is None:
        print("Failed to load database embeddings. Exiting.", file=sys.stderr)
        return None
    
    # Determine format: single document or list of documents
    if isinstance(data, dict) and "propositions" in data:
        # Single document format
        documents = [data]
    elif isinstance(data, list):
        # Check if this is a list of documents or list of propositions
        if len(data) > 0 and isinstance(data[0], dict) and "propositions" in data[0]:
            # List of documents
            documents = data
        else:
            # Might be a list of propositions, so wrap in a document
            documents = [{"documentId": "doc_1", "propositions": data}]
    else:
        print("Invalid data format. Expected a document with propositions or list of documents.", file=sys.stderr)
        return None
    
    # Create a list of all propositions across all documents
    all_propositions = []
    for document in documents:
        if 'propositions' in document and document['propositions']:
            all_propositions.extend(document['propositions'])
    
    if not all_propositions:
        print("No propositions found in the input data.", file=sys.stderr)
        return documents
    
    print(f"Processing {len(all_propositions)} propositions against {len(db_propositions)} database entries", file=sys.stderr)
    
    # Process each proposition and find similar ones in the database
    processed_count = 0
    for doc_idx, document in enumerate(documents):
        if 'propositions' not in document or not document['propositions']:
            continue
        
        for prop_idx, prop in enumerate(document['propositions']):
            processed_count += 1
            print(f"Processing proposition {processed_count}/{len(all_propositions)}", file=sys.stderr)
            
            # Create embedding for this proposition
            query_embedding = create_embedding(
                text=prop['text'],
                model=model,
                tokenizer=tokenizer,
                max_length=max_length,
                prefix=prefix,
                device=device
            )
            
            # Find similar propositions in the database
            similar_props = find_similar_propositions(
                query_embedding=query_embedding,
                db_embeddings=db_embeddings,
                db_propositions=db_propositions,
                threshold=threshold,
                top_k=top_k
            )
            
            # Add the results to the proposition
            documents[doc_idx]['propositions'][prop_idx]['closest_database_matches'] = similar_props
    
    # Return the updated documents
    return documents

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Process propositions and find similar ones in a database')
    parser.add_argument('-i', '--input', type=str, default='-', 
                      help='Path to JSON file. Use "-" for stdin (default)')
    parser.add_argument('-o', '--output', type=str, default='-',
                      help='Path to output JSON file. Use "-" for stdout (default)')
    parser.add_argument('-d', '--database', type=str, 
                      default='C:\\Users\\olive\\OneDrive\\Desktop\\SoftwoodLumber\\propositions_rows.csv',
                      help='Path to database CSV file with pre-computed embeddings')
    parser.add_argument('--prefix', type=str, default="search_document:", 
                      help='Prefix for embeddings (default: search_document:)')
    parser.add_argument('--threshold', type=float, default=0.6, 
                      help='Similarity threshold (default: 0.6)')
    parser.add_argument('--top_k', type=int, default=3, 
                      help='Number of top matches to return (default: 3)')
    parser.add_argument('--max_length', type=int, default=512, 
                      help='Maximum token length for embeddings (default: 512)')
    parser.add_argument('--use_gpu', action='store_true', 
                      help='Use GPU if available (default: auto-detect)')
    parser.add_argument('--no_gpu', action='store_true', 
                      help='Disable GPU usage even if available')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.use_gpu and args.no_gpu:
        print("Error: Cannot specify both --use_gpu and --no_gpu", file=sys.stderr)
        return 1
    
    use_gpu = None  # Auto-detect
    if args.use_gpu:
        use_gpu = True
    elif args.no_gpu:
        use_gpu = False
    
    # Read input
    try:
        if args.input == '-':
            print("Reading from stdin...", file=sys.stderr)
            data = json.load(sys.stdin)
        else:
            print(f"Reading from file: {args.input}", file=sys.stderr)
            with open(args.input, 'r', encoding='utf-8') as f:
                data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Input is not valid JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return 1
    
    # Process the data
    try:
        processed_data = process_propositions_with_database(
            data=data,
            db_path=args.database,
            prefix=args.prefix,
            threshold=args.threshold,
            top_k=args.top_k,
            max_length=args.max_length,
            use_gpu=use_gpu
        )
        
        if processed_data is None:
            print("Processing failed", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        return 1
    
    # Output
    try:
        if args.output == '-':
            json.dump(processed_data, sys.stdout, indent=2)
        else:
            print(f"Writing to file: {args.output}", file=sys.stderr)
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(args.output)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, indent=2)
            print(f"Successfully wrote enhanced propositions to {args.output}", file=sys.stderr)
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())