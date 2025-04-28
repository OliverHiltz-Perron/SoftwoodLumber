import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class MarkdownFixer:
    def __init__(self, api_key):
        self.api_key = api_key
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

    def create_prompt(self, markdown_content, prompt_template):
        """Creates the prompt for the Gemini API using a template."""
        # Replace the placeholder with the actual markdown content
        return prompt_template.replace("{markdown_content}", markdown_content)

    def fix_markdown_with_gemini(self, markdown_content, prompt_template):
        """Sends the markdown to Gemini for fixing and returns the cleaned version."""
        if not self.api_key:
            print("Error: GEMINI_API_KEY environment variable not set.")
            return None

        try:
            prompt = self.create_prompt(markdown_content, prompt_template)
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

    def process_markdown_file(self, input_file, output_file, prompt_template):
        """Process a single markdown file and fix its formatting"""
        try:
            # Read the Markdown file
            markdown_content = self.read_file(input_file)
            if not markdown_content:
                print("Input file is empty or could not be read. Exiting.")
                return False
                
            print(f"Attempting to fix formatting using Gemini (Model: gemini-2.5-flash-preview-04-17)...")
            cleaned_markdown = self.fix_markdown_with_gemini(markdown_content, prompt_template)

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


def main():
    # Set your Gemini API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Please set the GEMINI_API_KEY environment variable.")
        return
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up Markdown formatting issues using the Gemini API.")
    parser.add_argument("--output-dir", default="fixed_markdown", 
                      help="Directory to save the cleaned Markdown files (default: fixed_markdown)")
    parser.add_argument("--prompt", default="prompts/markdown_prompt.txt", 
                      help="Path to the prompt template file (default: prompts/markdown_prompt.txt)")
    
    args = parser.parse_args()
    
    # Create fixer with the API key
    fixer = MarkdownFixer(api_key)
    
    # Read the prompt template
    print(f"Reading prompt template from: {args.prompt}")
    prompt_template = fixer.read_prompt_template(args.prompt)
    if not prompt_template:
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Get all markdown files in the parent directory
    parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    markdown_files = [f for f in os.listdir(parent_dir) if f.endswith('.md')]
    
    if not markdown_files:
        print("No markdown (.md) files found in the parent directory.")
        return
    
    # Process each markdown file
    success_count = 0
    failure_count = 0
    
    for markdown_file in markdown_files:
        # Create full paths
        input_path = os.path.join(parent_dir, markdown_file)
        output_path = os.path.join(args.output_dir, markdown_file)
        
        # Process the file
        print(f"\n{'='*50}\nProcessing: {markdown_file}\n{'='*50}")
        success = fixer.process_markdown_file(input_path, output_path, prompt_template)
        
        if success:
            success_count += 1
        else:
            failure_count += 1
    
    print(f"\nProcessing complete! {success_count} files processed successfully, {failure_count} failed.")
    print(f"Check the '{args.output_dir}' directory for the cleaned markdown files.")


if __name__ == "__main__":
    main()