# Scholex — Lightweight LaTeX Research Editor

A self-hosted, split-screen LaTeX editor for research papers, built with
Python/Flask and plain HTML/CSS/JS. Compiles `.tex` + `.bib` + images to PDF
via the native `pdflatex` / `bibtex` toolchain.

---

## Project Structure

```
latex-editor/
├── app.py               # Flask backend
├── requirements.txt     # Python dependencies
├── README.md
└── templates/
    └── index.html       # Single-page frontend
```

---

## Prerequisites

### 1. Python 3.9+
```bash
python3 --version
```

### 2. TeX Live (provides pdflatex & bibtex)
```bash
# Debian / Ubuntu
sudo apt-get update && sudo apt-get install -y texlive-full

# macOS (via Homebrew)
brew install --cask mactex

# Windows
# Download and install MiKTeX from https://miktex.org/
```

Verify the tools are on your PATH:
```bash
pdflatex --version
bibtex --version
```

---

## Setup & Run

```bash
# 1. Clone / copy this project
cd latex-editor

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Start the server
python app.py
```

Open your browser at **http://localhost:5000**

---

## Usage

| Action | How |
|--------|-----|
| Write LaTeX | Left pane → `document.tex` editor |
| Add references | Left pane → `references.bib` editor |
| Upload figures | Drop or browse images in the Assets section |
| Compile | Click **▶ Compile** or press **Ctrl+Enter** |
| View PDF | Right pane auto-updates after success |
| Debug errors | Log panel at bottom-right expands on failure |
| Load sample | Click ⚡ in the `.tex` editor tab |

---

## Compilation Pipeline

Each press of Compile runs the standard four-step sequence inside an
isolated temporary directory (cleaned up automatically):

```
pdflatex (pass 1)  →  bibtex  →  pdflatex (pass 2)  →  pdflatex (pass 3)
```

- BibTeX runs only when the `.bib` panel has content.
- Errors surface the full log output in the collapsible log panel.
- A 60-second timeout guards against runaway compilations.

---

## Configuration

Edit the top of `app.py` to change:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_CONTENT_LENGTH` | 32 MB | Max upload size |
| `timeout` in `subprocess.run` | 60 s | Compilation timeout |
| `port` in `app.run` | 5000 | Server port |

For production, run behind **Gunicorn** + **Nginx** instead of the dev server:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```
