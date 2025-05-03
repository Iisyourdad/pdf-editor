README.md created with the following contents:

# PDF Toolkit

## Overview
PDF Toolkit is a PyQt5 application for combining, splitting, and removing pages from PDF files.

## Installation
1. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # on Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the main application:
```bash
python main.py
```

- **Combine PDFs**: Switch to the "Combine PDFs" tab, add files, arrange them, and click **Combine & Save As…**.
- **Split/Remove Pages**: Go to the "Split/Remove Pages" tab, select a PDF, click pages (use Shift+click for ranges), then **Remove Selected & Save As…**.

## License
MIT License
