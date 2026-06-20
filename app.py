import os
import re
import subprocess
import shutil
import tempfile
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB upload limit

# ── Persistent project storage (saved_projects/ next to app.py) ───────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, 'saved_projects')
os.makedirs(PROJECTS_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'eps', 'svg'}


# ── Helpers ────────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def extract_bib_name(tex_content):
    """Return the bib name from \\bibliography{name}, or 'document' as fallback."""
    match = re.search(r'\\bibliography\{([^}]+)\}', tex_content)
    if match:
        return match.group(1).split(',')[0].strip()
    return 'document'


def sanitize_asset_name(filename):
    """Spaces and shell-hostile chars → underscores, extension preserved."""
    name, ext = os.path.splitext(filename)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w.\-]', '_', name)
    return name + ext


def patch_tex_for_assets(tex_content, rename_map):
    """Replace original (spaced) filenames in .tex with sanitised versions."""
    for original, safe in rename_map.items():
        if original == safe:
            continue
        tex_content = tex_content.replace(original, safe)
        orig_noext = os.path.splitext(original)[0]
        safe_noext = os.path.splitext(safe)[0]
        if orig_noext != safe_noext:
            tex_content = tex_content.replace(orig_noext, safe_noext)
    return tex_content


def _hint_from_log(log_text):
    """Append plain-English hints for the most common fatal LaTeX errors."""
    hints = []
    if "File `" in log_text and "' not found" in log_text:
        for m in re.findall(r"File `([^']+)' not found", log_text):
            if any(m.endswith(e) for e in ('.png', '.jpg', '.jpeg', '.pdf', '.eps', '.svg')):
                hints.append(f"\n⚠ Image not found: '{m}'\n  → Upload it via the Assets panel.")
            else:
                hints.append(f"\n⚠ File not found: '{m}'\n  → Missing .cls/.sty — run: sudo apt-get install texlive-full")
    if "Undefined control sequence" in log_text:
        hints.append("\n⚠ Undefined control sequence — check for typos in LaTeX commands.")
    if "Missing $ inserted" in log_text:
        hints.append("\n⚠ Missing $ — math symbol used outside math mode.")
    return '\n'.join(hints)


def save_project(project_name, tex_content, bib_content, bib_name, image_files, rename_map):
    """
    Persist project to  saved_projects/<project_name>/
      - document.tex
      - <bib_name>.bib
      - all uploaded images (sanitised filenames)
      - .meta  (ISO timestamp)
    Returns the project directory path.
    """
    safe_name   = re.sub(r'[^\w\-]', '_', project_name) or 'untitled'
    project_dir = os.path.join(PROJECTS_DIR, safe_name)
    os.makedirs(project_dir, exist_ok=True)

    with open(os.path.join(project_dir, 'document.tex'), 'w', encoding='utf-8') as f:
        f.write(tex_content)

    with open(os.path.join(project_dir, f'{bib_name}.bib'), 'w', encoding='utf-8') as f:
        f.write(bib_content)

    for img in image_files:
        original = img.filename
        if original and original in rename_map:
            safe = rename_map[original]
            img.stream.seek(0)
            img.save(os.path.join(project_dir, safe))

    with open(os.path.join(project_dir, '.meta'), 'w') as f:
        f.write(datetime.now().isoformat())

    return project_dir


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/projects', methods=['GET'])
def list_projects():
    """List all saved projects with last-saved timestamps."""
    projects = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        path = os.path.join(PROJECTS_DIR, name)
        if not os.path.isdir(path):
            continue
        meta_path = os.path.join(path, '.meta')
        saved_at  = open(meta_path).read().strip() if os.path.exists(meta_path) else ''
        projects.append({'name': name, 'saved_at': saved_at})
    return jsonify(projects)


@app.route('/projects/<project_name>', methods=['GET'])
def load_project(project_name):
    """Return saved .tex, .bib content and image list for a project."""
    safe        = re.sub(r'[^\w\-]', '_', project_name)
    project_dir = os.path.join(PROJECTS_DIR, safe)
    if not os.path.isdir(project_dir):
        return jsonify({'success': False, 'error': 'Project not found'}), 404

    tex_path = os.path.join(project_dir, 'document.tex')
    tex      = open(tex_path, encoding='utf-8').read() if os.path.exists(tex_path) else ''

    bib = ''
    for fname in os.listdir(project_dir):
        if fname.endswith('.bib'):
            bib = open(os.path.join(project_dir, fname), encoding='utf-8').read()
            break

    img_exts = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.eps', '.svg'}
    images   = [f for f in os.listdir(project_dir)
                if os.path.splitext(f)[1].lower() in img_exts]

    return jsonify({'success': True, 'tex': tex, 'bib': bib, 'images': images})


@app.route('/projects/<project_name>', methods=['DELETE'])
def delete_project(project_name):
    safe        = re.sub(r'[^\w\-]', '_', project_name)
    project_dir = os.path.join(PROJECTS_DIR, safe)
    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir)
    return jsonify({'success': True})


@app.route('/projects/<project_name>/assets/<path:filename>', methods=['GET'])
def get_project_asset(project_name, filename):
    """Serve a single saved image asset belonging to a project, so the
    front-end can re-populate the Assets panel when a project is reopened."""
    safe        = re.sub(r'[^\w\-]', '_', project_name)
    project_dir = os.path.join(PROJECTS_DIR, safe)

    # secure_filename strips path separators / traversal sequences, and we
    # additionally confirm the resolved path stays inside project_dir.
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    file_path = os.path.abspath(os.path.join(project_dir, safe_filename))
    if not file_path.startswith(os.path.abspath(project_dir) + os.sep):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    ext = os.path.splitext(safe_filename)[1].lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({'success': False, 'error': 'Not an asset file'}), 400

    if not os.path.isfile(file_path):
        return jsonify({'success': False, 'error': 'Asset not found'}), 404

    return send_file(file_path, as_attachment=False)


@app.route('/compile', methods=['POST'])
def compile_latex():
    tex_content  = request.form.get('tex_content', '')
    bib_content  = request.form.get('bib_content', '')
    project_name = request.form.get('project_name', '').strip() or 'untitled'

    if not tex_content.strip():
        return jsonify({'success': False, 'log': 'Error: No LaTeX content provided.'}), 400

    workspace = tempfile.mkdtemp(prefix='latexjob_')
    job_name  = 'document'
    tex_file  = os.path.join(workspace, f'{job_name}.tex')
    pdf_file  = os.path.join(workspace, f'{job_name}.pdf')
    bib_name  = extract_bib_name(tex_content)
    bib_file  = os.path.join(workspace, f'{bib_name}.bib')

    try:
        # ── 1. Sanitise & stage uploaded images ───────────────────────────
        rename_map      = {}
        uploaded_images = request.files.getlist('images')
        for img in uploaded_images:
            if img and img.filename and allowed_file(img.filename):
                original = img.filename
                safe     = sanitize_asset_name(original)
                rename_map[original] = safe
                img.stream.seek(0)
                img.save(os.path.join(workspace, safe))

        # ── 2. Patch spaced filenames in .tex ─────────────────────────────
        tex_content = patch_tex_for_assets(tex_content, rename_map)

        # ── 3. Auto-save project to disk ──────────────────────────────────
        for img in uploaded_images:
            img.stream.seek(0)
        project_dir = save_project(
            project_name, tex_content, bib_content,
            bib_name, uploaded_images, rename_map
        )
        saved_at = datetime.now().strftime('%H:%M:%S')

        # ── 4. Write source files to temp workspace ────────────────────────
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(tex_content)
        with open(bib_file, 'w', encoding='utf-8') as f:
            f.write(bib_content)

        # Copy any previously-saved images that weren't re-uploaded this time
        img_exts = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.eps', '.svg'}
        for fname in os.listdir(project_dir):
            if os.path.splitext(fname)[1].lower() in img_exts:
                dst = os.path.join(workspace, fname)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(project_dir, fname), dst)

        run_kwargs = dict(cwd=workspace, capture_output=True, text=True, timeout=60)
        full_log   = [f'💾 Auto-saved → saved_projects/{re.sub(r"[^\\w\\-]","_",project_name)}/ at {saved_at}\n']

        # ── pdflatex pass 1 ───────────────────────────────────────────────
        r1 = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', f'{job_name}.tex'],
            **run_kwargs)
        full_log += ['=== pdflatex (pass 1) ===', r1.stdout]
        if r1.returncode != 0:
            full_log.append(_hint_from_log(r1.stdout))
            return jsonify({'success': False, 'log': '\n'.join(full_log), 'saved_at': saved_at}), 200

        # ── bibtex ────────────────────────────────────────────────────────
        if bib_content.strip():
            r2 = subprocess.run(['bibtex', job_name], **run_kwargs)
            full_log += [f'\n=== bibtex (using {bib_name}.bib) ===', r2.stdout]
            if r2.stderr:
                full_log.append(r2.stderr)

        # ── pdflatex pass 2 ───────────────────────────────────────────────
        r3 = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', f'{job_name}.tex'],
            **run_kwargs)
        full_log += ['\n=== pdflatex (pass 2) ===', r3.stdout]
        if r3.returncode != 0:
            full_log.append(_hint_from_log(r3.stdout))
            return jsonify({'success': False, 'log': '\n'.join(full_log), 'saved_at': saved_at}), 200

        # ── pdflatex pass 3 ───────────────────────────────────────────────
        r4 = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-halt-on-error', f'{job_name}.tex'],
            **run_kwargs)
        full_log += ['\n=== pdflatex (pass 3) ===', r4.stdout]
        if r4.returncode != 0:
            full_log.append(_hint_from_log(r4.stdout))
            return jsonify({'success': False, 'log': '\n'.join(full_log), 'saved_at': saved_at}), 200

        if not os.path.exists(pdf_file):
            full_log.append('\nError: PDF not generated despite successful compilation.')
            return jsonify({'success': False, 'log': '\n'.join(full_log), 'saved_at': saved_at}), 200

        # Save PDF into project folder too
        shutil.copy2(pdf_file, os.path.join(project_dir, 'document.pdf'))

        output_pdf = os.path.join(tempfile.gettempdir(), f'output_{uuid.uuid4().hex}.pdf')
        shutil.copy2(pdf_file, output_pdf)
        return send_file(output_pdf, mimetype='application/pdf',
                         as_attachment=False, download_name='document.pdf')

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'log': 'Compilation timed out after 60 seconds.'}), 200
    except FileNotFoundError as e:
        return jsonify({'success': False,
                        'log': f'Tool not found: {e}\n\nInstall with: sudo apt-get install texlive-full'}), 200
    except Exception as e:
        return jsonify({'success': False, 'log': f'Server error: {str(e)}'}), 500
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
