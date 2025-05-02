#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import tempfile
import datetime
import shutil

def main():
    parser = argparse.ArgumentParser(description="Process documents to extract and match propositions")
    parser.add_argument("input", help="Input document file (PDF, DOCX, etc.)")
    parser.add_argument("--output-dir", "-d", default=None, 
                      help="Output directory (default: creates a new directory based on filename)")
    parser.add_argument("--database", default="propositions_rows.csv", 
                      help="Path to database CSV file with pre-computed embeddings")
    parser.add_argument("--skip-citations", action="store_true", help="Skip the citation selection step")
    args = parser.parse_args()
    
    # Get input filename without extension
    input_filename = os.path.basename(args.input)
    base_name = os.path.splitext(input_filename)[0]
    
    # Create output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"{base_name}_analysis_{timestamp}"
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Set output file paths
    output_json = os.path.join(output_dir, f"{base_name}_results.json")
    output_csv = os.path.join(output_dir, f"{base_name}_citations.csv")
    
    # Create temporary directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Processing document: {args.input}")
        print(f"Results will be saved to: {output_dir}")
        
        # Step 1: Convert document to markdown
        print("Step 1/4: Converting document to markdown...")
        result = subprocess.run(
            ["python", "src/llamaparse_converter.py", "-i", args.input, "-o", "-"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"Error in document conversion:\n{result.stderr}", file=sys.stderr)
            return 1
            
        markdown_content = result.stdout
        
        # Save intermediate markdown file
        markdown_path = os.path.join(output_dir, f"{base_name}_raw.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Step 2: Fix markdown formatting
        print("Step 2/4: Fixing markdown formatting...")
        result = subprocess.run(
            ["python", "src/markdown_fixer.py", "-i", "-", "-o", "-"],
            input=markdown_content, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"Error in markdown fixing:\n{result.stderr}", file=sys.stderr)
            return 1
            
        fixed_markdown = result.stdout
        
        # Save fixed markdown file
        fixed_markdown_path = os.path.join(output_dir, f"{base_name}_cleaned.md")
        with open(fixed_markdown_path, 'w', encoding='utf-8') as f:
            f.write(fixed_markdown)
        
        # Step 3: Extract propositions
        print("Step 3/4: Extracting propositions...")
        result = subprocess.run(
            ["python", "src/propositions.py", "-i", "-", "-o", "-"],
            input=fixed_markdown, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"Error in proposition extraction:\n{result.stderr}", file=sys.stderr)
            return 1
            
        propositions_json = result.stdout
        
        # Save propositions JSON
        propositions_path = os.path.join(output_dir, f"{base_name}_propositions.json")
        with open(propositions_path, 'w', encoding='utf-8') as f:
            f.write(propositions_json)
        
        # Step 4: Find similar propositions in database
        print(f"Step 4/4: Finding similar propositions in database...")
        result = subprocess.run(
            ["python", "src/QueryJson.py", "-i", "-", "-o", output_json, "-d", args.database],
            input=propositions_json, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"Error in database matching:\n{result.stderr}", file=sys.stderr)
            return 1
            
        # Step 5 (Optional): Select best citations
        if not args.skip_citations:
            print("Bonus step: Selecting best citations...")
            result = subprocess.run(
                ["python", "src/citation.py", "--input", output_json, "--output", output_csv],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                print(f"Error in citation selection:\n{result.stderr}", file=sys.stderr)
                return 1
                
            print(f"Best citations saved to: {output_csv}")
        
        # Make a copy of the original document in the output folder
        shutil.copy2(args.input, os.path.join(output_dir, input_filename))
        
        # Automatically open the folder
        try:
            if sys.platform == 'win32':
                os.startfile(output_dir)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', output_dir])
            else:  # Linux
                subprocess.run(['xdg-open', output_dir])
        except Exception as e:
            print(f"Could not open output folder automatically: {e}")
            print(f"Please open manually: {os.path.abspath(output_dir)}")
        
        print(f"Processing complete! All results saved to: {output_dir}")
        return 0

if __name__ == "__main__":
    sys.exit(main())