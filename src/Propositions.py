import sys
import os
import json
import datetime
import logging
import google.generativeai as genai
import re
import glob
from dotenv import load_dotenv
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
            logging.StreamHandler()
        ]
    )
    
    # Log startup information
    logging.info("="*50)
    logging.info(f"Starting proposition extraction with model: {MODEL_NAME}")
    logging.info(f"Max output tokens: {MAX_OUTPUT_TOKENS}")
    logging.info(f"Output will be saved to: {OUTPUT_FILENAME}")
    logging.info("="*50)

def read_file_content(filepath):
    """Reads the entire content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'")
        return None
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}")
        return None

def call_gemini(prompt_text, model_name):
    """Sends the prompt to the specified Gemini model and returns the response."""
    try:
        # Configure the API key (ensure GOOGLE_API_KEY environment variable is set)
        API_KEY = os.environ.get("GEMINI_API_KEY")
        if not API_KEY:
            logging.error("GEMINI_API_KEY environment variable not set")
            print("Error: GEMINI_API_KEY environment variable not set.")
            print("Please set the variable in your .env file:")
            print("GEMINI_API_KEY=your_api_key_here")
            return None

        genai.configure(api_key=API_KEY)

        # Initialize the Generative Model
        logging.info(f"Initializing Gemini model: {model_name}")
        print(f"Initializing Gemini model: {model_name}...")
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
        print("Sending prompt to Gemini...")
        
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
                print(f"Error: {error_msg}")
                # You might want to inspect response.prompt_feedback for details
            else:
                logging.error("Received an empty response from the API")
                print("Error: Received an empty response from the API.")
            return None

        response_text = response.text
        logging.info(f"Received response of length: {len(response_text)} characters")
        return response_text

    except Exception as e:
        error_msg = f"An error occurred during the Gemini API call: {str(e)}"
        logging.exception(error_msg)
        print(f"\n{error_msg}")
        # You might want to inspect the specific type of exception for more details
        # e.g., google.api_core.exceptions.PermissionDenied: 403 API key not valid
        # e.g., google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded
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

def save_propositions_json(results, output_filename=OUTPUT_FILENAME, append_mode=False):
    """
    Saves the extracted propositions to a JSON file.
    
    Args:
        results: List of document processing results
        output_filename: Name of the output JSON file
        append_mode: If True, appends to existing file; if False, overwrites
    """
    try:
        # Check if we need to append to existing file
        if append_mode and os.path.exists(output_filename):
            # Read existing JSON
            with open(output_filename, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                    
                    # Make sure it's not empty
                    if existing_data:
                        # If results contains only one or two items (metadata + new doc),
                        # we want to append to the full existing data
                        if len(results) <= 2:
                            # Add only the new document (not metadata) to existing data
                            for item in results:
                                if item.get('documentId') != 'metadata':
                                    existing_data.append(item)
                        else:
                            # This is the full data set, just use it
                            existing_data = results
                        
                        # Write updated JSON
                        with open(output_filename, 'w', encoding='utf-8') as f_out:
                            json.dump(existing_data, f_out, indent=2)
                            
                        logging.info(f"Appended new results to {output_filename}")
                        return
                except json.JSONDecodeError:
                    # If the file is corrupted, overwrite it
                    logging.warning(f"Existing JSON file {output_filename} is corrupted, overwriting")
                    # Fall through to create new file
                    
        # Write or overwrite JSON file
        logging.info(f"Saving results to {output_filename}")
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        # Count total propositions
        total_propositions = sum(
            len(doc.get('propositions', [])) 
            for doc in results 
            if doc.get('documentId') != 'metadata'
        )
        
        logging.info(f"Successfully saved {total_propositions} propositions across {len(results)-1} documents")
        
        if not append_mode:
            print(f"\nSuccessfully saved all propositions to {output_filename}")
        else:
            print(f"Appended latest results to {output_filename}")
    
    except Exception as e:
        error_msg = f"Error saving JSON output: {str(e)}"
        logging.exception(error_msg)
        print(error_msg)

def process_file(input_file_path, all_results):
    """Process a single file and extract propositions."""
    # Get document ID from filename
    doc_id = extract_filename(input_file_path)
    print(f"\nProcessing file: {os.path.basename(input_file_path)}")
    logging.info(f"Processing file: {input_file_path} (ID: {doc_id})")
    
    # Read the prompt template - look for it in the script directory first, then try relative path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, PROMPT_FILENAME)
    
    # If not found in script directory, try looking in parent directory
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(script_dir, "..", PROMPT_FILENAME)
    
    logging.info(f"Looking for prompt template at: {prompt_path}")
    prompt_template = read_file_content(prompt_path)
    
    if prompt_template is None:
        logging.error(f"Failed to read prompt template from {prompt_path}")
        print(f"Error: Failed to find or read prompt template from {prompt_path}")
        return False
    
    # Check for placeholder
    if PLACEHOLDER not in prompt_template:
        logging.error(f"Placeholder '{PLACEHOLDER}' not found in '{prompt_path}'.")
        print(f"Error: Placeholder '{PLACEHOLDER}' not found in '{prompt_path}'.")
        return False
    
    # Read the input markdown content
    input_content = read_file_content(input_file_path)
    if input_content is None:
        logging.error(f"Failed to read content from {input_file_path}")
        return False
    
    # Log file size and character count
    logging.info(f"File size: {os.path.getsize(input_file_path)} bytes, {len(input_content)} characters")
    
    # Create the final prompt
    try:
        final_prompt = prompt_template.format(content=input_content)
        print("\n--- Generated Prompt (Sent to Gemini) ---")
        print(final_prompt[:300] + "..." if len(final_prompt) > 300 else final_prompt)
        print("--- End of Generated Prompt ---")
    except KeyError as e:
        print(f"Error during formatting. Found unexpected placeholder key: {e}")
        print(f"Ensure prompt template uses exactly '{PLACEHOLDER}'.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during formatting: {e}")
        return False
    
    # Call the Gemini API
    gemini_response = call_gemini(final_prompt, MODEL_NAME)
    
    # Process and save the response
    if gemini_response:
        print("\n--- Gemini Response ---")
        response_preview = gemini_response[:300] + "..." if len(gemini_response) > 300 else gemini_response
        print(response_preview)
        print("--- End of Gemini Response ---")
        
        # Process the propositions for JSON format
        process_result = {
            "documentId": doc_id,
            "filename": os.path.basename(input_file_path),
            "processingDate": datetime.datetime.now().isoformat(),
            "propositions": []
        }
        
        # Check if the response is "NA" (not applicable)
        if gemini_response.strip() == "NA":
            logging.info(f"Document '{doc_id}' marked as not relevant to wood industry")
            print(f"No propositions found for {doc_id} (not relevant to wood industry)")
            process_result["status"] = "NOT_RELEVANT"
            all_results.append(process_result)
            
            # Save after each file is processed - only sending the new document, not the full array
            save_propositions_json([all_results[0], process_result], append_mode=True)
                
            return True
        
        # Split the response by semicolons
        propositions = [p.strip() for p in gemini_response.split(';') if p.strip()]
        logging.info(f"Extracted {len(propositions)} propositions from {doc_id}")
        
        # Process each proposition
        for i, proposition in enumerate(propositions, 1):
            proposition_id = f"{doc_id}_{i}"
            source_text = find_text_for_proposition(input_content, proposition)
            
            process_result["propositions"].append({
                "id": proposition_id,
                "text": proposition,
                "sourceText": source_text
            })
            logging.debug(f"Added proposition {proposition_id}")
        
        process_result["status"] = "SUCCESS"
        process_result["count"] = len(propositions)
        all_results.append(process_result)
        
        print(f"Successfully processed {len(propositions)} propositions from {doc_id}")
        
        # Save after each file is processed - only sending the new document, not the full array
        save_propositions_json([all_results[0], process_result], append_mode=True)
            
        return True
    else:
        logging.error(f"Failed to get response from Gemini for {doc_id}")
        print("\nFailed to get a response from Gemini.")
        error_result = {
            "documentId": doc_id,
            "filename": os.path.basename(input_file_path),
            "processingDate": datetime.datetime.now().isoformat(),
            "status": "ERROR",
            "propositions": []
        }
        all_results.append(error_result)
        
        # Save after each file is processed - only sending the new document, not the full array
        save_propositions_json([all_results[0], error_result], append_mode=True)
            
        return False

def main():
    # Set up logging
    setup_logging()
    
    # Initialize results list for JSON
    all_results = []
    
    # Add metadata
    metadata = {
        "documentId": "metadata",
        "generatedDate": datetime.datetime.now().isoformat(),
        "tool": "Propositions.py",
        "model": MODEL_NAME,
        "generationParams": {
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "temperature": TEMPERATURE
        },
        "type": "metadata"
    }
    all_results.append(metadata)
    
    # Create initial JSON file with just metadata
    save_propositions_json(all_results, append_mode=True)
    
    # Get parent directory path
    parent_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    
    # Check if fixed_markdown directory exists
    fixed_markdown_dir = os.path.join(parent_directory, "fixed_markdown")
    
    if os.path.exists(fixed_markdown_dir) and os.path.isdir(fixed_markdown_dir):
        logging.info(f"The 'fixed_markdown' folder exists. Using markdown files from this folder.")
        print(f"The 'fixed_markdown' folder exists. Using markdown files from this folder.")
        # Get all markdown files from the fixed_markdown folder
        input_files = glob.glob(os.path.join(fixed_markdown_dir, "*.md"))
    else:
        logging.info(f"No 'fixed_markdown' folder found. Using markdown files from the parent directory.")
        print(f"No 'fixed_markdown' folder found. Using markdown files from the parent directory.")
        # Get all markdown files from the parent directory
        input_files = glob.glob(os.path.join(parent_directory, "*.md"))
    
    # Filter out README.md files (case-insensitive)
    filtered_files = []
    for file_path in input_files:
        filename = os.path.basename(file_path).lower()
        if filename != "readme.md":
            filtered_files.append(file_path)
        else:
            logging.info(f"Skipping README file: {file_path}")
            print(f"Skipping README file: {file_path}")
    
    file_count = len(filtered_files)
    
    if file_count == 0:
        logging.warning(f"No valid .md files found in the search directory")
        print(f"Warning: No valid .md files found in the search directory")
        sys.exit(0)
    
    logging.info(f"Found {file_count} valid .md files (excluding README)")
    print(f"Found {file_count} valid .md files (excluding README)")
    
    success_count = 0
    error_count = 0
    
    for index, file_path in enumerate(filtered_files, 1):
        logging.info(f"Processing file {index}/{file_count}: {file_path}")
        print(f"\nProcessing file {index}/{file_count}: {os.path.basename(file_path)}")
        
        if process_file(file_path, all_results):
            success_count += 1
        else:
            error_count += 1
    
    logging.info(f"Processing complete. Success: {success_count}, Errors: {error_count}")
    print(f"\nProcessing complete. Successfully processed {success_count} out of {file_count} files.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Process interrupted by user")
        print("\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logging.exception(f"Unhandled exception: {str(e)}")
        print(f"\nAn unexpected error occurred: {str(e)}")
        sys.exit(1)