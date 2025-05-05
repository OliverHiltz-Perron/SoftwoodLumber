# Softwood Lumber Board Document Checker 🌲

This application processes documents related to the wood industry, extracting key information and finding relationships to a database of propositions. It produces both structured data and a human-readable, formatted markdown summary of claims and their supporting evidence.

## How It Works

The Document Checker processes documents through a multi-stage pipeline, automated by `run_pipeline.sh`:

1. **Document Parsing**: Converts PDFs into clean Markdown text using LlamaParse.
2. **Markdown Cleaning**: Improves the formatting of the extracted text using OpenAI.
3. **Claim Extraction**: Identifies key claims (propositions, statements, facts) within the cleaned markdown using OpenAI.
4. **Metadata Extraction**: Extracts document metadata (title, summary, focus area, etc.) from the cleaned markdown.
5. **Database Matching**: Compares extracted claims to a database of known propositions and finds the best matches.
6. **Markdown Report Generation**: Produces a formatted markdown file summarizing all claims and their matched database propositions, including similarity scores and metadata.

### Pipeline Script

To run the full pipeline, use:

```bash
bash run_pipeline.sh
```

This will execute the following steps:

```bash
# 1. Convert PDF to Markdown
python src/llamaparse_converter.py -i input.pdf

# 2. Fix Markdown formatting with OpenAI
python src/markdown_fixer.py -i output/output_cleaned.md

# 3. Extract claims from cleaned markdown with OpenAI
python src/extract_claims.py -o output/extracted_claims.json

# 4. Extract metadata from all markdown files in output/ with OpenAI
python src/extract_metadata.py

# 5. Compare extracted claims to the database
python src/compare_claims_to_db.py -c output/extracted_claims.json -o output/claim_matches.json

# 6. Generate formatted markdown from claim matches and metadata
python src/claim_matches_to_markdown.py
```

### Output Files

After running the pipeline, the `output/` directory will contain:
- `output_cleaned.md`: Cleaned markdown version of your document
- `extracted_claims.json`: Extracted claims in JSON format
- `metadata.json`: Extracted metadata for the document
- `claim_matches.json`: List of claims and their best database matches
- `claim_matches_formatted.md`: **Formatted markdown report** summarizing all claims, their matches, similarity scores, and document metadata

## Formatted Markdown Report

The final step generates a human-readable markdown file (`claim_matches_formatted.md`) with the following structure:

- **Title**: From the document metadata
- **TL;DR**: Concise summary of the document
- **Focus Area**: Key focus areas/topics
- **Claims and Matched Propositions**: Each claim is listed with its matched database propositions, including similarity scores and IDs, for easy review and further analysis.

Example:

```
# Wood: Detailing for Performance

**TL;DR:**  
This document provides a detailed overview of wood as a building material, focusing on its variable properties, performance characteristics, and factors affecting durability such as exposure to weather, moisture, insects, and decay fungi. It emphasizes the importance of grain orientation, species grouping, and manufacturing processes on wood performance and deterioration in construction applications.

**Focus Area:**  
Material science | Building science | Construction | Forestry management | Research & development

---

## Claims and Matched Propositions

### Claim 1  
*In general, the variation for most wood properties (the ratio of highest to lowest for any property) is more than 2:1.*

**Matches:**  
- The strength of wood compared to its weight is an incredible strength to weight ratio (Similarity: 0.70) [ID: 7294_160]  
- Wood products are approximately 50% carbon by dry weight (Similarity: 0.61) [ID: Embodied C_23]  
...

---
```

## OpenAI Vector Embeddings in Supabase

The application now includes functionality to create and store OpenAI vector embeddings for propositions in the Supabase database. These embeddings enable powerful semantic search capabilities, allowing for more accurate matching between document claims and database propositions.

### What Are Vector Embeddings?

Vector embeddings are numerical representations of text that capture semantic meaning. They convert words and phrases into high-dimensional vectors (lists of numbers) where similar meanings are positioned closer together in the vector space. This allows for:

- **Semantic similarity search**: Finding propositions that are conceptually similar, not just keyword matches
- **Clustering of related content**: Identifying groups of propositions with similar themes
- **Cross-lingual capabilities**: Finding matches even when terminology differs

### How Embeddings Are Used

The OpenAI embeddings integration:
1. Connects to the Supabase database and retrieves proposition texts
2. Sends these texts to OpenAI's embedding API (`text-embedding-3-small` model)
3. Stores the resulting 1536-dimensional vectors in the `Embeddings_OpenAI` column of the `Embedded_propositions` table
4. Enables vector similarity search using pgvector's cosine similarity function

### Running the Embedding Script

To generate embeddings for all propositions in the database:

```bash
cd src/supabase-kb
python embeddings_openai.py
```

The script will:
- Only process propositions that don't already have embeddings (NULL values)
- Process in batches to respect API rate limits
- Handle Unicode and special characters
- Apply multiple storage methods to ensure compatibility with pgvector
- Save a CSV backup of all embeddings to the `output/` directory

### Prerequisites for Embeddings

- Supabase project with the pgvector extension enabled
- Table with a column of type `vector(1536)` named `Embeddings_OpenAI`
- OpenAI API key with access to the embeddings API
- Environment variables in `.env`:
  ```
  SUPABASE_URL=your_supabase_url
  SUPABASE_KEY=your_supabase_key
  OPENAI_API_KEY=your_openai_key
  ```

### Using Embeddings for Searches

Once embeddings are generated, you can perform semantic searches using SQL in Supabase:

```sql
SELECT id, text, 1 - ("Embeddings_OpenAI" <=> '[0.023,0.012,...]'::vector) as similarity 
FROM "Embedded_propositions"
ORDER BY "Embeddings_OpenAI" <=> '[0.023,0.012,...]'::vector
LIMIT 10;
```

Replace the vector with your query embedding to find the most semantically similar propositions.

## Setup

### Prerequisites

- Python 3.8 or higher
- Required libraries (see requirements.txt)

### API Keys

The application requires the following API keys:

- LlamaParse API Key
- OpenAI API Key

You need to provide these keys in a `.env` file in the project root directory:

```
LLAMA_CLOUD_API_KEY=your_llama_key_here
OPENAI_API_KEY=your_openai_key_here
```

## Troubleshooting

- **Application errors**: Check terminal output for detailed error messages
- **API key errors**: Ensure your .env file is properly formatted with valid API keys
- **Processing errors**: Check the terminal output for specific error messages from each processing stage

## Updating Dependencies

If you need to update the project dependencies, modify the `requirements.txt` file and install the updated dependencies:

```bash
pip install -r requirements.txt
```
