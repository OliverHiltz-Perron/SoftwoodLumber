# backend/markdown_fixer_service.py

import os
import re
import glob
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class MarkdownFixerService:
    """Service for fixing and improving markdown formatting using Gemini API."""
    
    def __init__(self, api_key=None, prompt_template_path=None):
        """
        Initialize the MarkdownFixer service.
        
        Args:
            api_key (str, optional): Gemini API key. If None, will try to load from env vars.
            prompt_template_path (str, optional): Path to the prompt template file. If None, 
                                                 will use the default template.
        """
        # Load API key from environment if not provided
        if not api_key:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables or .env file")
        
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        
        # Configure safety settings
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        
        # Configure generation settings
        self.generation_config = {
            "temperature": 0.3,
            "top_p": 1.0,
            "top_k": 1,
            "max_output_tokens": 65536,
        }
        
        # Load the prompt template
        if prompt_template_path:
            self.prompt_template = self.read_prompt_template(prompt_template_path)
        else:
            # Use default prompt if no path provided
            self.prompt_template = self._get_default_prompt_template()
    
    def read_file(self, filepath):
        """Reads content from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: Input file not found at '{filepath}'")
            return None
        except Exception as e:
            print(f"Error reading file '{filepath}': {e}")
            return None

    def write_file(self, filepath, content):
        """Writes content to a file."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Successfully wrote cleaned markdown to '{filepath}'")
            return True
        except Exception as e:
            print(f"Error writing file '{filepath}': {e}")
            return False

    def read_prompt_template(self, prompt_path):
        """Reads the prompt template from a file."""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: Prompt template file not found at '{prompt_path}'")
            return None
        except Exception as e:
            print(f"Error reading prompt template '{prompt_path}': {e}")
            return None

    def _get_default_prompt_template(self):
        """Returns a default prompt template if none is provided."""
        return """You are a Markdown formatting expert. Your task is to fix and improve the following 
        Markdown content without changing the meaning. Ensure proper heading hierarchy, fix list formatting, 
        improve table formatting, and make the content more readable.

        Here is the Markdown content to fix:

        {markdown_content}

        Please provide the cleaned and improved Markdown content only, with no explanations or comments.
        """

    def create_prompt(self, markdown_content):
        """Creates the prompt for the Gemini API using the template."""
        # Replace the placeholder with the actual markdown content
        return self.prompt_template.replace("{markdown_content}", markdown_content)

    def fix_markdown_with_gemini(self, markdown_content):
        """Sends the markdown to Gemini for fixing and returns the cleaned version."""
        try:
            prompt = self.create_prompt(markdown_content)
            print("Sending request to Gemini API...")

            # Add retries for potential transient API issues
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(prompt)
                    # Check for safety blocks or empty response
                    if not response.parts:
                        # Try to get block reason if available
                        block_reason = "Unknown"
                        if hasattr(response, 'prompt_feedback') and hasattr(response.prompt_feedback, 'block_reason'):
                            block_reason = response.prompt_feedback.block_reason
                        print(f"Warning: Gemini response was empty or blocked. Reason: {block_reason}")
                        # If blocked, return original
                        return markdown_content

                    cleaned_markdown = response.text
                    print("Received response from Gemini.")
                    return cleaned_markdown

                except Exception as e:
                    print(f"Error during Gemini API call (Attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        import time
                        time.sleep(2 ** attempt)
                    else:
                        print("Max retries reached. Failed to get response from Gemini.")
                        raise  # Re-raise the last exception

        except Exception as e:
            print(f"An error occurred while interacting with the Gemini API: {e}")
            return None

    def process_markdown_file(self, input_file, output_file):
        """Process a single markdown file and fix its formatting"""
        try:
            # Read the Markdown file
            markdown_content = self.read_file(input_file)
            if not markdown_content:
                print("Input file is empty or could not be read.")
                return False
                
            print(f"Attempting to fix formatting using Gemini (Model: gemini-2.5-flash-preview-04-17)...")
            cleaned_markdown = self.fix_markdown_with_gemini(markdown_content)

            if not cleaned_markdown:
                print("Gemini did not return valid content. No output file written.")
                return False
                
            # Basic check if Gemini returned something substantially different
            if cleaned_markdown.strip() != markdown_content.strip():
                return self.write_file(output_file, cleaned_markdown)
            else:
                print("Gemini returned content identical to the input (or only whitespace changes). Writing original content.")
                return self.write_file(output_file, markdown_content)
                
        except Exception as e:
            print(f"An error occurred: {e}")
            return False
    
    def process_directory(self, input_dir, output_dir, ignore_files=None):
        """
        Process all markdown files in a directory and fix their formatting.
        
        Args:
            input_dir (str): Path to the directory containing markdown files
            output_dir (str): Directory to save the fixed markdown files
            ignore_files (list, optional): List of filenames to ignore
            
        Returns:
            list: Paths to the fixed markdown files
        """
        if not ignore_files:
            ignore_files = ["README.md", "CHANGELOG.md"]
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get all markdown files in the directory
        markdown_files = glob.glob(os.path.join(input_dir, "*.md"))
        
        # Filter out ignored files
        markdown_files = [f for f in markdown_files if os.path.basename(f) not in ignore_files]
        
        if not markdown_files:
            print("No markdown (.md) files found in the directory (or all are ignored).")
            return []
        
        # Process each markdown file
        processed_files = []
        
        for input_path in markdown_files:
            # Create output path
            filename = os.path.basename(input_path)
            output_path = os.path.join(output_dir, filename)
            
            # Process the file
            print(f"\nProcessing: {filename}")
            success = self.process_markdown_file(input_path, output_path)
            
            if success:
                processed_files.append(output_path)
        
        return processed_files
    
    def pipeline_process(self, input_files, output_dir):
        """
        Process a list of markdown files in a pipeline fashion.
        Useful for integration with other services like LlamaParse.
        
        Args:
            input_files (list): List of paths to markdown files to process
            output_dir (str): Directory to save the fixed markdown files
            
        Returns:
            list: Paths to the fixed markdown files
        """
        processed_files = []
        
        for input_path in input_files:
            if not input_path.lower().endswith('.md'):
                print(f"Skipping non-markdown file: {input_path}")
                continue
                
            # Create output path
            filename = os.path.basename(input_path)
            output_path = os.path.join(output_dir, filename)
            
            # Process the file
            print(f"\nProcessing: {filename}")
            success = self.process_markdown_file(input_path, output_path)
            
            if success:
                processed_files.append(output_path)
        
        return processed_files