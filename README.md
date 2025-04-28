# 🌲 SoftwoodLumber 🌲

## 📋 Project Overview
SoftwoodLumber is a toolkit for processing and converting markdown files using Generative AI (Gemini). The project focuses on cleaning up markdown formatting, especially text converted from PDFs, extracting propositions for embedding, and converting markdown to JSON.

## 📁 Project Structure
```
SoftwoodLumber/
├── .env                      # Environment variables configuration
├── .git/                     # Git repository data
├── .gitignore                # Git ignore rules
├── prompts/                  # Prompt templates for AI models
│   ├── markdown_prompt.txt   # Template for markdown formatting 
│   └── markdown_to_json.txt  # Template for markdown to JSON conversion
├── README.md                 # This file
├── requirements.txt          # Python dependencies
└── src/                      # Source code
    ├── markdown_fixer.py            # Script to fix markdown formatting using Gemini
    ├── markdown_fixer_directory.sh  # Shell script to process multiple files
    ├── markdown_to_json.py          # Script to convert markdown to JSON
    └── Propositions.py              # Extracts propositions for embedding
```

## 🧪 Markdown Processing Pipeline
```
                   ┌───────────────────┐
                   │  Input Markdown   │
                   │ (from PDF/source) │
                   └─────────┬─────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────┐
│              markdown_fixer.py                   │
│ ┌────────────────────────────────────────────┐   │
│ │1. Read input markdown file                 │   │
│ │2. Load prompt from markdown_prompt.txt     │   │
│ │3. Send to Gemini API with prompt template  │   │
│ │4. Gemini fixes formatting issues:          │   │
│ │   - Join broken lines                      │   │
│ │   - Remove hyphenation                     │   │
│ │   - Clean headers/footers/page numbers     │   │
│ │   - Standardize markdown syntax            │   │
│ │   - Fix tables                             │   │
│ │   - Correct spacing                        │   │
│ │5. Save cleaned markdown                    │   │
│ └────────────────────────────────────────────┘   │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │    Cleaned Markdown     │
         └────────────┬────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│              Propositions.py                │
│ ┌─────────────────────────────────────────┐ │
│ │1. Process cleaned markdown              │ │
│ │2. Extract discrete propositions         │ │
│ │3. Identify key concepts and statements  │ │
│ │4. Prepare propositions for embedding    │ │
│ │5. Output structured propositions        │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
       ┌───────────────────────────────┐
       │      Extracted Propositions   │
       │     (Ready for Embedding)     │
       └───────────────┬───────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│            markdown_to_json.py              │
│ ┌─────────────────────────────────────────┐ │
│ │1. Read processed markdown               │ │
│ │2. Load prompt from markdown_to_json.txt │ │
│ │3. Send to Gemini API with prompt        │ │
│ │4. Gemini converts markdown to JSON      │ │
│ │5. Save structured JSON output           │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
          ┌────────────────────┐
          │   JSON Output      │
          │ (Structured Data)  │
          └────────────────────┘
```

## 🔧 Features
- 🧹 Clean up markdown formatting issues from PDF conversions
- 🔍 Extract key propositions for semantic embedding
- 🔄 Convert markdown documents to structured JSON
- 📚 Process entire directories of markdown files
- 🤖 Leverage Gemini AI for intelligent text processing

## 📦 Dependencies
- google-generativeai >= 0.3.0
- python-dotenv >= 1.0.0
- requests >= 2.31.0
- pandas >= 2.0.0
- colorama >= 0.4.6
- tqdm >= 4.66.0

## 🚀 Getting Started
1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up your `.env` file with `GEMINI_API_KEY=your_api_key_here`
4. Run the scripts from the `src` directory

## 📝 Usage Examples
### Fixing Markdown Formatting
```bash
python src/markdown_fixer.py input.md output.md
```

### Extracting Propositions
```bash
python src/Propositions.py cleaned_markdown.md propositions_output.txt
```

### Converting Markdown to JSON
```bash
python src/markdown_to_json.py input.md output.json
```

### Processing Directory of Files
```bash
./src/markdown_fixer_directory.sh input_directory output_directory
```

## 🔧 How It Works
1. **PDF-to-Markdown Conversion**: Start with markdown files (often with formatting issues from PDF conversion)
2. **Markdown Fixing**: The toolkit uses Gemini AI to intelligently clean up the markdown
3. **Proposition Extraction**: Extract key propositions from the text for semantic embedding
4. **Batch Processing**: Process entire directories of files with the shell script
5. **JSON Conversion**: Convert cleaned markdown to structured JSON for programmatic use
6. **Additional Processing**: Use the structured data for further analysis or applications

## 🔗 Related Projects
- Gemini API documentation: https://ai.google.dev/
- Markdown specification: https://www.markdownguide.org/

---
📚 Making document processing easier with the power of AI 🤖