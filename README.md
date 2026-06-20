# Scholex — Web-Based LaTeX Editor

Scholex is a lightweight, web-based LaTeX and BibTeX editor built with Python (Flask) and vanilla web technologies. It provides a real-time, split-pane workspace for drafting research papers, managing bibliographies, and uploading image assets—all compiled locally on your server.

## ✨ Features

* **Dual Editor Workspace:** Side-by-side editing for `document.tex` and `references.bib`.
* **Live PDF Preview:** Instantly view compiled outputs via an embedded PDF viewer.
* **Local Project Persistence:** Auto-saves projects, assets, and source files directly to the server's disk (`/saved_projects`).
* **Asset Management:** Drag-and-drop file uploading for images (`.png`, `.jpg`, `.pdf`, `.eps`) with automatic filename sanitization.
* **Detailed Compilation Logs:** Real-time stdout capture for `pdflatex` and `bibtex` to easily debug syntax errors.
* **Immersive Fullscreen Mode:** Distraction-free editing environment for heavy writing sessions.

## 🛠️ Tech Stack

* **Backend:** Python 3, Flask, Werkzeug
* **Frontend:** HTML5, CSS3 (Custom Design Tokens), Vanilla JavaScript
* **System Dependencies:** `texlive-full` (for `pdflatex` and `bibtex` execution)

## 🚀 Installation & Setup

### 1. System Prerequisites
Scholex requires a working installation of LaTeX on the host machine. If you are using an Ubuntu/Debian environment, you can install the full TeX Live distribution:

```bash
sudo apt-get update
sudo apt-get install texlive-full
