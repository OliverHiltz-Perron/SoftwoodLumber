# Softwood Lumber Board Document Checker 🌲

This application processes documents related to the wood industry, extracting key information and finding relationships to a database of propositions.

## How It Works

The Document Checker processes documents through a multi-stage pipeline:

1. **Document Parsing**: Converts PDFs, Word documents, PowerPoint presentations, and other formats into clean Markdown text using LlamaParse
2. **Markdown Cleaning**: Improves the formatting of the extracted text using Gemini AI
3. **Proposition Extraction**: Identifies key propositions (statements, claims, facts) within the document
4. **Similarity Matching**: Compares extracted propositions with a database of known propositions
5. **Citation Selection**: Uses AI to select the best matching citations for each proposition

### Using the Application

1. **Upload your document** through the web interface
2. **Review the results** in the generated output folder, which contains:
   - Original document copy
   - Raw extracted markdown
   - Cleaned markdown text
   - Extracted propositions JSON
   - Database matches for each proposition
   - Best citations in CSV format (if enabled)
3. **Explore relationships** between your document and the proposition database

All results are saved to a timestamped folder that opens automatically when processing is complete.

## Setup

### Prerequisites

- Python 3.8 or higher
- Required libraries (see requirements.txt)

### API Keys

The application requires the following API keys:

- LlamaParse API Key
- Gemini API Key
- OpenAI API Key

You need to provide these keys in a `.env` file in the project root directory:

```
LLAMA_CLOUD_API_KEY=your_llama_key_here
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
```

## Command Line Usage

You can run the application from the command line:

```bash
python documentprocessor.py your_document.pdf
```

This will:

1. Process your document through all stages
2. Create a timestamped output folder
3. Save all intermediate and final outputs
4. Open the output folder automatically

### Command Line Options

```
usage: document_processor.py [-h] [--output-dir OUTPUT_DIR] [--database DATABASE] [--skip-citations] input

Process documents to extract and match propositions

positional arguments:
  input                 Input document file (PDF, DOCX, etc.)

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR, -d OUTPUT_DIR
                        Output directory (default: creates a new directory based on filename)
  --database DATABASE   Path to database CSV file with pre-computed embeddings
  --skip-citations      Skip the citation selection step
```

## Working with the Results

- **JSON Output**: Review extracted propositions and database matches in structured JSON format
- **CSV Citations**: View selected citations in CSV format for easy reference or importing into other tools
- **Markdown Files**: Examine the document content in clean, structured text format

## Troubleshooting

- **Application errors**: Check terminal output for detailed error messages
- **API key errors**: Ensure your .env file is properly formatted with valid API keys
- **Processing errors**: Check the terminal output for specific error messages from each processing stage

## Updating Dependencies

If you need to update the project dependencies, modify the `requirements.txt` file and install the updated dependencies:

```bash
pip install -r requirements.txt
```
