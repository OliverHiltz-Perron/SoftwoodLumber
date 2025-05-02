import json
import argparse
import pandas as pd
import openai
from tqdm import tqdm
import time

# Set your OpenAI API key here
import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
print(f"OpenAI API Key: {OPENAI_API_KEY}")  # Debugging line to check if the key is set
def load_json(file_path):
    """Load and parse the JSON file."""
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def select_best_citation_with_openai(proposition, database_matches):
    """
    Use OpenAI's API to select the best citation from the database matches.
    Returns the best match, choice number, and explanation why.
    """
    if not database_matches or len(database_matches) == 0:
        return None, "None", "No citations available"
    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    # Prepare the prompt
    prompt = f"""
    Original proposition: "{proposition}"
    
    Potential citations:
    1. "{database_matches[0]['db_propositions']}"
    2. "{database_matches[1]['db_propositions'] if len(database_matches) > 1 else 'None'}"
    3. "{database_matches[2]['db_propositions'] if len(database_matches) > 2 else 'None'}"
    
    Which of these citations (1, 2, or 3) is the best match for the original proposition? 
    If none of them is a good match, respond with "None".
    
    Respond in this format:
    Choice: [1, 2, or 3 or None]
    Why: [brief explanation of why this is or isn't a good match]
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Parse the response
        choice_line = [line for line in answer.split('\n') if line.startswith('Choice:')]
        why_line = [line for line in answer.split('\n') if line.startswith('Why:')]
        
        choice = "None"
        why = "No explanation provided"
        
        if choice_line:
            choice_text = choice_line[0].replace('Choice:', '').strip()
            choice = choice_text
        
        if why_line:
            why = why_line[0].replace('Why:', '').strip()
        # Process the choice
        if choice == "None" or choice.lower() == "none":
            return None, "None", why
        elif choice == "1":
            return database_matches[0], "1", why
        elif choice == "2" and len(database_matches) > 1:
            return database_matches[1], "2", why
        elif choice == "3" and len(database_matches) > 2:
            return database_matches[2], "3", why
        else:
            print(f"Unexpected response from API: {answer}")
            return None, choice, why
            
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        time.sleep(2)  # Wait a bit before retrying
        return None, "Error", f"API Error: {str(e)}"

def process_document(document):
    """Process a single document from the JSON data and return a DataFrame."""
    document_id = document.get('documentId', 'Unknown')
    print(f"Processing document: {document_id}")
    
    results = []
    
    # Process each proposition in the document
    for proposition in tqdm(document.get('propositions', []), desc="Processing propositions"):
        prop_id = proposition.get('id', 'Unknown')
        clean_text = proposition.get('cleanText', '')
        database_matches = proposition.get('closest_database_matches', [])
        
        best_citation, choice, explanation = select_best_citation_with_openai(clean_text, database_matches)
        
        # Record the result
        citation_text = best_citation['db_propositions'] if best_citation else "No good match found"
        citation_id = best_citation['id'] if best_citation else "None"
        similarity_score = best_citation['similarity'] if best_citation else 0.0
        
        result = {
            'proposition_id': prop_id,
            'proposition_text': clean_text,
            'api_choice': choice,
            'citation_text': citation_text,
            'citation_id': citation_id,
            'similarity_score': similarity_score,
            'explanation': explanation
        }
        results.append(result)
        
        # Add a small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Create DataFrame from results
    return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description='Select best citations for propositions.')
    parser.add_argument('--input', required=True, help='Path to the input JSON file')
    parser.add_argument('--output', default='best_citations.csv', help='Path to the output CSV file')
    args = parser.parse_args()
    
    # Check if API key is set
    if not OPENAI_API_KEY:
        print("Please set your OpenAI API key in the environment variable OPENAI_API_KEY.")
        return

    
    # Load the JSON data
    data = load_json(args.input)
    
    # Initialize empty DataFrame
    all_results = pd.DataFrame(columns=['proposition_id', 'proposition_text', 'api_choice', 
                                        'citation_text', 'citation_id', 'similarity_score', 'explanation'])
    
    # Process each document in the data
    for document in data:
        document_results = process_document(document)
        all_results = pd.concat([all_results, document_results], ignore_index=True)
    
    # Save the results to CSV
    all_results.to_csv(args.output, index=False)
    print(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()