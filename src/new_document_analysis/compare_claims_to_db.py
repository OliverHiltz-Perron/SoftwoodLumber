import json
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import argparse
import sys
import os
import pandas as pd

# --- Embedding and similarity functions (adapted from QueryJson.py) ---
def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

def create_embedding(text, model, tokenizer, max_length, prefix, device):
    prefixed_text = f"{prefix} {text}"
    inputs = tokenizer(
        [prefixed_text],
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors='pt'
    ).to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    embedding = mean_pooling(outputs, inputs['attention_mask'])
    embedding = F.normalize(embedding, p=2, dim=1)
    return embedding.cpu().numpy()[0]

def find_similar_propositions(query_embedding, db_embeddings, db_propositions, threshold=0.5, top_k=4):
    similarities = np.dot(db_embeddings, query_embedding)
    matching_indices = np.where(similarities >= threshold)[0]
    if len(matching_indices) == 0:
        top_indices = np.argsort(similarities)[-top_k:][::-1]
    else:
        sorted_indices = matching_indices[np.argsort(similarities[matching_indices])[::-1]]
        top_indices = sorted_indices[:top_k]
    results = []
    for idx in top_indices:
        if 'db_proposition' in db_propositions[idx]:
            proposition_text = db_propositions[idx]['db_proposition']
        elif 'text' in db_propositions[idx]:
            proposition_text = db_propositions[idx]['text']
        else:
            text_fields = [k for k, v in db_propositions[idx].items() if isinstance(v, str) and k != 'id']
            proposition_text = db_propositions[idx][text_fields[0]] if text_fields else "Unknown proposition"
        results.append({
            'db_propositions': proposition_text,
            'id': db_propositions[idx]['id'],
            'similarity': float(similarities[idx])
        })
    return results

def load_database_embeddings(csv_path):
    print(f"Loading database embeddings from {csv_path}...", file=sys.stderr)
    try:
        df = pd.read_csv(csv_path)
        required_columns = ['text', 'embeddings', 'id']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            if 'id' not in df.columns:
                df['id'] = [f"db_row_{i}" for i in range(len(df))]
            if 'text' not in df.columns:
                print("Error: 'text' column must exist in database", file=sys.stderr)
                return None, None
            if 'embeddings' not in df.columns:
                print("Error: 'embeddings' column must exist in database", file=sys.stderr)
                return None, None
        embeddings_list = []
        for emb_str in df['embeddings']:
            try:
                if isinstance(emb_str, str):
                    values = emb_str.strip('[]').split(',')
                    emb = np.array([float(x.strip()) for x in values])
                    embeddings_list.append(emb)
                else:
                    embeddings_list.append(np.array(emb_str))
            except Exception as e:
                print(f"Error parsing embedding: {e}", file=sys.stderr)
                return None, None
        db_embeddings = np.array(embeddings_list)
        db_propositions = []
        for i, row in df.iterrows():
            prop_dict = {'id': row['id']}
            if 'text' in row:
                prop_dict['db_proposition'] = row['text']
            elif 'cleanText' in row:
                prop_dict['db_proposition'] = row['cleanText']
            elif 'Text' in row:
                prop_dict['db_proposition'] = row['Text']
            else:
                text_columns = [col for col in row.index if isinstance(row[col], str) and col not in ['id', 'embeddings']]
                if text_columns:
                    prop_dict['db_proposition'] = row[text_columns[0]]
                else:
                    prop_dict['db_proposition'] = f"Row {i}"
            # Add file_name if present
            if 'file_name' in row:
                prop_dict['file_name'] = row['file_name']
            db_propositions.append(prop_dict)
        return db_embeddings, db_propositions
    except Exception as e:
        print(f"Error loading database: {e}", file=sys.stderr)
        return None, None

# --- Main script logic ---
def main():
    parser = argparse.ArgumentParser(description='Compare extracted claims to proposition database using embeddings')
    parser.add_argument('-c', '--claims', type=str, default=None, help='Path to extracted_claims.json (default: output/{basename}_claims.json)')
    parser.add_argument('-d', '--database', type=str, default='propositions_rows.csv', help='Path to propositions_rows.csv')
    parser.add_argument('-o', '--output', type=str, default=None, help='Output JSON file for matches (default: output/{basename}_claim_matches.json)')
    parser.add_argument('--prefix', type=str, default="search_document:", help='Prefix for embeddings (default: search_document:)')
    parser.add_argument('--threshold', type=float, default=0.6, help='Similarity threshold (default: 0.6)')
    parser.add_argument('--top_k', type=int, default=3, help='Number of top matches to return (default: 3)')
    parser.add_argument('--max_length', type=int, default=512, help='Maximum token length for embeddings (default: 512)')
    parser.add_argument('--use_gpu', action='store_true', help='Use GPU if available')
    parser.add_argument('--no_gpu', action='store_true', help='Disable GPU usage even if available')
    args = parser.parse_args()

    # Determine base name
    if args.claims is None:
        import glob
        claim_files = glob.glob('output/*_claims.json')
        if claim_files:
            claims_path = claim_files[0]
        else:
            claims_path = 'output/extracted_claims.json'
    else:
        claims_path = args.claims
    base_name = os.path.splitext(os.path.basename(claims_path))[0]
    base_name = base_name.replace('_markdown', '').replace('_cleaned', '').replace('_claims', '')
    if args.output is None:
        output_json = f'output/{base_name}_claim_matches.json'
    else:
        output_json = args.output
    print(f"BASENAME:{base_name}", file=sys.stderr)

    use_gpu = None
    if args.use_gpu:
        use_gpu = True
    elif args.no_gpu:
        use_gpu = False
    device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}", file=sys.stderr)

    # Load model and tokenizer
    print("Loading model and tokenizer...", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained("nomic-ai/nomic-embed-text-v2-moe", revision="main")
    model = AutoModel.from_pretrained("nomic-ai/nomic-embed-text-v2-moe", revision="main", trust_remote_code=True)
    model = model.to(device)
    model.eval()

    # Load claims
    with open(claims_path, 'r', encoding='utf-8') as f:
        # Remove accidental markdown code block if present
        first_line = f.readline()
        if first_line.strip().startswith('['):
            claims = json.loads(first_line + f.read())
        else:
            claims = json.load(f)

    # Load database
    db_embeddings, db_propositions = load_database_embeddings(args.database)
    if db_embeddings is None or db_propositions is None:
        print("Failed to load database embeddings. Exiting.", file=sys.stderr)
        sys.exit(1)

    # For each claim, compute embedding and find matches
    results = []
    for idx, claim in enumerate(claims):
        text = claim.get('sourceText', '')
        if not text:
            continue
        print(f"Processing claim {idx+1}/{len(claims)}", file=sys.stderr)
        query_embedding = create_embedding(
            text=text,
            model=model,
            tokenizer=tokenizer,
            max_length=args.max_length,
            prefix=args.prefix,
            device=device
        )
        matches = find_similar_propositions(
            query_embedding=query_embedding,
            db_embeddings=db_embeddings,
            db_propositions=db_propositions,
            threshold=args.threshold,
            top_k=args.top_k
        )
        # Add file_name to each match if present in db_propositions
        for match in matches:
            match_id = match.get('id')
            for db_prop in db_propositions:
                if db_prop.get('id') == match_id:
                    match['file_name'] = db_prop.get('file_name', '')
                    break
        results.append({
            'claim': text,
            'matches': matches
        })

    # Write output
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Wrote results to {output_json}", file=sys.stderr)

if __name__ == "__main__":
    main() 