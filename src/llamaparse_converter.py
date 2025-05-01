# Force Python to ignore warnings by setting the PYTHONWARNINGS environment variable
import os
os.environ["PYTHONWARNINGS"] = "ignore"

# Now import everything else
import argparse
import zipfile
import tempfile
import shutil
import glob
import nest_asyncio
import warnings
import sys

# Set a placeholder OpenAI API key to prevent prompts for the key
# This is needed because some LlamaIndex dependencies might try to use OpenAI
os.environ["OPENAI_API_KEY"] = "placeholder-key-not-used"

from dotenv import load_dotenv
from llama_cloud_services import LlamaParse
from llama_index.core import SimpleDirectoryReader

# Apply nest_asyncio patch early
nest_asyncio.apply()

# Additional warning suppression for any warnings that might come later
warnings.filterwarnings("ignore")

def process_and_output(document, output_path):
    """
    Process a single document and output its content to the specified path or stdout.
    """
    if not document:
        print("No document received by process_and_output.", file=sys.stderr)
        return False

    try:
        # Get the content
        content = document.get_content()
        
        # Output to file or stdout
        if output_path == '-':
            sys.stdout.write(content)
        else:
            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                
            # Write the file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Successfully saved content to '{output_path}'.", file=sys.stderr)
        
        return True
        
    except Exception as e:
        print(f"Error processing or writing document: {e}", file=sys.stderr)
        return False

def main():
    """
    Main function to handle argument parsing, LlamaParse initialization, 
    and document processing based on input type.
    """
    
    # --- Argument Parsing ---
    cli_parser = argparse.ArgumentParser(description="Convert a document to Markdown using LlamaParse.")
    cli_parser.add_argument("-i", "--input", default="-", 
                         help="Path to the input file. Use '-' for stdin (default).")
    cli_parser.add_argument("-o", "--output", default="-", 
                         help="Path to output file. Use '-' for stdout (default).")
    args = cli_parser.parse_args()

    input_path = args.input
    output_path = args.output

    print(f"Script started. Input: {input_path}, Output: {output_path}", file=sys.stderr)

    # --- API Key Loading ---
    load_dotenv()

    api_key = None # Initialize to None first
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print("Error: LLAMA_CLOUD_API_KEY not found in environment variables or .env file.", file=sys.stderr)
        print("Please create a .env file with LLAMA_CLOUD_API_KEY=your_key or set the environment variable.", file=sys.stderr)
        return 1 # Exit if no API key
    else:
        # Mask the API key for security but show enough to verify it's correct
        masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "****"
        print(f"Using API key starting with {api_key[0:]}", file=sys.stderr)


    # --- LlamaParse Initialization ---
    print("Initializing LlamaParse...", file=sys.stderr)
    try:
        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",  # Explicitly set to markdown
            verbose=True             # Enable verbose output for debugging
        )
        # Define the file extractor for SimpleDirectoryReader
        file_extractor = {
            ".pdf": parser,
            ".docx": parser,
            ".doc": parser,
            ".pptx": parser,
            ".ppt": parser,
            ".html": parser
        }
        print("LlamaParse initialized successfully.", file=sys.stderr)
    except Exception as e:
        print(f"Error initializing LlamaParse: {e}", file=sys.stderr)
        return 1 # Exit if initialization fails

    # --- Input Handling ---
    documents = []
    temp_dir = None # To keep track of temporary directory for stdin or zip files
    temp_file = None # To keep track of temporary file for stdin

    try:
        # Handle stdin input
        if input_path == '-':
            print("Reading from stdin...", file=sys.stderr)
            temp_dir = tempfile.mkdtemp()
            temp_file = os.path.join(temp_dir, "input.pdf")
            
            # Read binary data from stdin
            with open(temp_file, 'wb') as f:
                f.write(sys.stdin.buffer.read())
                
            input_path = temp_file
            print(f"Saved stdin input to temporary file: {temp_file}", file=sys.stderr)

        # Process single file
        if os.path.isfile(input_path):
            # Get the file extension
            _, file_extension = os.path.splitext(input_path)
            file_extension = file_extension.lower() # Ensure case-insensitivity

            # Check if the extension is in our extractor OR if it's a zip file
            if file_extension in file_extractor:
                print(f"Processing file ({file_extension}): {input_path}", file=sys.stderr)
                reader = SimpleDirectoryReader(input_files=[input_path], file_extractor=file_extractor)
                documents = reader.load_data()
                
                # Log the number of document chunks
                print(f"LlamaParse extracted {len(documents)} document chunks.", file=sys.stderr)
            elif file_extension == '.zip':
                print(f"Processing ZIP archive: {input_path}", file=sys.stderr)
                if not temp_dir:  # Create temp dir if not already created for stdin
                    temp_dir = tempfile.mkdtemp()
                print(f"Extracting ZIP contents to temporary directory: {temp_dir}", file=sys.stderr)
                with zipfile.ZipFile(input_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Get the first supported file from the ZIP
                supported_extensions = tuple(file_extractor.keys())
                extracted_files = []
                for ext in supported_extensions:
                    # Use '*' before extension to match filenames like 'file.pdf'
                    extracted_files.extend(glob.glob(os.path.join(temp_dir, '**', f'*{ext}'), recursive=True))

                if not extracted_files:
                    print(f"Error: No supported files ({', '.join(supported_extensions)}) found in the ZIP archive.", file=sys.stderr)
                    return 1
                else:
                    # Take just the first file
                    first_file = extracted_files[0]
                    print(f"Processing first supported file from ZIP: {first_file}", file=sys.stderr)
                    reader = SimpleDirectoryReader(input_files=[first_file], file_extractor=file_extractor)
                    documents = reader.load_data()
                    print(f"LlamaParse extracted {len(documents)} document chunks from ZIP file.", file=sys.stderr)
            else:
                print(f"Error: File '{input_path}' has an unsupported extension ('{file_extension}').", file=sys.stderr)
                print(f"Supported extensions are: {', '.join(file_extractor.keys())} and .zip", file=sys.stderr)
                return 1 # Exit for unsupported file types
        else:
            print(f"Error: Input path '{input_path}' is not a valid file.", file=sys.stderr)
            return 1 # Exit for invalid path

        # --- Process and Output ---
        if documents:
            # Combine all document chunks into a single markdown document
            all_content = ""
            
            # Iterate through all document chunks and combine
            for i, doc in enumerate(documents):
                try:
                    content = doc.get_content()
                    if content:
                        # Add a separator between chunks if not the first chunk
                        if all_content:
                            all_content += "\n\n---\n\n"
                        all_content += content
                        print(f"Added content from chunk {i+1}/{len(documents)}", file=sys.stderr)
                except Exception as e:
                    print(f"Error processing chunk {i+1}/{len(documents)}: {e}", file=sys.stderr)
            
            # Output the combined content
            if all_content:
                if output_path == '-':
                    sys.stdout.write(all_content)
                else:
                    # Ensure directory exists
                    output_dir = os.path.dirname(output_path)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                        
                    # Write the file
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(all_content)
                    print(f"Successfully saved combined content to '{output_path}'.", file=sys.stderr)
            else:
                print("Error: No content extracted from documents.", file=sys.stderr)
                return 1
        else:
            print("No documents were loaded or found to process.", file=sys.stderr)
            return 1

    except FileNotFoundError:
        print(f"Error: Input path '{input_path}' not found.", file=sys.stderr)
        return 1
    except zipfile.BadZipFile:
        print(f"Error: Input file '{input_path}' is not a valid ZIP file.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}", file=sys.stderr)
        return 1
    finally:
        # --- Cleanup ---
        if temp_dir and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}", file=sys.stderr)
            shutil.rmtree(temp_dir)

    print("Script finished successfully.", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())