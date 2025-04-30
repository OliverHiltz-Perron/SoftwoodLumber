import sys
import os
import json
import re
import logging
import datetime
import time
from pathlib import Path

# Function to set up logging
def setup_logging(log_file="proposition_extraction.log"):
    """Configure logging for the application."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "streamlit_app", "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    
    logging.info("="*50)
    logging.info(f"Starting proposition extraction")
    logging.info("="*50)
    
    return log_path

# Helper function to read file content
def read_file_content(filepath):
    """Reads the entire content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"Error: File not found at '{filepath}'")
        return None
    except Exception as e:
        logging.error(f"Error reading file '{filepath}': {e}")
        return None

# Helper function to extract filename-based document ID
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

# Helper function to find original text for a proposition
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

# Function to call Gemini API
def call_gemini(prompt_text, model_name, api_key, temperature=0.2, max_tokens=65536):
    """Sends the prompt to the specified Gemini model and returns the response."""
    try:
        # Configure the API key
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Initialize the Generative Model
        logging.info(f"Initializing Gemini model: {model_name}")
        model = genai.GenerativeModel(model_name)

        # Set generation config
        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature
        }
        logging.debug(f"Generation config: {generation_config}")

        # Generate content
        prompt_length = len(prompt_text)
        logging.info(f"Sending prompt to Gemini (length: {prompt_length} characters)")
        
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
                return None
            else:
                logging.error("Received an empty response from the API")
                return None

        response_text = response.text
        logging.info(f"Received response of length: {len(response_text)} characters")
        return response_text

    except Exception as e:
        error_msg = f"An error occurred during the Gemini API call: {str(e)}"
        logging.exception(error_msg)
        return None

# Function to process a single file
def process_file(file_path, prompt_template, model_name, api_key, all_results, status_callback=None, progress_callback=None, temperature=0.2, max_tokens=65536):
    """Process a single file and extract propositions."""
    # Get document ID from filename
    doc_id = extract_filename(file_path)
    logging.info(f"Processing file: {file_path} (ID: {doc_id})")
    
    if status_callback:
        status_callback(f"Processing: {os.path.basename(file_path)}")
    
    # Read the input markdown content
    input_content = read_file_content(file_path)
    if input_content is None:
        logging.error(f"Failed to read content from {file_path}")
        return False
    
    # Log file size and character count
    logging.info(f"File size: {os.path.getsize(file_path)} bytes, {len(input_content)} characters")
    
    # Create the final prompt
    try:
        placeholder = "{content}"
        if placeholder not in prompt_template:
            logging.error(f"Placeholder '{placeholder}' not found in prompt template.")
            return False
            
        final_prompt = prompt_template.replace(placeholder, input_content)
    except Exception as e:
        logging.error(f"An error formatting the prompt: {e}")
        return False
    
    # Call the Gemini API
    gemini_response = call_gemini(final_prompt, model_name, api_key, temperature, max_tokens)
    
    # Process and save the response
    if gemini_response:
        # Process the propositions for JSON format
        process_result = {
            "documentId": doc_id,
            "filename": os.path.basename(file_path),
            "processingDate": datetime.datetime.now().isoformat(),
            "propositions": []
        }
        
        # Check if the response is "NA" (not applicable)
        if gemini_response.strip() == "NA":
            logging.info(f"Document '{doc_id}' marked as not relevant to wood industry")
            if status_callback:
                status_callback(f"No propositions found for {doc_id} (not relevant to wood industry)")
            process_result["status"] = "NOT_RELEVANT"
            all_results.append(process_result)
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
        
        if status_callback:
            status_callback(f"Processed {len(propositions)} propositions from {os.path.basename(file_path)}")
            
        return True
    else:
        logging.error(f"Failed to get response from Gemini for {doc_id}")
        
        error_result = {
            "documentId": doc_id,
            "filename": os.path.basename(file_path),
            "processingDate": datetime.datetime.now().isoformat(),
            "status": "ERROR",
            "propositions": []
        }
        all_results.append(error_result)
        return False

# Function to save JSON results
def save_proposition_results(results, output_dir=None):
    """Saves the extracted propositions to JSON files."""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "streamlit_app", "data", "propositions")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Save individual document results
    for doc_result in results:
        if doc_result.get("documentId") != "metadata":
            json_filename = f"{os.path.splitext(doc_result['filename'])[0]}_propositions.json"
            output_path = os.path.join(output_dir, json_filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(doc_result, f, indent=2)
    
    # Save combined results
    combined_json_filename = f"extracted_propositions_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    combined_json_path = os.path.join(output_dir, combined_json_filename)
    
    with open(combined_json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    return combined_json_path

# Get default prompt template
def get_default_prompt_template():
    """Returns the default prompt template for proposition extraction."""
    return """You are analyzing a document to extract propositions related to the wood industry, lumber, timber, building with wood, or wood manufacturing.

A proposition is a declarative statement that makes a claim or assertion that can be judged as true or false. Focus on extracting key claims about wood, timber, lumber, or forestry products in construction, manufacturing, or industry.

For this task:
1. Extract ONLY propositions specifically related to wood, timber, lumber usage, or wood products.
2. Focus on statements of fact, industry trends, market conditions, technical properties, or forecasts.
3. Ignore statements that are purely descriptive and don't make clear claims.
4. Do not extract general statements that are not specifically about wood/timber/lumber.
5. Extract only complete, standalone propositions - not fragments or partial thoughts.
6. Use exact wording from the text, but make minor adjustments if needed for clarity.
7. Separate each distinct proposition with a semicolon (;).
8. If the document contains no relevant propositions about wood/lumber/timber, respond with "NA".

Here is the document to analyze:

{content}

Now extract the key propositions related to wood, timber, or lumber from this text:"""