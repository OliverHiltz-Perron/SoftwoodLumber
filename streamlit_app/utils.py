import os
import json
import streamlit as st
import pandas as pd
import shutil
import datetime
from pathlib import Path

# Define the data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Create the directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Sub-directories for different file types
MARKDOWN_DIR = os.path.join(DATA_DIR, "markdown")
FIXED_MARKDOWN_DIR = os.path.join(DATA_DIR, "fixed_markdown")
JSON_DIR = os.path.join(DATA_DIR, "json")
PROPOSITIONS_DIR = os.path.join(DATA_DIR, "propositions")
ENHANCED_PROPS_DIR = os.path.join(DATA_DIR, "enhanced_propositions")

# Create all subdirectories
for directory in [MARKDOWN_DIR, FIXED_MARKDOWN_DIR, JSON_DIR, PROPOSITIONS_DIR, ENHANCED_PROPS_DIR]:
    os.makedirs(directory, exist_ok=True)

def save_uploaded_file(uploaded_file, directory=None):
    """
    Save an uploaded file to the specified directory
    Returns the path to the saved file
    """
    if directory is None:
        directory = DATA_DIR
    
    # Create the directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create the file path
    file_path = os.path.join(directory, uploaded_file.name)
    
    # Write the file
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path

def save_markdown_file(content, filename, fixed=False):
    """
    Save a markdown file to the markdown directory
    If fixed=True, save to the fixed_markdown directory
    Returns the path to the saved file
    """
    directory = FIXED_MARKDOWN_DIR if fixed else MARKDOWN_DIR
    
    # Create the directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create the file path
    file_path = os.path.join(directory, filename)
    
    # Write the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return file_path

def save_json_file(content, filename, directory_type="json"):
    """
    Save a JSON file to the specified directory type
    directory_type can be "json", "propositions", or "enhanced_propositions"
    Returns the path to the saved file
    """
    if directory_type == "json":
        directory = JSON_DIR
    elif directory_type == "propositions":
        directory = PROPOSITIONS_DIR
    elif directory_type == "enhanced_propositions":
        directory = ENHANCED_PROPS_DIR
    else:
        directory = JSON_DIR
    
    # Create the directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create the file path
    file_path = os.path.join(directory, filename)
    
    # If content is already a dict or list, serialize it
    if isinstance(content, (dict, list)):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
    else:
        # Otherwise, assume it's already a JSON string
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    return file_path

def get_all_files_by_type(file_type, extensions=None):
    """
    Get all files of a specific type across all directories
    file_type can be "markdown", "fixed_markdown", "json", "propositions", "enhanced_propositions", or "all"
    Returns a list of (file_path, file_name, directory_name) tuples
    """
    if extensions is None:
        if file_type == "markdown" or file_type == "fixed_markdown":
            extensions = [".md"]
        elif file_type in ["json", "propositions", "enhanced_propositions"]:
            extensions = [".json"]
        else:
            extensions = []
    
    # Determine which directories to search
    directories = []
    if file_type == "markdown":
        directories = [MARKDOWN_DIR]
    elif file_type == "fixed_markdown":
        directories = [FIXED_MARKDOWN_DIR]
    elif file_type == "json":
        directories = [JSON_DIR]
    elif file_type == "propositions":
        directories = [PROPOSITIONS_DIR]
    elif file_type == "enhanced_propositions":
        directories = [ENHANCED_PROPS_DIR]
    elif file_type == "all":
        directories = [MARKDOWN_DIR, FIXED_MARKDOWN_DIR, JSON_DIR, PROPOSITIONS_DIR, ENHANCED_PROPS_DIR]
    
    # Collect all files
    all_files = []
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
        
        dir_name = os.path.basename(directory)
        
        for f in os.listdir(directory):
            file_path = os.path.join(directory, f)
            if os.path.isfile(file_path):
                # Check extensions if specified
                if extensions and not any(f.lower().endswith(ext.lower()) for ext in extensions):
                    continue
                
                all_files.append((file_path, f, dir_name))
    
    return all_files

def advanced_file_selector(title="Select a file:", file_types=None, exclude=None):
    """
    Create an advanced file selector that can browse all file types
    Returns the selected file path or None if no file is selected
    """
    if file_types is None:
        file_types = ["all"]
    
    if exclude is None:
        exclude = []
    
    # Get all files by type
    all_files = []
    for file_type in file_types:
        all_files.extend(get_all_files_by_type(file_type))
    
    # Filter out excluded files
    all_files = [f for f in all_files if f[1] not in exclude]
    
    if not all_files:
        st.info(f"No files available of the requested types: {', '.join(file_types)}.")
        return None
    
    # Sort files by modification time (newest first)
    all_files.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
    
    # Format file names with type and date
    file_options = []
    for file_path, file_name, dir_name in all_files:
        # Get file modification time
        mod_time = os.path.getmtime(file_path)
        mod_date = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
        
        # Format the option
        file_options.append(f"{file_name} ({dir_name}, {mod_date})")
    
    # Add a "None" option
    file_options.insert(0, "None")
    
    # Create the selectbox
    selected_option = st.selectbox(title, file_options)
    
    if selected_option == "None":
        return None
    
    # Extract just the file name and directory from the selected option
    parts = selected_option.split(" (")
    selected_file_name = parts[0]
    selected_dir_name = parts[1].split(",")[0]
    
    # Find the corresponding file path
    selected_file_path = next((file_path for file_path, file_name, dir_name in all_files 
                              if file_name == selected_file_name and dir_name == selected_dir_name), None)
    
    return selected_file_path

def display_shared_data_status():
    """
    Display the status of shared data in the app
    """
    st.sidebar.header("Stored Files")
    
    # Count files in each directory
    markdown_count = len(get_all_files_by_type("markdown"))
    fixed_md_count = len(get_all_files_by_type("fixed_markdown"))
    json_count = len(get_all_files_by_type("json"))
    prop_count = len(get_all_files_by_type("propositions"))
    enhanced_prop_count = len(get_all_files_by_type("enhanced_propositions"))
    
    # Display counts
    st.sidebar.markdown(f"📄 Markdown files: **{markdown_count}**")
    st.sidebar.markdown(f"🧹 Fixed markdown files: **{fixed_md_count}**")
    st.sidebar.markdown(f"🔄 JSON files: **{json_count}**")
    st.sidebar.markdown(f"📋 Proposition files: **{prop_count}**")
    st.sidebar.markdown(f"🔍 Enhanced proposition files: **{enhanced_prop_count}**")

    # Add a file browser in the sidebar
    with st.sidebar.expander("Browse All Files"):
        all_files = get_all_files_by_type("all")
        if all_files:
            # Group by directory
            files_by_dir = {}
            for file_path, file_name, dir_name in all_files:
                if dir_name not in files_by_dir:
                    files_by_dir[dir_name] = []
                files_by_dir[dir_name].append((file_path, file_name))
            
            # Display by directory
            for dir_name, files in files_by_dir.items():
                st.markdown(f"**{dir_name}**")
                for _, file_name in files:
                    st.markdown(f"- {file_name}")
        else:
            st.info("No files available.")
