# Supernote Cloud API Client for Python

Unofficial Python API client that allows you to access your Supernote files through the Supernote Cloud.

`sncloud` is intended for integrating your Supernote Cloud files into other apps. Yes, there are other cloud providers integrated into the Supernote which are easier to develop for, but only the Supernote Cloud offer "auto sync" at the moment. The Supernote APIs are extensive but this library only covers the subset that most developers will need for common filesystem actions such as list, download and upload files.

So while it doesn't currently cover every endpoint (for example you cannot delete, move or rename files) it will likely work for you. That said, PRs are weclome.

## Core Features

- 🔑 **Login** to the Supernote Cloud
- 🔍 **List** the files and folders for a parent directory
- 💾 **Get** a file and save it locally
- 📄 **Get** a note file and convert it to PDF
- 🖼 **Get** a note file and convert it to PNG
- 🔼 **Put** a file and upload it to the cloud
- 📂 **Make a directory** on the cloud

## Installation

`pip install sncloud`

## Usage

### Python API

```python
from sncloud import SNClient

client = SNClient()
client.login("test@example.com", "1234") # login with email and password
files = client.ls() # returns a list of the files/directories on the Supernote
print(files)
client.get("/Note/notes.note") # downloads the file with the given path
```

### Command Line Interface

The package also provides a command line interface:

```bash
# Login to your Supernote Cloud account
sncloud login

# List files in the root directory
sncloud ls

# List files in a specific directory
sncloud ls /Notes

# Download a file
sncloud get /Notes/document.note

# Download a note as PDF
sncloud get /Notes/document.note --pdf

# Download a note as PNG
sncloud get /Notes/document.note --png

# Download specific pages (works with both PDF and PNG)
sncloud get /Notes/document.note --pdf --pages "1,3,5"

# Set output directory
sncloud get /Notes/document.note --output /path/to/directory

# Create a new folder
sncloud mkdir NewFolder --parent /Notes

# Upload a file
sncloud put /path/to/file.txt --parent /Notes
```

The CLI will store your access token in `~/.config/sncloud/config.json` and automatically refresh it when needed.

## Roadmap

- [x] CLI/SHELL script
- [ ] Example scripts
- [ ] Advanced API calls
- [ ] Get Supernote Cloud API complete
- [ ] Docker container

## Want to contribute?

PRs are welcome. But please open an issue first to see if the proposed feature fits with the direction of this library.

## Acknowledgements

- General idea for a Supernote Cloud library taken from the amazing [rmapi](https://github.com/juruen/rmapi) project for the reMarkable cloud
- Help to identify API endpoints from [NYT crossword puzzle to Supernote script](https://github.com/bwhitman/supernote-cloud-python)
