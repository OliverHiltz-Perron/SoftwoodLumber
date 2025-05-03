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

md_lines = []
md_lines.append(f"# {title}\n")
md_lines.append(f"**TL;DR:**  \n{tldr}\n")
md_lines.append(f"**Focus Area:**  \n{focus_area_str}\n")
md_lines.append("\n---\n")

# New report: For each claim, show ranked propositions, bolding strong evidence
for idx, claim_entry in enumerate(claim_matches, 1):
    claim = claim_entry.get('claim', '').strip()
    ranked_props = claim_entry.get('ranked_propositions', [])
    md_lines.append(f"\n### Claim {idx}\n")
    md_lines.append(f"*{claim}*\n")
    if ranked_props:
        for prop in sorted(ranked_props, key=lambda x: x.get('rank', 9999)):
            text = prop.get('proposition', '').replace('\\u2019', "'")
            similarity = prop.get('similarity', None)
            match_id = prop.get('id', '')
            bullet = f"* "
            if prop.get('evidence_strength') == 'strong':
                bullet += f"**{text}"
            else:
                bullet += text
            if similarity is not None:
                bullet += f" (Similarity: {similarity:.2f})"
            if match_id:
                bullet += f" [ID: {match_id}]"
            if prop.get('evidence_strength') == 'strong':
                bullet += "**"
            md_lines.append(bullet)
            md_lines.append("")
    else:
        md_lines.append("- No propositions found\n")
    md_lines.append("\n---\n")

# Write to markdown file
with open(output_md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))

# Add references section
references_lines = []
references_lines.append("\n## References\n")
for idx, claim_entry in enumerate(claim_matches, 1):
    ranked_props = claim_entry.get('ranked_propositions', [])
    if ranked_props:
        references_lines.append(f"\n*Claim {idx}:*")
        for prop in sorted(ranked_props, key=lambda x: x.get('rank', 9999)):
            match_id = prop.get('id', '')
            file_name = prop.get('file_name', '')
            if match_id or file_name:
                if prop.get('evidence_strength') == 'strong':
                    references_lines.append(f"- *[{match_id}] {file_name}*")
                else:
                    references_lines.append(f"- [{match_id}] {file_name}")
if references_lines:
    with open(output_md_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(references_lines))

print(f"Markdown file generated at {output_md_path}") 