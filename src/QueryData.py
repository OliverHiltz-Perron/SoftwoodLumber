import argparse
import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import json
from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser(description='Match text against embeddings')
    parser.add_argument('--file_path', type=str, default="C:\\Users\\olive\\OneDrive\\Desktop\\BrianNomic\\propositions_rows.csv", 
                      help='Path to CSV file with embeddings')
    parser.add_argument('--query', type=str, 
                      default="To reduce carbon emissions in construction, there is expected to be a return to using wood in many building cases",
                      help='Query text to match')
    parser.add_argument('--threshold', type=float, default=0.6, 
                      help='Minimum similarity threshold (between 0 and 1)')
    parser.add_argument('--max_length', type=int, default=512, help='Maximum token length')
    parser.add_argument('--prefix', type=str, default='search_query:', 
                      help='Prefix for embedding (search_document: or search_query:)')
    parser.add_argument('--use_gpu', action='store_true', help='Use GPU if available')
    return parser.parse_args()

def mean_pooling(model_output, attention_mask):
    """
    Perform mean pooling on token embeddings
    """
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

def create_query_embedding(query_text, model, tokenizer, max_length, prefix, device):
    """
    Create embedding for the query text
    """
    # Add prefix to query
    prefixed_query = f"{prefix} {query_text}"
    
    # Tokenize
    inputs = tokenizer(
        [prefixed_query],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors='pt'
    ).to(device)
    
    # Generate embedding
    with torch.no_grad():
        outputs = model(**inputs)
    
    # Pool and normalize
    query_embedding = mean_pooling(outputs, inputs['attention_mask'])
    query_embedding = F.normalize(query_embedding, p=2, dim=1)
    
    return query_embedding.cpu().numpy()[0]

def find_similar_texts(df, query_embedding, threshold=0.6):
    """
    Find texts with similarity above threshold
    """
    # Convert stored embeddings from string to numpy arrays
    all_embeddings = np.array([json.loads(emb) for emb in df['embeddings']])
    
    # Calculate cosine similarity
    similarities = np.dot(all_embeddings, query_embedding)
    
    # Get indices of texts that meet the threshold
    matching_indices = np.where(similarities >= threshold)[0]
    
    # Sort by similarity (highest first)
    sorted_indices = matching_indices[np.argsort(similarities[matching_indices])[::-1]]
    
    # Create result list
    results = []
    for idx in sorted_indices:
        results.append({
            'text': df.iloc[idx]['text'],
            'similarity': float(similarities[idx]),
            'row_index': int(idx)
        })
    
    return results

def main():
    args = parse_args()
    
    # Determine device (CPU/GPU)
    device = torch.device('cuda' if torch.cuda.is_available() and args.use_gpu else 'cpu')
    print(f"Using device: {device}")
    
    # Load model and tokenizer
    print("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained("nomic-ai/nomic-embed-text-v2-moe")
    model = AutoModel.from_pretrained("nomic-ai/nomic-embed-text-v2-moe", trust_remote_code=True)
    model = model.to(device)
    model.eval()
    
    # Load CSV data
    print(f"Loading data from {args.file_path}...")
    df = pd.read_csv(args.file_path)
    print(f"Loaded {len(df)} rows")
    
    # Create embedding for query
    print(f"Creating embedding for query: '{args.query}'")
    query_embedding = create_query_embedding(
        query_text=args.query,
        model=model,
        tokenizer=tokenizer,
        max_length=args.max_length,
        prefix=args.prefix,
        device=device
    )
    
    # Find similar texts
    print(f"Finding matches with similarity >= {args.threshold}...")
    results = find_similar_texts(df, query_embedding, args.threshold)
    
    # Print results
    if len(results) > 0:
        print(f"\nFound {len(results)} matches with similarity >= {args.threshold}:")
        for i, result in enumerate(results):
            print(f"\n[{i+1}] Similarity: {result['similarity']:.4f}")
            print(f"Text: {result['text']}")
    else:
        print(f"\nNo matches found with similarity >= {args.threshold}")
    
    print("\nDone!")

if __name__ == '__main__':
    main()