import os
import re
import google.generativeai as genai
from dotenv import load_dotenv
import sys

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
            print(f"Error: Input file not found at '{filepath}'", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
            return None

    def write_file(self, filepath, content):
        """Writes content to a file."""
        try:
            # Only create the directory if one is specified
            output_dir = os.path.dirname(filepath)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Successfully wrote cleaned markdown to '{filepath}'", file=sys.stderr)
            return True
        except Exception as e:
            print(f"Error writing file '{filepath}': {e}", file=sys.stderr)
            return False

    def read_prompt_template(self, prompt_path):
        """Reads the prompt template from a file."""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: Prompt template file not found at '{prompt_path}'", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error reading prompt template '{prompt_path}': {e}", file=sys.stderr)
            return None

    def create_prompt(self, markdown_content, prompt_template):
        """Creates the prompt for the Gemini API using a template."""
        # Replace the placeholder with the actual markdown content
        return prompt_template.replace("{markdown_content}", markdown_content)

    def fix_markdown_with_gemini(self, markdown_content, prompt_template):
        """Sends the markdown to Gemini for fixing and returns the cleaned version."""
        if not self.api_key:
            print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
            return None

        try:
            prompt = self.create_prompt(markdown_content, prompt_template)
            print("Sending request to Gemini API...", file=sys.stderr)

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
                        print(f"Warning: Gemini response was empty or blocked. Reason: {block_reason}", file=sys.stderr)
                        # If blocked, return original
                        return markdown_content

                    cleaned_markdown = response.text
                    print("Received response from Gemini.", file=sys.stderr)
                    return cleaned_markdown

                except Exception as e:
                    print(f"Error during Gemini API call (Attempt {attempt + 1}/{max_retries}): {e}", file=sys.stderr)
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        import time
                        time.sleep(2 ** attempt)
                    else:
                        print("Max retries reached. Failed to get response from Gemini.", file=sys.stderr)
                        raise  # Re-raise the last exception

        except Exception as e:
            print(f"An error occurred while interacting with the Gemini API: {e}", file=sys.stderr)
            return None

    def process_markdown_content(self, markdown_content, prompt_template):
        """Process markdown content and fix its formatting"""
        try:
            if not markdown_content:
                print("Input content is empty. Exiting.", file=sys.stderr)
                return None
                
            print(f"Attempting to fix formatting using Gemini (Model: gemini-2.5-flash-preview-04-17)...", file=sys.stderr)
            cleaned_markdown = self.fix_markdown_with_gemini(markdown_content, prompt_template)

            if not cleaned_markdown:
                print("Gemini did not return valid content.", file=sys.stderr)
                return None
                
            # Basic check if Gemini returned something substantially different
            if cleaned_markdown.strip() != markdown_content.strip():
                return cleaned_markdown
            else:
                print("Gemini returned content identical to the input (or only whitespace changes). Using original content.", file=sys.stderr)
                return markdown_content
                
        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
            return None


def main():
    # Set your Gemini API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Please set the GEMINI_API_KEY environment variable.", file=sys.stderr)
        return 1
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up Markdown formatting issues using the Gemini API.")
    parser.add_argument("-i", "--input", default="-", 
                      help="Input Markdown file path. Use '-' for stdin (default)")
    parser.add_argument("-o", "--output", default="output/cleaned.md", 
                      help="Output file path. Use '-' for stdout (default: output/cleaned.md)")
    parser.add_argument("--prompt", default="src/prompts/markdown_prompt.txt", 
                      help="Path to the prompt template file (default: src/prompts/markdown_prompt.txt)")
    
    args = parser.parse_args()
    
    # Create fixer with the API key
    fixer = MarkdownFixer(api_key)
    
    # Read the prompt template
    print(f"Reading prompt template from: {args.prompt}", file=sys.stderr)
    prompt_template = fixer.read_prompt_template(args.prompt)
    if not prompt_template:
        return 1
    
    # Read input
    if args.input == '-':
        print("Reading from stdin...", file=sys.stderr)
        markdown_content = sys.stdin.read()
    else:
        print(f"Reading from file: {args.input}", file=sys.stderr)
        markdown_content = fixer.read_file(args.input)
        
    if not markdown_content:
        print("Input is empty or could not be read. Exiting.", file=sys.stderr)
        return 1
    
    # Process the content
    cleaned_markdown = fixer.process_markdown_content(markdown_content, prompt_template)
    
    if not cleaned_markdown:
        print("Processing failed. No output generated.", file=sys.stderr)
        return 1
    
    # Output
    if args.output == '-':
        sys.stdout.write(cleaned_markdown)
    else:
        success = fixer.write_file(args.output, cleaned_markdown)
        if not success:
            return 1
    
    print("Processing complete.", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())