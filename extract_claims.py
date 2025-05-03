import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Read the extraction prompt
with open('src/prompts/extract_claims_prompt.txt', 'r') as f:
    prompt_template = f.read()

# Read the cleaned markdown content
with open('output_cleaned.md', 'r') as f:
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

# Write to output file
with open('extracted_claims.json', 'w') as f:
    f.write(claims_json)

print("Extraction complete. Results written to extracted_claims.json.") 