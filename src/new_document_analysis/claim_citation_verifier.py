import os
import json
import openai
from dotenv import load_dotenv
import sys
import re
import argparse

# Load environment variables
load_dotenv()

PROMPT_PATH = "src/prompts/claim_proposition_citation_check.txt"

MODEL = "gpt-4.1-mini"
TEMPERATURE = 0.1
MAX_TOKENS = 256


def load_prompt_template(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def load_claim_matches(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_claim_matches(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_proposition_supports_claim(client, prompt_template, claim, proposition):
    prompt = prompt_template.replace("{{claim}}", claim).replace("{{proposition}}", proposition)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    answer = response.choices[0].message.content.strip()
    answer_lower = answer.lower()
    # Extract classification and justification
    match = re.match(r"(aligned|partially aligned|not aligned)\s*:\s*(.*)", answer_lower, re.IGNORECASE)
    if match:
        classification = match.group(1).strip()
        justification = answer[len(match.group(1)):].lstrip(':').strip()
    else:
        # fallback: treat the whole answer as justification
        classification = None
        justification = answer
    if classification in ["aligned", "partially aligned"]:
        return True, (classification, justification)
    return False, (classification, justification)

def main():
    parser = argparse.ArgumentParser(description='Verify claim citations using LLM.')
    parser.add_argument('-i', '--input', type=str, default="output/WoodAsBuildingMaterial_claim_matches.json", help='Input claim matches JSON file')
    parser.add_argument('-o', '--output', type=str, default=None, help='Output claim matches JSON file (default: overwrite input)')
    args = parser.parse_args()

    # Standardize base name
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    base_name = base_name.replace('_markdown', '').replace('_cleaned', '').replace('_claim_matches', '')
    if args.output is None:
        output_path = f'output/{base_name}_claim_matches.json'
    else:
        output_path = args.output
    print(f"BASENAME:{base_name}", file=sys.stderr)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Please set the OPENAI_API_KEY environment variable.", file=sys.stderr)
        return 1
    client = openai.OpenAI(api_key=api_key)
    prompt_template = load_prompt_template(PROMPT_PATH)
    claim_matches = load_claim_matches(args.input)
    updated = 0
    no_support = 0
    print("\n===== Starting Claim Citation Verification =====\n")
    for idx, entry in enumerate(claim_matches):
        claim = entry.get("claim", "")
        matches = entry.get("matches", [])
        print(f"\n--- Claim {idx+1}/{len(claim_matches)} ---\n{claim}\n{'-'*40}")
        supporting = None
        for m_idx, match in enumerate(matches):
            prop_text = match.get("db_propositions", "")
            print(f"  Checking proposition {m_idx+1}/{len(matches)}:")
            print(f"    {prop_text}")
            is_support, answer = check_proposition_supports_claim(client, prompt_template, claim, prop_text)
            print(f"    LLM answer: {answer}")
            if is_support:
                supporting = {
                    "id": match.get("id"),
                    "db_propositions": prop_text,
                    "llm_classification": answer[0],
                    "llm_justification": answer[1]
                }
                print("    -> This proposition WILL be used as a citation.\n")
                updated += 1
                break
            else:
                print("    -> Not sufficient as a citation.")
        if not supporting:
            print("  !! No supporting proposition found for this claim.\n")
            no_support += 1
        entry["supporting_proposition"] = supporting
    save_claim_matches(output_path, claim_matches)
    print("\n===== Claim Citation Verification Complete =====\n")
    print(f"Claims with supporting proposition: {updated}")
    print(f"Claims without supporting proposition: {no_support}")
    print(f"Total claims processed: {len(claim_matches)}\n")
    print("Sample output (first 2 claims):\n" + "="*40)
    for entry in claim_matches[:2]:
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        print("\n" + "-"*40 + "\n")

if __name__ == "__main__":
    main() 