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

def rank_and_annotate_propositions(client, prompt_template, claim, propositions):
    # Format the propositions as a numbered list for the prompt
    prop_list = "\n".join([f"{i+1}. {p}" for i, p in enumerate(propositions)])
    prompt = prompt_template.replace("{{claim}}", claim).replace("{{propositions}}", prop_list)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
        max_tokens=2048,
    )
    answer = response.choices[0].message.content.strip()
    # Try to extract JSON from the response
    try:
        ranked = json.loads(answer)
    except Exception:
        # Fallback: try to extract JSON substring
        match = re.search(r'(\[.*\])', answer, re.DOTALL)
        if match:
            ranked = json.loads(match.group(1))
        else:
            print(f"Could not parse LLM output as JSON for claim: {claim}", file=sys.stderr)
            ranked = []
    return ranked

def main():
    parser = argparse.ArgumentParser(description='Rank and annotate claim citations using LLM.')
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
    print("\n===== Starting Claim Proposition Ranking =====\n")
    for idx, entry in enumerate(claim_matches):
        claim = entry.get("claim", "")
        matches = entry.get("matches", [])
        propositions = [m.get("db_propositions", "") for m in matches]
        print(f"\n--- Claim {idx+1}/{len(claim_matches)} ---\n{claim}\n{'-'*40}")
        if not propositions:
            entry["ranked_propositions"] = []
            continue
        ranked = rank_and_annotate_propositions(client, prompt_template, claim, propositions)
        # Attach the original match metadata to the ranked output
        ranked_with_ids = []
        for r in ranked:
            # Find the original match for this proposition
            match = next((m for m in matches if m.get("db_propositions", "") == r["proposition"]), None)
            if match:
                ranked_with_ids.append({
                    "proposition": r["proposition"],
                    "rank": r["rank"],
                    "evidence_strength": r["evidence_strength"],
                    "id": match.get("id"),
                    "similarity": match.get("similarity")
                })
            else:
                ranked_with_ids.append(r)
        entry["ranked_propositions"] = ranked_with_ids
        # Remove old supporting_proposition if present
        if "supporting_proposition" in entry:
            del entry["supporting_proposition"]
    save_claim_matches(output_path, claim_matches)
    print("\n===== Claim Proposition Ranking Complete =====\n")
    print(f"Total claims processed: {len(claim_matches)}\n")
    print("Sample output (first 2 claims):\n" + "="*40)
    for entry in claim_matches[:2]:
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        print("\n" + "-"*40 + "\n")

if __name__ == "__main__":
    main() 