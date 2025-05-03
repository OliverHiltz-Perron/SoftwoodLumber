#!/bin/bash

# Loop over all PDF files in the input directory
for INPUT_PDF in input/*.pdf; do
  BASENAME=$(basename "$INPUT_PDF" .pdf)

  # 1. Convert PDF to Markdown
  python src/new_document_analysis/llamaparse_converter.py -i "$INPUT_PDF" -o "output/${BASENAME}_markdown.md"

  # 2. Fix Markdown formatting with OpenAI
  python src/new_document_analysis/markdown_fixer.py -i "output/${BASENAME}_markdown.md" -o "output/${BASENAME}_markdown.md"

  # 3. Extract claims from cleaned markdown with OpenAI
  python src/new_document_analysis/extract_claims.py -i "output/${BASENAME}_markdown.md" -o "output/${BASENAME}_claims.json"

  # 4. Extract metadata from cleaned markdown with OpenAI
  python src/new_document_analysis/extract_metadata.py -i "output/${BASENAME}_markdown.md" -o "output/${BASENAME}_metadata.json"

  # 5. Compare extracted claims to the database
  python src/new_document_analysis/compare_claims_to_db.py -c "output/${BASENAME}_claims.json" -o "output/${BASENAME}_claim_matches.json"

  # 5.5. Verify claim citations using LLM
  python src/new_document_analysis/claim_citation_verifier.py -i "output/${BASENAME}_claim_matches.json" -o "output/${BASENAME}_claim_matches.json"

  # 6. Generate formatted markdown from claim matches and metadata
  python src/new_document_analysis/claim_matches_to_markdown.py -m "output/${BASENAME}_metadata.json" -c "output/${BASENAME}_claim_matches.json" -o "output/${BASENAME}_claim_matches_formatted.md"
done