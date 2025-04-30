# backend/proposition_extraction_service.py

import os
import re
import json
import datetime
import logging
import google.generativeai as genai
import glob
from dotenv import load_dotenv

class PropositionExtractionService:
    """Service for extracting propositions from markdown files using Gemini API."""
    
    def __init__(self, api_key=None, prompt_template_path=None, model_name=None):
        """
        Initialize the Proposition Extraction service.
        
        Args:
            api_key (str, optional): Gemini API key. If None, will try to load from env vars.
            prompt_template_path (str, optional): Path to the prompt template file. If None, 
                                                 will look in default locations.
            model_name (str, optional): Name of the Gemini model to use. If None, defaults to
                                       'gemini-2.5-flash-preview-04-17'.
        """
        # Load API key from environment if not provided
        if not api_key:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables or .env file")
        
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        
        # Set model name
        self.model_name = model_name or "gemini-2.5-flash-preview-04-17"
        self.model = genai.GenerativeModel(self.model_name)
        
        # Model generation parameters
        self.max_output_tokens = 65536  # Maximum tokens for Gemini response
        self.temperature = 0.2  # Lower temperature for more deterministic/focused output
        
        # Configure generation settings
        self.generation_config = {
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature
        }
        
        # Configure safety settings
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Placeholder for prompt template
        self.placeholder = "{content}"
        
        # Load prompt template
        if prompt_template_path:
            self.prompt_template = self.read_file(prompt_template_path)
            if not self.prompt_template:
                raise ValueError(f"Failed to read prompt template from {prompt_template_path}")
        else:
            # Try to find prompt template in default locations
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_paths = [
                os.path.join(script_dir, "prompts", "Proposition.md"),
                os.path.join(script_dir, "..", "prompts", "Proposition.md"),
                os.path.join(script_dir, "..", "Proposition.md")
            ]
            
            for path in default_paths:
                if os.path.exists(path):
                    self.prompt_template = self.read_file(path)
                    if self.prompt_template:
                        break
            
            if not self.prompt_template:
                raise ValueError("Prompt template not found in default locations. Please provide a valid path.")
                
        # Check for placeholder in template
        if self.placeholder not in self.prompt_template:
            raise ValueError(f"Placeholder '{self.placeholder}' not found in prompt template.")
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging for the service."""
        # Create logger
        self.logger = logging.getLogger("PropositionExtraction")
        self.logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler
        file_handler = logging.FileHandler("proposition_extraction.log")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Log startup information
        self.logger.info("="*50)
        self.logger.info(f"Initialized proposition extraction with model: {self.model_name}")
        self.logger.info(f"Max output tokens: {self.max_output_tokens}")
        self.logger.info("="*50)
    
    def read_file(self, filepath):
        """Reads content from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            self.logger.error(f"Error: Input file not found at '{filepath}'")
            return None
        except Exception as e:
            self.logger.error(f"Error reading file '{filepath}': {e}")
            return None

    def write_file(self, filepath, content):
        """Writes content to a file."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Successfully wrote to '{filepath}'")
            return True
        except Exception as e:
            self.logger.error(f"Error writing file '{filepath}': {e}")
            return False

    def extract_filename(self, filepath):
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
            self.logger.debug(f"Extracted document ID '{doc_id}' from filename '{base_name}'")
        else:
            # If no leading numbers, use first 10 characters (or all if < 10)
            doc_id = filename_without_ext[:10]
            self.logger.debug(f"No leading numbers found, using first 10 chars: '{doc_id}' from '{base_name}'")
        
        return doc_id

    def find_text_for_proposition(self, original_text, proposition):
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

    def call_gemini(self, prompt_text):
        """Sends the prompt to the specified Gemini model and returns the response."""
        try:
            # Log prompt information
            prompt_length = len(prompt_text)
            self.logger.info(f"Sending prompt to Gemini (length: {prompt_length} characters)")
            
            start_time = datetime.datetime.now()
            response = self.model.generate_content(
                prompt_text,
                generation_config=self.generation_config
            )
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.info(f"Received response from Gemini in {duration:.2f} seconds")

            # Handle potential safety blocks or empty responses
            if not response.parts:
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    error_msg = f"Call blocked due to safety settings. Reason: {response.prompt_feedback.block_reason}"
                    self.logger.error(error_msg)
                else:
                    self.logger.error("Received an empty response from the API")
                return None

            response_text = response.text
            self.logger.info(f"Received response of length: {len(response_text)} characters")
            return response_text

        except Exception as e:
            error_msg = f"An error occurred during the Gemini API call: {str(e)}"
            self.logger.exception(error_msg)
            return None

    def process_file(self, input_file_path):
        """
        Process a single file and extract propositions.
        
        Args:
            input_file_path (str): Path to the markdown file to process
            
        Returns:
            dict: Processing results including propositions
        """
        # Get document ID from filename
        doc_id = self.extract_filename(input_file_path)
        self.logger.info(f"Processing file: {input_file_path} (ID: {doc_id})")
        
        # Read the input markdown content
        input_content = self.read_file(input_file_path)
        if input_content is None:
            self.logger.error(f"Failed to read content from {input_file_path}")
            return {
                "documentId": doc_id,
                "filename": os.path.basename(input_file_path),
                "processingDate": datetime.datetime.now().isoformat(),
                "status": "ERROR",
                "error": "Failed to read file",
                "propositions": []
            }
        
        # Log file size and character count
        self.logger.info(f"File size: {os.path.getsize(input_file_path)} bytes, {len(input_content)} characters")
        
        # Create the final prompt
        try:
            final_prompt = self.prompt_template.format(content=input_content)
        except Exception as e:
            self.logger.error(f"Error formatting prompt template: {e}")
            return {
                "documentId": doc_id,
                "filename": os.path.basename(input_file_path),
                "processingDate": datetime.datetime.now().isoformat(),
                "status": "ERROR",
                "error": f"Error formatting prompt: {str(e)}",
                "propositions": []
            }
        
        # Call the Gemini API
        gemini_response = self.call_gemini(final_prompt)
        
        # Process and save the response
        if gemini_response:
            # Process the propositions for JSON format
            process_result = {
                "documentId": doc_id,
                "filename": os.path.basename(input_file_path),
                "processingDate": datetime.datetime.now().isoformat(),
                "propositions": []
            }
            
            # Check if the response is "NA" (not applicable)
            if gemini_response.strip() == "NA":
                self.logger.info(f"Document '{doc_id}' marked as not relevant to wood industry")
                process_result["status"] = "NOT_RELEVANT"
                return process_result
            
            # Split the response by semicolons
            propositions = [p.strip() for p in gemini_response.split(';') if p.strip()]
            self.logger.info(f"Extracted {len(propositions)} propositions from {doc_id}")
            
            # Process each proposition
            for i, proposition in enumerate(propositions, 1):
                proposition_id = f"{doc_id}_{i}"
                source_text = self.find_text_for_proposition(input_content, proposition)
                
                process_result["propositions"].append({
                    "id": proposition_id,
                    "text": proposition,
                    "sourceText": source_text
                })
                self.logger.debug(f"Added proposition {proposition_id}")
            
            process_result["status"] = "SUCCESS"
            process_result["count"] = len(propositions)
            
            return process_result
        else:
            self.logger.error(f"Failed to get response from Gemini for {doc_id}")
            return {
                "documentId": doc_id,
                "filename": os.path.basename(input_file_path),
                "processingDate": datetime.datetime.now().isoformat(),
                "status": "ERROR",
                "error": "Failed to get response from Gemini",
                "propositions": []
            }

    def process_directory(self, input_dir, output_file=None, ignore_files=None):
        """
        Process all markdown files in a directory and extract propositions.
        
        Args:
            input_dir (str): Path to the directory containing markdown files
            output_file (str, optional): Path to save the JSON output. If None, no file is saved.
            ignore_files (list, optional): List of filenames to ignore
            
        Returns:
            list: List of results for each processed file
        """
        if not ignore_files:
            ignore_files = ["README.md", "CHANGELOG.md"]
        
        # Get all markdown files in the directory
        markdown_files = glob.glob(os.path.join(input_dir, "*.md"))
        
        # Filter out ignored files
        markdown_files = [f for f in markdown_files if os.path.basename(f).lower() not in [ignore.lower() for ignore in ignore_files]]
        
        if not markdown_files:
            self.logger.warning("No markdown (.md) files found in the directory (or all are ignored).")
            return []
        
        # Initialize results list
        all_results = []
        
        # Add metadata
        metadata = {
            "documentId": "metadata",
            "generatedDate": datetime.datetime.now().isoformat(),
            "tool": "PropositionExtractionService",
            "model": self.model_name,
            "generationParams": {
                "maxOutputTokens": self.max_output_tokens,
                "temperature": self.temperature
            },
            "type": "metadata"
        }
        all_results.append(metadata)
        
        # Process each markdown file
        for input_path in markdown_files:
            # Process the file
            self.logger.info(f"Processing: {input_path}")
            result = self.process_file(input_path)
            all_results.append(result)
            
            # Save after each file is processed if output_file is provided
            if output_file:
                # Save the full results
                self.save_propositions_json(all_results, output_file)
        
        return all_results
    
    def save_propositions_json(self, results, output_filename):
        """
        Saves the extracted propositions to a JSON file.
        
        Args:
            results: List of document processing results
            output_filename: Name of the output JSON file
        """
        try:
            # Write JSON file
            self.logger.info(f"Saving results to {output_filename}")
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            
            # Count total propositions
            total_propositions = sum(
                len(doc.get('propositions', [])) 
                for doc in results 
                if doc.get('documentId') != 'metadata'
            )
            
            self.logger.info(f"Successfully saved {total_propositions} propositions across {len(results)-1} documents")
            return True
        
        except Exception as e:
            error_msg = f"Error saving JSON output: {str(e)}"
            self.logger.exception(error_msg)
            return False
    
    def pipeline_process(self, input_files, output_file=None):
        """
        Process a list of markdown files in a pipeline fashion.
        
        Args:
            input_files (list): List of paths to markdown files to process
            output_file (str, optional): Path to save the JSON output. If None, no file is saved.
            
        Returns:
            list: List of results for each processed file
        """
        # Initialize results list
        all_results = []
        
        # Add metadata
        metadata = {
            "documentId": "metadata",
            "generatedDate": datetime.datetime.now().isoformat(),
            "tool": "PropositionExtractionService",
            "model": self.model_name,
            "generationParams": {
                "maxOutputTokens": self.max_output_tokens,
                "temperature": self.temperature
            },
            "type": "metadata"
        }
        all_results.append(metadata)
        
        # Process each markdown file
        for input_path in input_files:
            if not input_path.lower().endswith('.md'):
                self.logger.info(f"Skipping non-markdown file: {input_path}")
                continue
                
            # Process the file
            self.logger.info(f"Processing: {input_path}")
            result = self.process_file(input_path)
            all_results.append(result)
            
            # Save after each file is processed if output_file is provided
            if output_file:
                # Save the full results
                self.save_propositions_json(all_results, output_file)
        
        return all_resultss