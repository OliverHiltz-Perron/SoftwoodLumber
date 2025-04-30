# backend/llamaparse_service.py

import os
import zipfile
import tempfile
import shutil
import glob
import nest_asyncio
import warnings

# Suppress warnings
os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")

# Set a placeholder OpenAI API key to prevent prompts
os.environ["OPENAI_API_KEY"] = "placeholder-key-not-used"

from dotenv import load_dotenv
from llama_cloud_services import LlamaParse
from llama_index.core import SimpleDirectoryReader

# Apply nest_asyncio patch
nest_asyncio.apply()

class LlamaParseService:
    """Service for converting documents to Markdown using LlamaParse."""
    
    def __init__(self, api_key=None):
        """
        Initialize the LlamaParse service.
        
        Args:
            api_key (str, optional): LlamaParse API key. If None, will try to load from env vars.
        """
        if not api_key:
            load_dotenv()
            api_key = os.getenv("LLAMA_CLOUD_API_KEY")
            
        if not api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY not found in environment variables or .env file")
            
        self.parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            verbose=True
        )
        
        self.file_extractor = {
            ".pdf": self.parser,
            ".docx": self.parser,
            ".doc": self.parser,
            ".pptx": self.parser,
            ".ppt": self.parser,
            ".html": self.parser
        }
    
    def process_file(self, file_path, output_dir):
        """
        Process a single file and save the Markdown output.
        
        Args:
            file_path (str): Path to the file to process
            output_dir (str): Directory to save the output
            
        Returns:
            list: Paths to the created Markdown files
        """
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower()
        
        if file_extension not in self.file_extractor:
            raise ValueError(f"Unsupported file extension: {file_extension}")
            
        reader = SimpleDirectoryReader(input_files=[file_path], file_extractor=self.file_extractor)
        documents = reader.load_data()
        
        return self._process_and_save(documents, output_dir)
    
    def process_directory(self, dir_path, output_dir):
        """
        Process all supported files in a directory and save the Markdown output.
        
        Args:
            dir_path (str): Path to the directory to process
            output_dir (str): Directory to save the output
            
        Returns:
            list: Paths to the created Markdown files
        """
        reader = SimpleDirectoryReader(
            input_dir=dir_path,
            file_extractor=self.file_extractor,
            recursive=True,
            exclude=["*.zip"]
        )
        documents = reader.load_data()
        
        return self._process_and_save(documents, output_dir)
    
    def process_zip(self, zip_path, output_dir):
        """
        Extract and process all supported files in a ZIP archive.
        
        Args:
            zip_path (str): Path to the ZIP file
            output_dir (str): Directory to save the output
            
        Returns:
            list: Paths to the created Markdown files
        """
        temp_dir = tempfile.mkdtemp()
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            reader = SimpleDirectoryReader(
                input_dir=temp_dir,
                file_extractor=self.file_extractor,
                recursive=True
            )
            documents = reader.load_data()
            
            return self._process_and_save(documents, output_dir)
        finally:
            shutil.rmtree(temp_dir)
    
    def _process_and_save(self, documents, output_dir):
        """
        Process loaded documents, group content by original file,
        concatenate, and save as Markdown.
        
        Args:
            documents (list): List of document objects
            output_dir (str): Directory to save the output
            
        Returns:
            list: Paths to the created Markdown files
        """
        if not documents:
            return []
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Group content by target output file
        grouped_content = {}
        
        for doc in documents:
            try:
                if 'file_path' not in doc.metadata:
                    continue
                    
                original_full_path = doc.metadata['file_path']
                original_basename = os.path.basename(original_full_path)
                
                base_name_no_ext = os.path.splitext(original_basename)[0]
                output_filename = f"{base_name_no_ext}.md"
                output_filepath = os.path.join(output_dir, output_filename)
                
                content_chunk = doc.get_content()
                
                if output_filepath not in grouped_content:
                    grouped_content[output_filepath] = []
                
                grouped_content[output_filepath].append(content_chunk)
                
            except Exception as e:
                # Log error but continue processing
                continue
        
        # Concatenate and write grouped content
        created_files = []
        for output_filepath, content_chunks in grouped_content.items():
            try:
                full_markdown_content = "\n\n".join(content_chunks)
                
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    f.write(full_markdown_content)
                
                created_files.append(output_filepath)
                
            except Exception as e:
                # Log error but continue processing
                continue
        
        return created_files

    def get_supported_extensions(self):
        """
        Get the list of supported file extensions.
        
        Returns:
            list: List of supported file extensions
        """
        return list(self.file_extractor.keys()) + ['.zip']