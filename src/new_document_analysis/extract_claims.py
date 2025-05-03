import json
from openai import OpenAI
from dotenv import load_dotenv
import argparse
import os
import sys

load_dotenv()

parser = argparse.ArgumentParser(description="Extract claims from markdown using OpenAI.")
parser.add_argument('-i', '--input', default=None, help='Input cleaned markdown file (default: output/{basename}_cleaned.md)')
parser.add_argument('-o', '--output', default=None, help='Output file path (default: output/{basename}_claims.json)')
args = parser.parse_args()

# Determine base name
if args.input is None:
    # Try to find a cleaned markdown file in output/
    import glob
    md_files = glob.glob('output/*_cleaned.md')
    if md_files:
        input_md = md_files[0]
    else:
        input_md = 'output/output_cleaned.md'
else:
    input_md = args.input
base_name = os.path.splitext(os.path.basename(input_md))[0]
base_name = base_name.replace('_markdown', '').replace('_cleaned', '')
if args.output is None:
    output_json = f'output/{base_name}_claims.json'
else:
    output_json = args.output
print(f"BASENAME:{base_name}", file=sys.stderr)

# Read the extraction prompt
with open('src/prompts/extract_claims_prompt.txt', 'r') as f:
    prompt_template = f.read()

# Read the cleaned markdown content
with open(input_md, 'r') as f:
    markdown_content = f.read()

# Insert the markdown content into the prompt
prompt = prompt_template.replace('{text}', markdown_content)

# Call the OpenAI API
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,
    max_tokens=32768,
)

# Parse the response (should be a JSON array)
claims_json = response.choices[0].message.content.strip()

def clean_json_markdown_wrapping(text):
    lines = text.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)

raw = clean_json_markdown_wrapping(claims_json)
claims = json.loads(raw)

# Write to output file
with open(output_json, 'w') as f:
    f.write(raw)

print(f"Extraction complete. Results written to {output_json}.")

with open(output_json, 'r', encoding='utf-8') as f:
    raw = f.read()
    raw = clean_json_markdown_wrapping(raw)
    claims = json.loads(raw) 