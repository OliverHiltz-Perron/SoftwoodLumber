import argparse
import sys
import os

def clean_json_markdown_wrapping(input_path, output_path=None):
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Remove code block markers and empty lines
    cleaned_lines = [
        line for line in lines
        if not line.strip().startswith('```') and line.strip() != ''
    ]
    cleaned_content = ''.join(cleaned_lines).strip()
    # Optionally validate JSON
    import json
    try:
        obj = json.loads(cleaned_content)
    except Exception as e:
        print(f"Warning: Cleaned content is not valid JSON: {e}", file=sys.stderr)
        # Still write the cleaned content for inspection
    # Write to output
    if output_path is None:
        output_path = input_path
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
    print(f"Cleaned JSON written to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove markdown code block markers from a JSON file.")
    parser.add_argument('input', help='Input file path (JSON with possible markdown wrapping)')
    parser.add_argument('-o', '--output', help='Output file path (default: overwrite input)')
    args = parser.parse_args()
    clean_json_markdown_wrapping(args.input, args.output) 