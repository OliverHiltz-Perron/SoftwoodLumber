import sys
import os
import json
import datetime
import logging
import google.generativeai as genai
import re
import glob
from dotenv import load_dotenv
import argparse
load_dotenv()

# --- Configuration ---
# Update the path to look in the prompts folder
PROMPT_FILENAME = os.path.join("prompts", "Proposition.md")
PLACEHOLDER = "{content}"
# Choose your Gemini model (e.g., 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-pro')
# See available models: https://ai.google.dev/models/gemini
# Configure the Gemini model you want to use
MODEL_NAME = "gemini-2.5-flash-preview-04-17" # Or "gemini-pro", "gemini-1.5-pro", etc.
OUTPUT_FILENAME = "extracted_propositions.json"

# Model generation parameters
MAX_OUTPUT_TOKENS = 65536  # Maximum tokens for Gemini response
TEMPERATURE = 0.2  # Lower temperature for more deterministic/focused output

# Logging configuration
LOG_LEVEL = logging.INFO  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE = "proposition_extraction.log"

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stderr)  # Log to stderr instead of stdout for pipeline compatibility
        ]
    )
    
    # Log startup information
    logging.info("="*50)
    logging.info(f"Starting proposition extraction with model: {MODEL_NAME}")
    logging.info(f"Max output tokens: {MAX_OUTPUT_TOKENS}")
    logging.info("="*50)

def read_file_content(filepath):
    """Reads the entire content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        return None

def call_gemini(prompt_text, model_name):
    """Sends the prompt to the specified Gemini model and returns the response."""
    try:
        # Configure the API key (ensure GOOGLE_API_KEY environment variable is set)
        API_KEY = os.environ.get("GEMINI_API_KEY")
        if not API_KEY:
            logging.error("GEMINI_API_KEY environment variable not set")
            print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
            print("Please set the variable in your .env file:", file=sys.stderr)
            print("GEMINI_API_KEY=your_api_key_here", file=sys.stderr)
            return None

        genai.configure(api_key=API_KEY)

        # Initialize the Generative Model
        logging.info(f"Initializing Gemini model: {model_name}")
        print(f"Initializing Gemini model: {model_name}...", file=sys.stderr)
        model = genai.GenerativeModel(model_name)

        # Set generation config with max output tokens
        generation_config = {
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": TEMPERATURE
        }
        logging.debug(f"Generation config: {generation_config}")

        # Generate content
        prompt_length = len(prompt_text)
        logging.info(f"Sending prompt to Gemini (length: {prompt_length} characters)")
        print("Sending prompt to Gemini...", file=sys.stderr)
        
        start_time = datetime.datetime.now()
        response = model.generate_content(
            prompt_text,
            generation_config=generation_config
        )
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logging.info(f"Received response from Gemini in {duration:.2f} seconds")

        # Handle potential safety blocks or empty responses
        if not response.parts:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                error_msg = f"Call blocked due to safety settings. Reason: {response.prompt_feedback.block_reason}"
                logging.error(error_msg)
                print(f"Error: {error_msg}", file=sys.stderr)
                # You might want to inspect response.prompt_feedback for details
            else:
                logging.error("Received an empty response from the API")
                print("Error: Received an empty response from the API.", file=sys.stderr)
            return None

        response_text = response.text
        logging.info(f"Received response of length: {len(response_text)} characters")
        return response_text

    except Exception as e:
        error_msg = f"An error occurred during the Gemini API call: {str(e)}"
        logging.exception(error_msg)
        print(f"\n{error_msg}", file=sys.stderr)
        # You might want to inspect the specific type of exception for more details
        return None

def extract_filename(filepath):
    """
    Extracts document ID from a filepath.
    Uses leading numbers from the filename, or first 10 characters if no numbers exist.
    """
    # Get just the base filename without extension
    base_name = os.path.basename(filepath)
    filename_without_ext = os.path.splitext(base_name)[0]
    
    # Extract leading numbers using regex
    leading_numbers = re.match(r'^(\d+)', filename_without_ext)
    
    if leading_numbers:
        # If there are leading numbers, use them as document ID
        doc_id = leading_numbers.group(1)
        logging.debug(f"Extracted document ID '{doc_id}' from filename '{base_name}'")
    else:
        # If no leading numbers, use first 10 characters (or all if < 10)
        doc_id = filename_without_ext[:10]
        logging.debug(f"No leading numbers found, using first 10 chars: '{doc_id}' from '{base_name}'")
    
    return doc_id

def find_text_for_proposition(original_text, proposition):
    """Attempts to find the original text that led to a proposition.
    Returns a snippet of text containing the proposition source."""
    # Simple heuristic: Find sentences or paragraphs that contain key terms from the proposition
    
    # Split the proposition into significant words (excluding common words)
    common_words = {'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is', 'are', 'be'}
    significant_words = [word.lower() for word in proposition.split() if word.lower() not in common_words and len(word) > 3]
    
    # If no significant words, return a default message
    if not significant_words:
        return "Source context not identified"
    
    # Split the original text into paragraphs
    paragraphs = original_text.split('\n\n')
    
    best_match = None
    highest_score = 0
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        paragraph_lower = paragraph.lower()
        score = 0
        
        # Calculate how many significant words appear in this paragraph
        for word in significant_words:
            if word in paragraph_lower:
                score += 1
        
        # Calculate match percentage
        match_percentage = score / len(significant_words) if significant_words else 0
        
        # Update best match if this paragraph has a higher score
        if match_percentage > highest_score:
            highest_score = match_percentage
            best_match = paragraph
    
    # If we found a reasonable match
    if highest_score > 0.3 and best_match:
        # Truncate if too long
        if len(best_match) > 250:
            words = best_match.split()
            if len(words) > 50:
                best_match = ' '.join(words[:50]) + '...'
        return best_match.strip()
    
    return "Source context not clearly identified"

def process_content(content, doc_id, prompt_template):
    """Process a single piece of content and extract propositions."""
    logging.info(f"Processing content (ID: {doc_id})")
    
    # Create the final prompt
    try:
        final_prompt = prompt_template.replace(PLACEHOLDER, content)
    except Exception as e:
        print(f"An error occurred during formatting: {e}", file=sys.stderr)
        return None
    
    # Call the Gemini API
    gemini_response = call_gemini(final_prompt, MODEL_NAME)
    
    # Process the response
    if gemini_response:
        # Process the propositions for JSON format
        process_result = {
            "documentId": doc_id,
            "processingDate": datetime.datetime.now().isoformat(),
            "propositions": []
        }
        
        # Check if the response is "NA" (not applicable)
        if gemini_response.strip() == "NA":
            process_result["status"] = "NOT_RELEVANT"
            return process_result
        
        # Split the response by semicolons
        propositions = [p.strip() for p in gemini_response.split(';') if p.strip()]
        logging.info(f"Extracted {len(propositions)} propositions from {doc_id}")
        
        # Process each proposition
        for i, proposition in enumerate(propositions, 1):
            proposition_id = f"{doc_id}_{i}"
            source_text = find_text_for_proposition(content, proposition)
            
            process_result["propositions"].append({
                "id": proposition_id,
                "text": proposition,
                "sourceText": source_text
            })
            logging.debug(f"Added proposition {proposition_id}")
        
        process_result["status"] = "SUCCESS"
        process_result["count"] = len(propositions)
        
        return process_result
    else:
        logging.error(f"Failed to get response from Gemini for {doc_id}")
        print("Failed to get a response from Gemini.", file=sys.stderr)
        return None

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Extract propositions from a Markdown file.")
    parser.add_argument("-i", "--input", default="-", 
                      help="Input Markdown file path. Use '-' for stdin (default)")
    parser.add_argument("-o", "--output", default="-", 
                      help="Output JSON file path. Use '-' for stdout (default)")
    parser.add_argument("--prompt", default=PROMPT_FILENAME,
                      help=f"Path to the prompt template file (default: {PROMPT_FILENAME})")
    parser.add_argument("--doc-id", default=None,
                      help="Document ID to use (default: generated from filename or timestamp)")
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging()
    
    # Read the prompt template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, args.prompt)
    
    # If not found in script directory, try looking in parent directory
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(script_dir, "..", args.prompt)
    
    logging.info(f"Looking for prompt template at: {prompt_path}")
    prompt_template = read_file_content(prompt_path)
    
    if prompt_template is None:
        logging.error(f"Failed to read prompt template from {prompt_path}")
        print(f"Error: Failed to find or read prompt template from {prompt_path}", file=sys.stderr)
        return 1
    
    # Read input content
    if args.input == '-':
        print("Reading from stdin...", file=sys.stderr)
        content = sys.stdin.read()
    else:
        print(f"Reading from file: {args.input}", file=sys.stderr)
        content = read_file_content(args.input)
        
    if not content:
        logging.error("Failed to read input content")
        print("Error: Input is empty or could not be read", file=sys.stderr)
        return 1
        
    # Get document ID
    if args.doc_id:
        doc_id = args.doc_id
    elif args.input == '-':
        doc_id = f"doc_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    else:
        doc_id = extract_filename(args.input)
    
    # Process the content
    result = process_content(content, doc_id, prompt_template)
    
    if result:
        # Output the result
        output_json = json.dumps(result, indent=2)
        
        if args.output == '-':
            # Write to stdout
            sys.stdout.write(output_json)
        else:
            # Write to file
            try:
                # Create output directory if needed
                output_dir = os.path.dirname(args.output)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output_json)
                print(f"Successfully wrote results to {args.output}", file=sys.stderr)
            except Exception as e:
                print(f"Error writing to output file: {e}", file=sys.stderr)
                return 1
        
        return 0
    else:
        print("Failed to process content", file=sys.stderr)
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.warning("Process interrupted by user")
        print("\nProcess interrupted by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logging.exception(f"Unhandled exception: {str(e)}")
        print(f"\nAn unexpected error occurred: {str(e)}", file=sys.stderr)
        sys.exit(1)