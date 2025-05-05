#!/usr/bin/env python3
from pathlib import Path
import os
import pandas as pd
import openai
from dotenv import load_dotenv
from supabase import create_client, Client
import time
import unicodedata
import re

# Set up paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
env_path = PROJECT_ROOT / '.env'
load_dotenv(env_path)

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError('Supabase credentials not found in .env')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError('OpenAI API key not found in .env')
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Config
BATCH_SIZE = 10
EMBEDDING_MODEL = 'text-embedding-3-small'
EMBEDDING_SIZE = 1536  # For text-embedding-3-small
OUTPUT_CSV = PROJECT_ROOT / 'output' / 'openai_embeddings.csv'
TABLE_NAME = 'Embedded_propositions'
EMBEDDING_COL = 'Embeddings_OpenAI'  # Should be vector(1536) in Supabase

# Ensure output directory exists
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

# 1. Add the embedding column if it doesn't exist
def ensure_embedding_column():
    # Get table columns
    resp = supabase.table(TABLE_NAME).select('*').limit(1).execute()
    if resp.data:
        columns = resp.data[0].keys()
        if EMBEDDING_COL in columns:
            return
    print(f"Column '{EMBEDDING_COL}' not found. Please add it manually in Supabase as type 'vector(1536)'.")
    print(f"Enable the pgvector extension if you haven't already.")
    exit(1)

# 2. Fetch all rows
def fetch_rows():
    rows = []
    offset = 0
    page_size = 1000
    while True:
        resp = supabase.table(TABLE_NAME).select('id, text').is_(EMBEDDING_COL, 'null').range(offset, offset+page_size-1).execute()
        if not resp.data:
            break
        rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size
    return pd.DataFrame(rows)

# 3. Generate embeddings
def generate_embeddings(texts):
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        embeddings = [item.embedding for item in response.data]
        # Check embedding size
        for emb in embeddings:
            if len(emb) != EMBEDDING_SIZE:
                raise ValueError(f"Embedding size mismatch: expected {EMBEDDING_SIZE}, got {len(emb)}")
        return embeddings
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return None

# 4. Update rows with embeddings
def update_rows(df, embeddings):
    success_count = 0
    error_count = 0
    
    # Directly loop through rows and embeddings together
    for (_, row), embedding in zip(df.iterrows(), embeddings):
        try:
            # Debug info
            print(f"Processing row id={row['id']}")
            print(f"  Embedding length: {len(embedding)}")
            print(f"  First 5 values: {embedding[:5]}")
            
            # METHOD 1: Try with direct list (standard)
            try:
                print("  Attempting update with direct list...")
                resp = supabase.table(TABLE_NAME).update({EMBEDDING_COL: embedding}).eq('id', row['id']).execute()
                print(f"  SUCCESS: Updated with direct list")
                success_count += 1
                continue  # If successful, move to next row
            except Exception as e:
                print(f"  WARNING: Direct list update failed: {e}")
            
            # METHOD 2: Try with JSON string
            try:
                print("  Attempting update with JSON string...")
                import json
                embedding_json = json.dumps(embedding)
                resp = supabase.table(TABLE_NAME).update({EMBEDDING_COL: embedding_json}).eq('id', row['id']).execute()
                print(f"  SUCCESS: Updated with JSON string")
                success_count += 1
                continue  # If successful, move to next row
            except Exception as e:
                print(f"  WARNING: JSON string update failed: {e}")
            
            # METHOD 3: Try with RPC call instead of direct update
            try:
                print("  Attempting RPC call...")
                # Create a simple RPC function in Supabase first
                # CREATE OR REPLACE FUNCTION set_embedding(row_id TEXT, vec VECTOR(1536))
                # RETURNS VOID AS $$
                # BEGIN
                #   UPDATE "Embedded_propositions" SET "Embeddings_OpenAI" = vec WHERE id = row_id;
                # END;
                # $$ LANGUAGE plpgsql;
                resp = supabase.rpc('set_embedding', {'row_id': row['id'], 'vec': embedding}).execute()
                print(f"  SUCCESS: Updated with RPC call")
                success_count += 1
                continue  # If successful, move to next row
            except Exception as e:
                print(f"  WARNING: RPC call failed: {e}")
            
            # If we get here, all methods failed
            print(f"  ERROR: All update methods failed for row id={row['id']}")
            error_count += 1
            
        except Exception as e:
            print(f"  ERROR: General error updating row id={row['id']}: {e}")
            error_count += 1
        
        time.sleep(0.05)  # avoid rate limits
    
    print(f"Update summary: {success_count} successful, {error_count} failed")
    return success_count, error_count

# 5. Save to CSV
def save_to_csv(df, embeddings):
    df = df.copy()
    df['embedding'] = embeddings
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved embeddings to {OUTPUT_CSV}")

# Add this function above the main loop
def filter_valid_texts(batch):
    valid_indices = []
    valid_texts = []
    for idx, text in enumerate(batch['text']):
        if isinstance(text, str) and text.strip():
            # Normalize Unicode characters
            cleaned_text = unicodedata.normalize('NFKD', text)
            # Replace common problematic Unicode quotes and apostrophes with ASCII versions
            cleaned_text = re.sub(r'[\u2018\u2019]', "'", cleaned_text)  # Smart single quotes
            cleaned_text = re.sub(r'[\u201C\u201D]', '"', cleaned_text)  # Smart double quotes
            cleaned_text = re.sub(r'\u2026', '...', cleaned_text)  # Ellipsis
            cleaned_text = re.sub(r'\u2013|\u2014', '-', cleaned_text)  # En and em dashes
            
            # If you want even more aggressive cleaning
            cleaned_text = re.sub(r'[^\x00-\x7F]+', '', cleaned_text)  # Remove any remaining non-ASCII characters
            
            valid_indices.append(idx)
            valid_texts.append(cleaned_text)
            
            # Print debug info if text was changed
            if cleaned_text != text:
                print(f"Unicode characters normalized in text at idx {idx} (row id={batch.iloc[idx]['id']})")
        else:
            print(f"Skipping empty or invalid text at batch index {idx} (row id={batch.iloc[idx]['id']})")
    return valid_indices, valid_texts

# Main
if __name__ == '__main__':
    ensure_embedding_column()
    df = fetch_rows()
    if df.empty:
        print('No rows found in table.')
        exit(0)
    print(f"Found {len(df)} rows to embed.")
    all_embeddings = []
    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i:i+BATCH_SIZE]
        valid_indices, valid_texts = filter_valid_texts(batch)
        print(f"Processing batch {i//BATCH_SIZE+1} ({len(valid_texts)} valid texts out of {len(batch)} total)...")
        if not valid_texts:
            print("No valid texts in this batch, skipping.")
            continue
        embeddings = generate_embeddings(valid_texts)
        if embeddings:
            if len(embeddings) != len(valid_indices):
                print(f"Embedding count mismatch: got {len(embeddings)} embeddings for {len(valid_indices)} valid texts. Skipping this batch.")
                continue
            print(f"Sample embedding (first 5 values): {embeddings[0][:5]}")
            # Only update rows with valid texts
            success_count, error_count = update_rows(batch.iloc[valid_indices], embeddings)
            all_embeddings.extend(embeddings)
        else:
            print(f"Failed to generate embeddings for batch {i//BATCH_SIZE+1}")
        time.sleep(0.5)
    save_to_csv(df, all_embeddings)
    print('Done.')