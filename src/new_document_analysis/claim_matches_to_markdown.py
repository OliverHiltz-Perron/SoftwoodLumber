import json
from pathlib import Path
import argparse
import sys
import os

parser = argparse.ArgumentParser(description='Format claim matches and metadata to markdown.')
parser.add_argument('-m', '--metadata', default=None, help='Metadata JSON file (default: output/{basename}.json)')
parser.add_argument('-c', '--claim_matches', default=None, help='Claim matches JSON file (default: output/{basename}_claim_matches.json)')
parser.add_argument('-o', '--output', default=None, help='Output markdown file (default: output/{basename}_claim_matches_formatted.md)')
args = parser.parse_args()

# Determine base name
if args.metadata is None:
    import glob
    meta_files = glob.glob('output/*.json')
    meta_files = [f for f in meta_files if not f.endswith('_claim_matches.json') and not f.endswith('_claims.json')]
    if meta_files:
        metadata_path = meta_files[0]
    else:
        metadata_path = 'output/metadata.json'
else:
    metadata_path = args.metadata
base_name = os.path.splitext(os.path.basename(metadata_path))[0]
base_name = base_name.replace('_markdown', '').replace('_cleaned', '').replace('_claim_matches', '').replace('_metadata', '')
if args.claim_matches is None:
    claim_matches_path = f'output/{base_name}_claim_matches.json'
else:
    claim_matches_path = args.claim_matches
if args.output is None:
    output_md_path = f'output/{base_name}_claim_matches_formatted.md'
else:
    output_md_path = args.output
print(f"BASENAME:{base_name}", file=sys.stderr)

# Read metadata
with open(metadata_path, 'r', encoding='utf-8') as f:
    metadata = json.load(f)

title = metadata.get('Article_Title', 'Untitled')
tldr = metadata.get('TLDR_summary', '')
focus_area = metadata.get('Focus area', [])
if isinstance(focus_area, list):
    focus_area_str = ' | '.join(focus_area)
else:
    focus_area_str = str(focus_area)

# Read claim matches
with open(claim_matches_path, 'r', encoding='utf-8') as f:
    claim_matches = json.load(f)

# Organize claims by alignment
aligned_claims = []
partially_aligned_claims = []
not_aligned_claims = []

for claim_entry in claim_matches:
    claim = claim_entry.get('claim', '').strip()
    matches = claim_entry.get('matches', [])
    supporting = claim_entry.get('supporting_proposition', None)
    if supporting and supporting.get('llm_classification') == 'aligned':
        aligned_claims.append((claim_entry, claim, matches, supporting))
    elif supporting and supporting.get('llm_classification') == 'partially aligned':
        partially_aligned_claims.append((claim_entry, claim, matches, supporting))
    else:
        not_aligned_claims.append((claim_entry, claim, matches, supporting))

md_lines = []
md_lines.append(f"# {title}\n")
md_lines.append(f"**TL;DR:**  \n{tldr}\n")
md_lines.append(f"**Focus Area:**  \n{focus_area_str}\n")
md_lines.append("\n---\n")

# If there are no claims at all, return a single message
if not (aligned_claims or partially_aligned_claims or not_aligned_claims):
    md_lines.append("## No supporting propositions from the SLB database were found.\n")
else:
    # Section: Aligned
    md_lines.append("## Aligned\n")
    if aligned_claims:
        for idx, (claim_entry, claim, matches, supporting) in enumerate(aligned_claims, 1):
            md_lines.append(f"\n### Claim 1.{idx}  ")
            md_lines.append(f"*{claim}*\n")
            md_lines.append(f"**Aligned Matches:**  ")
            aligned_id = supporting.get('id')
            # List all matches as a single bullet list
            for match in matches:
                db_prop = match.get('db_propositions', '').replace('\\u2019', "'")
                similarity = match.get('similarity', 0)
                match_id = match.get('id', '')
                md_lines.append(f"* {db_prop} (Similarity: {similarity:.2f}) [ID: {match_id}]")
                md_lines.append("")  # Add a blank line to end the bullet list
            md_lines.append("\n---\n")
    else:
        md_lines.append("No aligned claims found.\n")

    # Section: Partially aligned
    md_lines.append("## Partially aligned\n")
    if partially_aligned_claims:
        for idx, (claim_entry, claim, matches, supporting) in enumerate(partially_aligned_claims, 1):
            md_lines.append(f"\n### Claim 2.{idx}  ")
            md_lines.append(f"*{claim}*\n")
            md_lines.append(f"**Partially Aligned Matches:**  ")
            aligned_id = supporting.get('id')
            # List all matches as a single bullet list
            for match in matches:
                db_prop = match.get('db_propositions', '').replace('\\u2019', "'")
                similarity = match.get('similarity', 0)
                match_id = match.get('id', '')
                md_lines.append(f"* {db_prop} (Similarity: {similarity:.2f}) [ID: {match_id}]")
                md_lines.append("")  # Add a blank line to end the bullet list
            md_lines.append("\n---\n")
    else:
        md_lines.append("No partially aligned claims found.\n")

    # Section: Not aligned
    md_lines.append("## Not aligned\n")
    if not_aligned_claims:
        for idx, (claim_entry, claim, matches, supporting) in enumerate(not_aligned_claims, 1):
            md_lines.append(f"\n### Claim 3.{idx}  ")
            md_lines.append(f"*{claim}*\n")
            md_lines.append(f"**Matches:**  ")
            if matches:
                for match in matches:
                    db_prop = match.get('db_propositions', '').replace('\\u2019', "'")
                    similarity = match.get('similarity', 0)
                    match_id = match.get('id', '')
                    md_lines.append(f"* {db_prop} (Similarity: {similarity:.2f}) [ID: {match_id}]")
                    md_lines.append("")  # Add a blank line to end the bullet list
            else:
                md_lines.append("- None found  ")
            md_lines.append("\n---\n")
    else:
        md_lines.append("All claims are aligned or partially aligned.\n---\n")

# Write to markdown file
with open(output_md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))

print(f"Markdown file generated at {output_md_path}") 