# backend/cli.py

import argparse
import os
from llamaparse_service import LlamaParseService

def main():
    """
    Command-line interface for the LlamaParse converter.
    """
    # Argument Parsing
    parser = argparse.ArgumentParser(description="Convert documents to Markdown using LlamaParse.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input file, directory, or ZIP archive.")
    parser.add_argument("-o", "--output", required=True, help="Path to the directory where Markdown files will be saved.")
    args = parser.parse_args()
    
    print(f"Starting conversion. Input: {args.input}, Output: {args.output}")
    
    try:
        # Initialize LlamaParseService
        service = LlamaParseService()
        
        # Ensure output directory exists
        os.makedirs(args.output, exist_ok=True)
        
        # Process based on input type
        if os.path.isfile(args.input):
            if args.input.lower().endswith('.zip'):
                print(f"Processing ZIP archive: {args.input}")
                created_files = service.process_zip(args.input, args.output)
            else:
                print(f"Processing file: {args.input}")
                created_files = service.process_file(args.input, args.output)
        
        elif os.path.isdir(args.input):
            print(f"Processing directory: {args.input}")
            created_files = service.process_directory(args.input, args.output)
        
        else:
            print(f"Error: Input path '{args.input}' is not a valid file or directory.")
            return
        
        # Report results
        if created_files:
            print(f"Conversion complete! Created {len(created_files)} Markdown file(s):")
            for file_path in created_files:
                print(f"  - {file_path}")
        else:
            print("No Markdown files were created. The input may be empty or unsupported.")
            
    except Exception as e:
        print(f"Error during conversion: {str(e)}")

if __name__ == "__main__":
    main()