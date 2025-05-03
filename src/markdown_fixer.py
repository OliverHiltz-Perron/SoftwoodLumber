import os
import re
import sys
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()

class MarkdownFixer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()
    
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
        """Creates the prompt for the LLM using a template."""
        return prompt_template.replace("{markdown_content}", markdown_content)

    def fix_markdown_with_openai(self, markdown_content, prompt_template):
        """Sends the markdown to OpenAI for fixing and returns the cleaned version."""
        if not self.api_key:
            print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
            return None
        try:
            prompt = self.create_prompt(markdown_content, prompt_template)
            print("Sending request to OpenAI gpt-4.1-mini...", file=sys.stderr)
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=32768,
            )
            cleaned_markdown = response.choices[0].message.content
            print("Received response from OpenAI.", file=sys.stderr)
            return cleaned_markdown
        except Exception as e:
            print(f"An error occurred while interacting with OpenAI: {e}", file=sys.stderr)
            return None

    def process_markdown_content(self, markdown_content, prompt_template):
        """Process markdown content and fix its formatting"""
        try:
            if not markdown_content:
                print("Input content is empty. Exiting.", file=sys.stderr)
                return None
            print(f"Attempting to fix formatting using OpenAI (Model: gpt-4.1-mini)...", file=sys.stderr)
            cleaned_markdown = self.fix_markdown_with_openai(markdown_content, prompt_template)
            if not cleaned_markdown:
                print("OpenAI did not return valid content.", file=sys.stderr)
                return None
            if cleaned_markdown.strip() != markdown_content.strip():
                return cleaned_markdown
            else:
                print("OpenAI returned content identical to the input (or only whitespace changes). Using original content.", file=sys.stderr)
                return markdown_content
        except Exception as e:
            print(f"An error occurred: {e}", file=sys.stderr)
            return None


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Please set the OPENAI_API_KEY environment variable.", file=sys.stderr)
        return 1
    import argparse
    parser = argparse.ArgumentParser(description="Clean up Markdown formatting issues using OpenAI gpt-4.1-mini.")
    parser.add_argument("-i", "--input", default="-", 
                      help="Input Markdown file path. Use '-' for stdin (default)")
    parser.add_argument("-o", "--output", default="output/cleaned.md", 
                      help="Output file path. Use '-' for stdout (default: output/cleaned.md)")
    parser.add_argument("--prompt", default="src/prompts/markdown_prompt.txt", 
                      help="Path to the prompt template file (default: src/prompts/markdown_prompt.txt)")
    args = parser.parse_args()
    fixer = MarkdownFixer(api_key)
    print(f"Reading prompt template from: {args.prompt}", file=sys.stderr)
    prompt_template = fixer.read_prompt_template(args.prompt)
    if not prompt_template:
        return 1
    if args.input == '-':
        print("Reading from stdin...", file=sys.stderr)
        markdown_content = sys.stdin.read()
    else:
        print(f"Reading from file: {args.input}", file=sys.stderr)
        markdown_content = fixer.read_file(args.input)
    if not markdown_content:
        print("Input is empty or could not be read. Exiting.", file=sys.stderr)
        return 1
    cleaned_markdown = fixer.process_markdown_content(markdown_content, prompt_template)
    if not cleaned_markdown:
        print("Processing failed. No output generated.", file=sys.stderr)
        return 1
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