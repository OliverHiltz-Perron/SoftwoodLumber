#!/bin/bash

# Get the base name of the input PDF (without extension)
INPUT_PDF="WoodAsBuildingMaterial.pdf"
BASENAME=$(basename "$INPUT_PDF" .pdf)

# 1. Convert PDF to Markdown
python src/llamaparse_converter.py -i "$INPUT_PDF" -o "output/${BASENAME}_markdown.md"

# 2. Fix Markdown formatting with OpenAI
python src/markdown_fixer.py -i "output/${BASENAME}_markdown.md" -o "output/${BASENAME}_markdown.md"

# 3. Extract claims from cleaned markdown with OpenAI
python src/extract_claims.py -i "output/${BASENAME}_markdown.md" -o "output/${BASENAME}_claims.json"

# 4. Extract metadata from cleaned markdown with OpenAI
python src/extract_metadata.py -i "output/${BASENAME}_markdown.md" -o "output/${BASENAME}_metadata.json"

# 5. Compare extracted claims to the database
python src/compare_claims_to_db.py -c "output/${BASENAME}_claims.json" -o "output/${BASENAME}_claim_matches.json"

# 6. Generate formatted markdown from claim matches and metadata
python src/claim_matches_to_markdown.py -m "output/${BASENAME}_metadata.json" -c "output/${BASENAME}_claim_matches.json" -o "output/${BASENAME}_claim_matches_formatted.md"