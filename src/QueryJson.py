import json
import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm

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

def process_propositions_with_embeddings(json_path, prefix="search_document:", threshold=0.6, top_k=3):
    """
    Process all propositions in the JSON file, find similar propositions, and add them to the JSON
    """
    # Load the JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Determine device (CPU/GPU)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load model and tokenizer
    print("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained("nomic-ai/nomic-embed-text-v2-moe")
    model = AutoModel.from_pretrained("nomic-ai/nomic-embed-text-v2-moe", trust_remote_code=True)
    model = model.to(device)
    model.eval()
    
    # Create a list of all propositions across all documents
    all_propositions = []
    for document in data:
        if 'propositions' in document and document['propositions']:
            all_propositions.extend(document['propositions'])
    
    print(f"Total propositions: {len(all_propositions)}")
    
    # Create embeddings for all propositions
    print("Creating embeddings for all propositions...")
    all_embeddings = []
    for prop in tqdm(all_propositions):
        embedding = create_embedding(
            text=prop['text'],
            model=model,
            tokenizer=tokenizer,
            max_length=512,
            prefix=prefix,
            device=device
        )
        all_embeddings.append(embedding)
    
    # Convert to numpy array for faster calculations
    all_embeddings = np.array(all_embeddings)
    
    # Process each document and find similar propositions
    print("Finding similar propositions for each proposition...")
    for document in tqdm(data):
        if 'propositions' not in document or not document['propositions']:
            continue
        
        for prop in document['propositions']:
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
                threshold=threshold,
                top_k=top_k
            )
            
            # Add the results to the proposition
            prop['closest_embeddings'] = similar_props
    
    # Save the updated JSON to the same file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"Process complete. Results saved to {json_path}")
    return data

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process propositions and find similar ones')
    parser.add_argument('--path', type=str, 
                      default="C:\\Users\\olive\\OneDrive\\Desktop\\SoftwoodLumber\\extracted_propositions.json", 
                      help='Path to JSON file')
    parser.add_argument('--prefix', type=str, default="search_document:", help='Prefix for embeddings')
    parser.add_argument('--threshold', type=float, default=0.6, help='Similarity threshold')
    parser.add_argument('--top_k', type=int, default=3, help='Number of top matches to return')
    
    args = parser.parse_args()
    
    process_propositions_with_embeddings(
        json_path=args.path,
        prefix=args.prefix,
        threshold=args.threshold,
        top_k=args.top_k
    )