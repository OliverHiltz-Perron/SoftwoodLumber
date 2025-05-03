import json
from pathlib import Path

# Paths
metadata_path = Path('output/metadata.json')
claim_matches_path = Path('output/claim_matches.json')
output_md_path = Path('output/claim_matches_formatted.md')

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

# Start markdown content
md_lines = []
md_lines.append(f"# {title}\n")
md_lines.append(f"**TL;DR:**  \n{tldr}\n")
md_lines.append(f"**Focus Area:**  \n{focus_area_str}\n")
md_lines.append("\n---\n")
md_lines.append("## Claims and Matched Propositions\n")

for idx, claim_entry in enumerate(claim_matches, 1):
    claim = claim_entry.get('claim', '').strip()
    matches = claim_entry.get('matches', [])
    md_lines.append(f"\n### Claim {idx}  ")
    md_lines.append(f"*{claim}*\n")
    md_lines.append(f"**Matches:**  ")
    if matches:
        for match in matches:
            db_prop = match.get('db_propositions', '').replace('\\u2019', "'")
            match_id = match.get('id', '')
            similarity = match.get('similarity', 0)
            md_lines.append(f"- {db_prop} (Similarity: {similarity:.2f}) [ID: {match_id}]  ")
    else:
        md_lines.append("- None found  ")
    md_lines.append("\n---\n")

# Write to markdown file
with open(output_md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))

print(f"Markdown file generated at {output_md_path}") 