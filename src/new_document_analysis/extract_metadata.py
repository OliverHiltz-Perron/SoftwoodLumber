import os
import json
import re
import openai
from dotenv import load_dotenv
import argparse
import sys

# Load environment variables from .env file
load_dotenv()

class MetadataExtractor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def extract_filename(self, markdown_file, markdown_content):
        """Extract a filename based on either first numbers or first 10 characters"""
        # Remove file extension from the original filename
        basename = os.path.splitext(os.path.basename(markdown_file))[0]
        
        # Look for numbers at the beginning of the content
        number_match = re.search(r'^\s*(\d+)', basename)
        if number_match:
            # Use the first numbers as the filename
            return number_match.group(1)
        else:
            # Use the first 10 characters (or less if content is shorter)
            # Clean the text by removing whitespace and special characters
            cleaned_text = re.sub(r'[^\w\s]', '', markdown_content.strip())
            return cleaned_text[:10] if len(cleaned_text) >= 10 else cleaned_text

    def create_template_json(self):
        """Create a template JSON when all else fails"""
        print("Creating template JSON as fallback")
        return {
            "Article Title": "Not specified",
            "File_ID": "Not specified",
            "File_name": "Unknown",
            "Author": "Not specified",
            "Author_organization": "Not specified",
            "Publication year": "Not specified",
            "Keywords": [],
            "TLDR_summary": "Could not extract summary",
            "Focus_area": [],
            "Participating company/organization names": [],
            "Hyperlinks_Internal": ["Not specified"],
            "Hyperlinks_External": ["Not specified"],
            "Hyperlink_Other": ["Not specified"]
        }
        
    def fix_json(self, json_string):
        """Attempt to fix common JSON parsing errors"""
        # First try direct parsing
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            # Attempt to fix common JSON errors
            error_message = str(e)
            print(f"JSON decode error: {error_message}")
            
            # Check if we have actual JSON content
            json_match = re.search(r'(\{.*\})', json_string, re.DOTALL)
            if json_match:
                # Extract just the JSON part
                json_string = json_match.group(1)
                print("Extracted JSON-like content from output")
            
            # Try to fix unquoted keys
            if "Expecting property name enclosed in double quotes" in error_message:
                json_string = re.sub(r"([{,]\s*)(\w+)\s*:", r'\1"\2":', json_string)
                print("Fixed unquoted keys")
            
            # Fix missing quotes around string values
            json_string = re.sub(r":\s*(\w+)\s*([,}])", r': "\1"\2', json_string)
            print("Fixed unquoted values")
            
            # Remove control characters and other problematic chars
            if "Invalid control character at" in error_message or "Unexpected character" in error_message:
                json_string = ''.join(ch for ch in json_string if ch.isalnum() or ch in '.,;:?!-\'"()[]{} \n')
                print("Removed invalid characters")
            
            # Try parsing again
            try:
                fixed_json = json.loads(json_string)
                print("Successfully fixed JSON!")
                return fixed_json
            except json.JSONDecodeError:
                print("Could not fix JSON. Using template instead.")
                return self.create_template_json()

    def process_markdown_file(self, markdown_file, output_file, prompt):
        """Process a single markdown file and convert it to JSON"""
        try:
            # Read the Markdown file
            with open(markdown_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
                
            # Extract filename according to the specified pattern
            file_name = self.extract_filename(markdown_file, markdown_content)
            print(f"Extracted file name: {file_name}")
                
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Enhance the prompt for better JSON output
            enhanced_prompt = self._prepare_enhanced_prompt(prompt)

            # Generate and process content using OpenAI API
            data = self._generate_and_process_content(enhanced_prompt, markdown_content)
            
            # Add the file name that we extracted
            new_data = {
                "File ID": file_name,
                "File name": os.path.splitext(os.path.basename(markdown_file))[0]
            }

            # Merge the existing data into the new object
            new_data.update(data)

            # Replace the original data with the new data
            data = new_data
            # Save the JSON data to a file
            with open(output_file, 'w', encoding='utf-8') as outfile:
                json.dump(data, outfile, indent=4)

            print(f"Successfully converted {markdown_file} to {output_file}")
            
        except FileNotFoundError:
            print(f"Error: File not found: {markdown_file}")
        except Exception as e:
            print(f"An error occurred: {e}")
            
            # Create a minimal JSON with just the filename
            data = self.create_template_json()
            data["File name"] = os.path.splitext(os.path.basename(markdown_file))[0]
            
            with open(output_file, 'w', encoding='utf-8') as outfile:
                json.dump(data, outfile, indent=4)
            print(f"Created template JSON for {markdown_file} due to error")

    def _prepare_enhanced_prompt(self, prompt):
        """Prepare an enhanced prompt for better JSON generation"""
        # Remove the file name field instruction from the prompt
        prompt_without_filename = re.sub(r'1\. File name:.*?\n2\.', '2.', prompt, flags=re.DOTALL)
        # Add explicit JSON formatting instructions
        return prompt_without_filename + "\n\nIMPORTANT: Your response must be valid JSON and nothing else. Do not include any text before or after the JSON object. Do not include code block backticks or any other formatting. Your response must start with { and end with } and be a valid parseable JSON object."

    def _generate_and_process_content(self, prompt, markdown_content):
        """Generate and process content using the OpenAI API"""
        try:
            print("Sending request to OpenAI gpt-4.1-mini...", flush=True)
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt + "\n\n" + markdown_content}],
                temperature=0.1,
                max_tokens=32768,
            )
            openai_output = response.choices[0].message.content
            
            # Try to find a JSON object in the response
            json_match = re.search(r'(\{.*\})', openai_output, re.DOTALL)
            if json_match:
                openai_output = json_match.group(1)
                print("Extracted JSON object from response")

            # Try to parse the JSON
            try:
                data = json.loads(openai_output)
                print("Successfully parsed JSON directly")
                return data
            except json.JSONDecodeError:
                # If parsing fails, try to fix the JSON
                print("Warning: OpenAI output is not valid JSON. Attempting to fix...")
                return self._retry_json_parsing(openai_output, prompt, markdown_content)
                
        except Exception as openai_error:
            print(f"OpenAI API error: {openai_error}")
            return self.create_template_json()

    def _retry_json_parsing(self, openai_output, prompt, markdown_content):
        """Retry JSON parsing with fixes or a second attempt"""
        # Try to fix the JSON
        data = self.fix_json(openai_output)
        if data is not None and not isinstance(data, dict):
            data = None
            
        # If fixing failed, try again with a stronger prompt
        if data is None:
            print("Trying again with stronger formatting instructions...")
            try:
                retry_prompt = prompt + "\nYOUR RESPONSE MUST BE VALID JSON ONLY. NO OTHER TEXT.\n\n"
                response = self.client.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[{"role": "user", "content": retry_prompt + markdown_content}],
                    temperature=0.1,
                    max_tokens=32768,
                )
                retry_output = response.choices[0].message.content
                
                # Try to parse directly
                try:
                    data = json.loads(retry_output)
                    print("Successfully parsed JSON on retry")
                except:
                    # Try to extract and fix
                    json_match = re.search(r'(\{.*\})', retry_output, re.DOTALL)
                    if json_match:
                        extracted = json_match.group(1)
                        data = self.fix_json(extracted)
                    else:
                        raise Exception("No JSON object found in retry response")
            except Exception as retry_error:
                print(f"Retry attempt failed: {retry_error}")
                print("Using template JSON as fallback")
                data = self.create_template_json()
                
        return data if data is not None else self.create_template_json()


def main():
    # Set your OpenAI API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Please set the OPENAI_API_KEY environment variable.")
        return
    parser = argparse.ArgumentParser(description="Extract metadata from cleaned markdown.")
    parser.add_argument('-i', '--input', default=None, help='Input cleaned markdown file (default: output/{basename}_cleaned.md)')
    parser.add_argument('-o', '--output', default=None, help='Output JSON file (default: output/{basename}_metadata.json)')
    args = parser.parse_args()
    # Determine base name
    if args.input is None:
        import glob
        md_files = glob.glob('output/*_cleaned.md')
        if md_files:
            input_md = md_files[0]
        else:
            input_md = 'output/output_cleaned.md'
    else:
        input_md = args.input
    base_name = os.path.splitext(os.path.basename(input_md))[0]
    base_name = base_name.replace('_markdown', '').replace('_cleaned', '')
    if args.output is None:
        output_json = f'output/{base_name}_metadata.json'
    else:
        output_json = args.output
    print(f"BASENAME:{base_name}", file=sys.stderr)
    # Define the prompt for OpenAI
    with open("src/prompts/markdown_to_json.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    # Create processor with the API key
    extractor = MetadataExtractor(api_key)
    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)
    # Process the markdown file
    print(f"\n{'='*50}\nProcessing: {input_md}\n{'='*50}")
    extractor.process_markdown_file(input_md, output_json, prompt)
    print(f"\nProcessing complete! Check '{output_json}' for the JSON file.")


if __name__ == "__main__":
    main()