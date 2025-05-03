#!/bin/bash

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