import json
from openai import OpenAI
from dotenv import load_dotenv
import argparse
import os

load_dotenv()

# Read the extraction prompt
with open('src/prompts/extract_claims_prompt.txt', 'r') as f:
    prompt_template = f.read()

# Read the cleaned markdown content
with open('output/output_cleaned.md', 'r') as f:
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

parser = argparse.ArgumentParser(description="Extract claims from markdown using OpenAI.")
parser.add_argument('-o', '--output', default='output/extracted_claims.json', help='Output file path (default: output/extracted_claims.json)')
args = parser.parse_args()

# Write to output file
with open(args.output, 'w') as f:
    f.write(raw)

print(f"Extraction complete. Results written to {args.output}.")

with open(args.output, 'r', encoding='utf-8') as f:
    raw = f.read()
    raw = clean_json_markdown_wrapping(raw)
    claims = json.loads(raw) 