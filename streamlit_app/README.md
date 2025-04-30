# Softwood Lumber Analysis Tool

A comprehensive Streamlit application for analyzing documents related to the softwood lumber industry.

## Features

The app includes the following tools:

1. **PDF to Markdown Converter** - Convert PDF documents to clean Markdown format using LlamaParse
2. **Markdown Formatting Fixer** - Fix formatting issues in Markdown files using Gemini AI
3. **Proposition Extractor** - Extract key propositions from documents related to softwood lumber
4. **Markdown to JSON Converter** - Convert Markdown files to structured JSON data
5. **Semantic Search** - Find semantically similar text using embeddings

## Unified File System

The app features a centralized file storage system that allows for seamless workflow between tools.

### How It Works

All files processed by any tool are automatically saved to appropriate directories in the `data/` folder:

```
data/
├── markdown/            # Raw markdown from PDF conversion
├── fixed_markdown/      # Markdown after formatting fixes 
├── json/                # JSON files from markdown conversion
├── propositions/        # Extracted propositions
└── enhanced_propositions/   # Propositions with semantic search results
```

### Benefits

- **No Downloads Required**: Files processed in one tool can be directly accessed by other tools
- **Persistent Storage**: Files remain available between app sessions
- **Cross-Tool Access**: Any tool can access files created by any other tool
- **Progress Visibility**: Sidebar shows files available at each processing stage

### Using the File System

1. In each tool, you can either:
   - Upload a new file
   - Select an existing file from any directory

2. The file browser shows:
   - File name
   - Directory location
   - Creation/modification date

3. Files are automatically saved to the appropriate directory based on their type and processing stage

4. The home page includes a universal file browser to view any file in the system

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root directory with your API keys:
   ```
   LLAMA_CLOUD_API_KEY=your_llama_cloud_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

## Workflow Example

A typical workflow might look like:

1. Use **PDF to Markdown** to convert a PDF document to Markdown
2. Use **Markdown Fixer** to clean up the formatting (select the file from storage)
3. Use **Proposition Extractor** to extract key statements (select the fixed file)
4. Use **Semantic Search** to find similar propositions across documents (select the proposition file)

At each stage, files are automatically saved to storage and can be accessed by any tool.

## Note on File Formats

- The Semantic Search tool works with proposition JSON files in a specific format
- Ensure your propositions_rows.csv file is in the project root directory for search functionality
