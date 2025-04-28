import google.generativeai as genai
import os
import argparse
import sys
import time
from dotenv import load_dotenv

# --- Configuration ---

# Best Practice: Set your API key as an environment variable
# Example (Linux/macOS): export GOOGLE_API_KEY="YOUR_API_KEY"
# Example (Windows): set GOOGLE_API_KEY=YOUR_API_KEY
# Or uncomment and set it here (less secure):
API_KEY = os.environ.get("GEMINI_API_KEY")


# Configure the Gemini model you want to use
MODEL_NAME = "gemini-2.5-flash-preview-04-17" # Or "gemini-pro", "gemini-1.5-pro", etc.

# Configure safety settings (adjust as needed)
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# Configure generation settings (optional)
GENERATION_CONFIG = {
    "temperature": 0.3, # Lower temperature for more deterministic formatting
    "top_p": 1.0,
    "top_k": 1,
    "max_output_tokens": 65536, # Adjust based on model and expected output size
}


# --- Helper Functions ---

def read_file(filepath):
    """Reads content from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at '{filepath}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}")
        sys.exit(1)

def write_file(filepath, content):
    """Writes content to a file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully wrote cleaned markdown to '{filepath}'")
    except Exception as e:
        print(f"Error writing file '{filepath}': {e}")
        sys.exit(1)

def read_prompt_template(prompt_path):
    """Reads the prompt template from a file."""
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt template file not found at '{prompt_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading prompt template '{prompt_path}': {e}")
        sys.exit(1)

def create_prompt(markdown_content, prompt_template):
    """Creates the prompt for the Gemini API using a template."""
    # Replace the placeholder with the actual markdown content
    return prompt_template.replace("{markdown_content}", markdown_content)


def fix_markdown_with_gemini(markdown_content):
    """Sends the markdown to Gemini for fixing and returns the cleaned version."""
    if not API_KEY:
        print("Error: GOOGLE_API_KEY environment variable not set.")
        sys.exit(1)

    try:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            safety_settings=SAFETY_SETTINGS,
            generation_config=GENERATION_CONFIG
        )

        prompt = create_prompt(markdown_content, prompts_template)
        print("Sending request to Gemini API...")

        # Add retries for potential transient API issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                # Check for safety blocks or empty response
                if not response.parts:
                    # Try to get block reason if available
                    block_reason = "Unknown"
                    if hasattr(response, 'prompt_feedback') and hasattr(response.prompt_feedback, 'block_reason'):
                         block_reason = response.prompt_feedback.block_reason
                    print(f"Warning: Gemini response was empty or blocked. Reason: {block_reason}")
                    # If blocked, maybe try slightly different prompt or safety settings? For now, return original.
                    # Consider raising an error or returning None depending on desired behavior
                    return markdown_content # Or raise Exception("Gemini response blocked")

                cleaned_markdown = response.text
                print("Received response from Gemini.")
                return cleaned_markdown

            except Exception as e:
                print(f"Error during Gemini API call (Attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt) # Exponential backoff
                else:
                    print("Max retries reached. Failed to get response from Gemini.")
                    raise # Re-raise the last exception

    except Exception as e:
        print(f"An error occurred while interacting with the Gemini API: {e}")
        # Depending on the error, you might want to return the original content
        # or signal failure more explicitly.
        # For now, we'll exit as it likely indicates a setup or API issue.
        sys.exit(1)


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Clean up Markdown formatting issues using the Gemini API.")
    parser.add_argument("input_file", help="Path to the input Markdown file.")
    parser.add_argument("output_file", help="Path to save the cleaned Markdown file.")
    parser.add_argument("--prompt", default="prompts/markdown_prompt.txt", 
                        help="Path to the prompt template file (default: prompts/markdown_prompt.txt)")
    # Optional: Add chunking arguments later if needed for large files

    args = parser.parse_args()

    print(f"Reading markdown from: {args.input_file}")
    original_markdown = read_file(args.input_file)

    if not original_markdown:
        print("Input file is empty. Exiting.")
        sys.exit(0)
        
    # Read the prompt template
    print(f"Reading prompt template from: {args.prompt}")
    prompt_template = read_prompt_template(args.prompt)

    print(f"Attempting to fix formatting using Gemini (Model: {MODEL_NAME})...")
    cleaned_markdown = fix_markdown_with_gemini(original_markdown, prompt_template)

    # Basic check if Gemini returned something substantially different
    if cleaned_markdown and cleaned_markdown.strip() != original_markdown.strip():
         write_file(args.output_file, cleaned_markdown)
    elif cleaned_markdown:
         print("Gemini returned content identical to the input (or only whitespace changes). Writing original content.")
         write_file(args.output_file, original_markdown) # Or write cleaned_markdown, should be same
    else:
         print("Gemini did not return valid content. No output file written.")


if __name__ == "__main__":
    main()