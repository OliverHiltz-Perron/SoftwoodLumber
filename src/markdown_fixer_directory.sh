#!/bin/bash

# Create output directory if it doesn't exist
mkdir -p markdown_fixed

# Loop through all markdown files in the source directory
for file in 20250301_Markdown/*.md; do
    # Get just the filename without the path
    filename=$(basename "$file")
    
    # Define the output file path
    output_file="markdown_fixed/${filename}"
    
    echo "Processing: $file -> $output_file"
    
    # Run the markdown fixer on the file
    python markdown_fixer.py "$file" "$output_file"
    
    # Check if processing was successful
    if [ $? -eq 0 ]; then
        echo "Successfully processed: $filename"
    else
        echo "Error processing: $filename"
    fi
    
    echo "-----------------------------------------"
done

echo "All files processed. Results are in the markdown_fixed directory." 