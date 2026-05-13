import os
import io
import uuid
from PIL import Image
from flask import Blueprint, request, jsonify
from routes.auth import token_required

upload_bp = Blueprint('upload', __name__)

BASE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.ogg'}
ALLOWED_VIDEO_MIME_TYPES = {
    'video/mp4': '.mp4',
    'video/webm': '.webm',
    'video/ogg': '.ogg',
}


def _ensure_upload_dir(*parts):
    target_dir = os.path.join(BASE_UPLOAD_DIR, *parts)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


def _delete_upload_file(relative_path):
    path = str(relative_path or '').strip()
    if not path or not path.startswith('/uploads/'):
        return False

    rel_parts = path[len('/uploads/'):].lstrip('/').replace('/', os.sep)
    abs_path = os.path.realpath(os.path.join(BASE_UPLOAD_DIR, rel_parts))
    upload_root = os.path.realpath(BASE_UPLOAD_DIR)

    if abs_path != upload_root and not abs_path.startswith(upload_root + os.sep):
        return False

    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
            return True
        except OSError:
            return False
    return False


def _resolve_video_extension(file_storage):
    filename = str(getattr(file_storage, 'filename', '') or '')
    ext = os.path.splitext(filename)[1].lower()
    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return ext

    mimetype = str(getattr(file_storage, 'mimetype', '') or '').split(';')[0].strip().lower()
    return ALLOWED_VIDEO_MIME_TYPES.get(mimetype, '')


@upload_bp.route('/logo/<upload_type>', methods=['POST'])
@token_required
def upload_logo(current_user, upload_type):
    if upload_type not in ['college', 'university']:
        return jsonify({'message': 'Invalid type'}), 400

    file = request.files.get('logo')
    if not file:
        return jsonify({'message': 'No file uploaded'}), 400

    if not file.mimetype or not file.mimetype.startswith('image/'):
        return jsonify({'message': 'Only images allowed'}), 400

    folder_map = {
        'college': 'colleges',
        'university': 'universities',
    }
    folder = folder_map[upload_type]
    target_dir = _ensure_upload_dir(folder)

    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(target_dir, filename)

    try:
        image = Image.open(io.BytesIO(file.read())).convert('RGBA')

        # Keep original aspect ratio and place into 300x300 canvas like old backend.
        image.thumbnail((300, 300))
        canvas = Image.new('RGBA', (300, 300), (255, 255, 255, 255))
        x = (300 - image.width) // 2
        y = (300 - image.height) // 2
        canvas.paste(image, (x, y), image)
        canvas.save(filepath, format='PNG', optimize=True, compress_level=6)

        rel_path = f"/uploads/{folder}/{filename}"
        return jsonify({'path': rel_path, 'filename': filename})
    except Exception as exc:
        return jsonify({'message': str(exc)}), 500


@upload_bp.route('/video-guide', methods=['POST'])
@token_required
def upload_video_guide(current_user):
    if getattr(current_user, 'role', '') != 'admin':
        return jsonify({'message': 'Admin privilege required'}), 403

    file = request.files.get('video')
    if not file:
        return jsonify({'message': 'No file uploaded'}), 400

    ext = _resolve_video_extension(file)
    if not ext:
        return jsonify({'message': 'Only mp4, webm, and ogg video files are supported'}), 400

    target_dir = _ensure_upload_dir('video_guides')
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(target_dir, filename)

    try:
        file.save(filepath)
        return jsonify({
            'path': f"/uploads/video_guides/{filename}",
            'filename': filename,
        })
    except Exception as exc:
        return jsonify({'message': str(exc)}), 500


@upload_bp.route('/resume-photo', methods=['POST'])
@token_required
def upload_resume_photo(current_user):
    file = request.files.get('photo')
    if not file:
        return jsonify({'message': 'No file uploaded'}), 400

    if not file.mimetype or not file.mimetype.startswith('image/'):
        return jsonify({'message': 'Only images allowed'}), 400

    target_dir = _ensure_upload_dir('resumes')
    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(target_dir, filename)

    try:
        image = Image.open(io.BytesIO(file.read())).convert('RGBA')
        image.thumbnail((500, 700))
        canvas = Image.new('RGBA', image.size, (255, 255, 255, 255))
        canvas.paste(image, (0, 0), image)
        canvas.save(filepath, format='PNG', optimize=True, compress_level=6)
        return jsonify({
            'path': f"/uploads/resumes/{filename}",
            'filename': filename,
        })
    except Exception as exc:
        return jsonify({'message': str(exc)}), 500
