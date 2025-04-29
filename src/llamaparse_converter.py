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

def process_and_save(documents, output_dir):
    """
    Processes loaded documents, groups content by original file,
    concatenates, and saves the full markdown content to the output directory.
    """
    if not documents:
        print("No documents received by process_and_save.")
        return

    print(f"Received {len(documents)} document objects/chunks to process.")
    
    # Dictionary to hold content grouped by target output file path
    # Key: output_filepath (str), Value: list of content chunks (str)
    grouped_content = {}

    # --- Step 1: Group content by target output file ---
    print("Grouping content chunks by target output file...")
    for i, doc in enumerate(documents):
        try:
            # Extract original filename from metadata
            if 'file_path' not in doc.metadata:
                print(f"Warning - Skipping chunk {i+1}/{len(documents)} (ID: {doc.id_}) - missing 'file_path' metadata.")
                continue

            original_full_path = doc.metadata['file_path']
            original_basename = os.path.basename(original_full_path)

            # Construct the target output filename
            base_name_no_ext = os.path.splitext(original_basename)[0]
            output_filename = f"{base_name_no_ext}.md"
            output_filepath = os.path.join(output_dir, output_filename)

            # Get the content chunk
            content_chunk = doc.get_content()

            # Add the chunk to the list for the corresponding output file
            if output_filepath not in grouped_content:
                grouped_content[output_filepath] = []
                print(f"Initializing group for output file: '{output_filepath}' (from original: '{original_basename}')")
            
            grouped_content[output_filepath].append(content_chunk)
            # Optional: Log every chunk addition (can be very verbose)
            # print(f"LOG: Added chunk {i+1} from '{original_basename}' to group '{output_filepath}'.")

        except KeyError:
             print(f"Warning - Skipping chunk {i+1}/{len(documents)} (ID: {doc.id_}) due to missing metadata key (expected 'file_path').")
        except Exception as e:
            original_file_info = doc.metadata.get('file_path', doc.id_)
            print(f"Error processing chunk {i+1}/{len(documents)} from '{original_file_info}': {e}")

    # --- Step 2: Concatenate and Write grouped content ---
    print(f"Finished grouping. Found content for {len(grouped_content)} unique output files.")
    saved_count = 0
    for output_filepath, content_chunks in grouped_content.items():
        try:
            print(f"Concatenating {len(content_chunks)} chunks for '{output_filepath}'...")
            full_markdown_content = "\n\n".join(content_chunks) # Join chunks with double newline for separation

            print(f"Writing concatenated content to '{output_filepath}'...")
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(full_markdown_content)
            saved_count += 1
            print(f"Successfully saved '{output_filepath}'.")

        except IOError as e:
            print(f"Error writing file '{output_filepath}': {e}")
        except Exception as e:
            print(f"Error concatenating or writing file '{output_filepath}': {e}")

    print(f"Finished processing. Saved {saved_count} complete markdown files to '{output_dir}'.")

def main():
    """
    Main function to handle argument parsing, LlamaParse initialization, 
    and document processing based on input type.
    """
    # --- Argument Parsing ---
    cli_parser = argparse.ArgumentParser(description="Convert documents to Markdown using LlamaParse.")
    cli_parser.add_argument("-i", "--input", required=True, help="Path to the input PDF file, directory containing PDFs, or a ZIP archive of PDFs.")
    cli_parser.add_argument("-o", "--output", required=True, help="Path to the directory where Markdown files will be saved.")
    args = cli_parser.parse_args()

    print(f"Script started. Input: {args.input}, Output: {args.output}")

    # --- API Key Loading ---

    load_dotenv()


    api_key = None # Initialize to None first
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print("Error: LLAMA_CLOUD_API_KEY not found in environment variables or .env file.")
        print("Please create a .env file with LLAMA_CLOUD_API_KEY=your_key or set the environment variable.")
        return # Exit if no API key

    # --- LlamaParse Initialization ---
    print("Initializing LlamaParse...")
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
        print("LlamaParse initialized successfully.")
    except Exception as e:
        print(f"Error initializing LlamaParse: {e}")
        return # Exit if initialization fails

    # --- Output Directory ---
    try:
        os.makedirs(args.output, exist_ok=True)
        print(f"Output directory '{args.output}' ensured.")
    except OSError as e:
        print(f"Error creating output directory '{args.output}': {e}")
        return # Exit if output directory cannot be created

    # --- Input Handling ---
    documents = []
    temp_dir = None # To keep track of temporary directory for zip files

    try:
        input_path = args.input
        output_path = args.output

        if os.path.isfile(input_path):
            # Get the file extension
            _, file_extension = os.path.splitext(input_path)
            file_extension = file_extension.lower() # Ensure case-insensitivity

            # Check if the extension is in our extractor OR if it's a zip file
            if file_extension in file_extractor:
                print(f"Processing single file ({file_extension}): {input_path}")
                reader = SimpleDirectoryReader(input_files=[input_path], file_extractor=file_extractor)
                documents = reader.load_data()
            elif file_extension == '.zip':
                print(f"Processing ZIP archive: {input_path}")
                temp_dir = tempfile.mkdtemp()
                print(f"Extracting ZIP contents to temporary directory: {temp_dir}")
                with zipfile.ZipFile(input_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Check if extraction resulted in *any* supported files (not just PDF)
                supported_extensions = tuple(file_extractor.keys())
                extracted_files = []
                for ext in supported_extensions:
                    # Use '*' before extension to match filenames like 'file.pdf'
                    extracted_files.extend(glob.glob(os.path.join(temp_dir, '**', f'*{ext}'), recursive=True))

                if not extracted_files:
                     print(f"Warning: No supported files ({', '.join(supported_extensions)}) found in the extracted ZIP archive: {input_path}")
                else:
                    print(f"Found {len(extracted_files)} supported files in ZIP. Processing directory: {temp_dir}")
                    # SimpleDirectoryReader will automatically pick up supported files based on file_extractor
                    reader = SimpleDirectoryReader(input_dir=temp_dir, file_extractor=file_extractor, recursive=True)
                    documents = reader.load_data()
            else:
                print(f"Error: Input file '{input_path}' has an unsupported extension ('{file_extension}').")
                print(f"Supported extensions are: {', '.join(file_extractor.keys())} and .zip")
                return # Exit for unsupported file types
        
        elif os.path.isdir(input_path):
            print(f"Processing directory: {input_path}")
            # Check if directory contains any supported files
            supported_extensions = tuple(file_extractor.keys())
            found_files = []
            print(f"Searching for supported files ({', '.join(supported_extensions)}) in directory '{input_path}'...")
            for ext in supported_extensions:
                 # Use '*' before extension to match filenames like 'file.pdf'
                found_files.extend(glob.glob(os.path.join(input_path, '**', f'*{ext}'), recursive=True))

            if not found_files:
                print(f"Warning: No supported files ({', '.join(supported_extensions)}) found in the input directory: {input_path}")
                # We still proceed, SimpleDirectoryReader might handle things differently or find files LlamaParse can process without explicit extension mapping in future? Or maybe it should return here? Let's proceed for now.
                # documents = [] # Ensure documents list is empty if nothing found by glob
            else:
                 print(f"Found {len(found_files)} supported files in directory. Processing with SimpleDirectoryReader...")
            
            # Let SimpleDirectoryReader handle the actual loading based on file_extractor
            # It will internally filter based on the extensions provided in file_extractor
            # Exclude zip files when processing a directory directly
            reader = SimpleDirectoryReader(
                input_dir=input_path,
                file_extractor=file_extractor,
                recursive=True,
                exclude=["*.zip"] # Add exclusion for zip files
            )
            documents = reader.load_data()
        
        else:
            print(f"Error: Input path '{input_path}' is not a valid file or directory.")
            return # Exit for invalid path

        # --- Process and Save ---
        if documents: # Only process if documents were loaded
            process_and_save(documents, output_path)
        else:
            print("No documents were loaded or found to process.")

    except FileNotFoundError:
        print(f"Error: Input path '{args.input}' not found.")
    except zipfile.BadZipFile:
        print(f"Error: Input file '{args.input}' is not a valid ZIP file.")
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")
    finally:
        # --- Cleanup ---
        if temp_dir and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)

    print("Script finished.")

if __name__ == "__main__":
    main()