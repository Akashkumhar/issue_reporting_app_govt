from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import uuid
import hashlib
from sqlalchemy import and_
from models import Issue, User, ChatLog, IssueProgressImage, CoinTransaction, FastagRedemption
from db import db
from chatbot import send_message_to_gemini
from yolo_validator import is_valid_issue_image, validate_issue_image
from rewards import process_report, redeem_fastag, process_pending_payouts

issues_bp = Blueprint('issues', __name__)


@issues_bp.before_request
def block_banned_users():
    if current_user.is_authenticated and getattr(current_user, 'role', None) != 'admin':
        if getattr(current_user, 'is_banned', False):
            return jsonify({'error': 'Account is banned'}), 403


def _abs_upload_folder():
    folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.isabs(folder):
        folder = os.path.join(current_app.root_path, folder)
    return folder

def _issue_to_dict(issue):
    return {
        'id': issue.id,
        'user_id': issue.user_id,
        'lat': issue.lat,
        'lng': issue.lng,
        'description': issue.description,
        'image_path': issue.image_path,
        'status': issue.status,
        'progress': issue.progress,
        'assigned_worker_id': issue.assigned_worker_id
    }


def _safe_remove_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _delete_issue_with_files(issue):
    try:
        _safe_remove_file(issue.image_path)
    except Exception:
        pass

    progress_rows = IssueProgressImage.query.filter_by(issue_id=issue.id).all()
    for row in progress_rows:
        try:
            upload_folder = _abs_upload_folder()
            abs_path = os.path.join(upload_folder, row.image_path) if row.image_path else None
            _safe_remove_file(abs_path)
        except Exception:
            pass
        db.session.delete(row)

    db.session.delete(issue)

@issues_bp.route('/report', methods=['GET', 'POST'])
@login_required
def report_issue():
    if current_user.role != 'user':
        return jsonify({'error': 'Only users can report issues'}), 403
    if request.method == 'POST':
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        description = request.form.get('description')
        image = request.files.get('image')
        image_path = None
        yolo_info = None
        image_hash = None
        if image:
            filename = secure_filename(image.filename)
            upload_folder = _abs_upload_folder()
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            stored_filename = f"{uuid.uuid4().hex}_{filename}" if filename else f"{uuid.uuid4().hex}.jpg"
            image_path = os.path.join(upload_folder, stored_filename)
            image.save(image_path)

            try:
                with open(image_path, 'rb') as f:
                    image_hash = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                image_hash = None

            if image_hash:
                existing = Issue.query.filter(and_(Issue.user_id == current_user.id, Issue.image_hash == str(image_hash))).first()
                if existing is not None:
                    try:
                        os.remove(image_path)
                    except OSError:
                        pass
                    return jsonify({'error': 'Duplicate image detected. Please upload a new photo.'}), 400

            try:
                yolo_info = validate_issue_image(image_path, conf_threshold=0.25)
            except Exception:
                try:
                    os.remove(image_path)
                except OSError:
                    pass
                return jsonify({'error': 'AI model error while validating image. Check best.pt path and model dependencies.'}), 500
            if not yolo_info['is_valid']:
                try:
                    os.remove(image_path)
                except OSError:
                    pass
                return jsonify({'error': 'Image rejected by AI validation. Please upload a closer, well-lit pothole/road-damage image (try different angle).'}), 400

        issue = Issue(user_id=current_user.id, lat=lat, lng=lng, description=description, image_path=image_path, image_hash=image_hash)
        db.session.add(issue)
        db.session.commit()

        try:
            lat_f = float(lat) if lat is not None else None
            lng_f = float(lng) if lng is not None else None
        except (TypeError, ValueError):
            lat_f, lng_f = None, None

        awarded = False
        award_reason = 'not_evaluated'
        new_balance = None
        ai_conf = 0.0

        if lat_f is not None and lng_f is not None:
            try:
                ai_conf = float(yolo_info.get('max_confidence', 0.0)) if image and yolo_info else 0.0
            except Exception:
                ai_conf = 0.0

            try:
                awarded, award_reason, new_balance = process_report(current_user.id, lat_f, lng_f, ai_conf, issue_id=issue.id, image_hash=image_hash)
            except Exception:
                awarded, award_reason, new_balance = False, 'reward_error', None

        payload = {
            'message': 'Issue reported successfully',
            'issue_id': issue.id,
            'ai_confidence': float(ai_conf),
            'reward_awarded': bool(awarded),
            'reward_reason': award_reason,
        }
        if new_balance is not None:
            payload['wallet_balance'] = int(new_balance)

        return jsonify(payload), 201
    return render_template('report.html')

@issues_bp.route('/issues', methods=['GET'])
@login_required
def get_issues():
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can view all issues'}), 403
    issues = Issue.query.all()
    return jsonify([_issue_to_dict(issue) for issue in issues]), 200

@issues_bp.route('/issues/mine', methods=['GET'])
@login_required
def get_my_issues():
    if current_user.role != 'user':
        return jsonify({'error': 'Only users can view their issues'}), 403
    issues = Issue.query.filter_by(user_id=current_user.id).order_by(Issue.id.desc()).all()
    return jsonify([_issue_to_dict(issue) for issue in issues]), 200


@issues_bp.route('/issues/<int:issue_id>', methods=['DELETE'])
@login_required
def delete_issue(issue_id):
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404

    if current_user.role == 'admin':
        pass
    elif current_user.role == 'user' and issue.user_id == current_user.id:
        pass
    else:
        return jsonify({'error': 'Access denied'}), 403

    _delete_issue_with_files(issue)
    db.session.commit()
    return jsonify({'message': 'Issue deleted'}), 200

@issues_bp.route('/issues/assigned', methods=['GET'])
@login_required
def get_assigned_issues():
    if current_user.role != 'worker':
        return jsonify({'error': 'Only workers can view assigned issues'}), 403
    issues = Issue.query.filter_by(assigned_worker_id=current_user.id).order_by(Issue.id.desc()).all()
    return jsonify([_issue_to_dict(issue) for issue in issues]), 200

@issues_bp.route('/issues/<int:issue_id>/progress', methods=['GET'])
@login_required
def get_issue_progress(issue_id):
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404

    is_admin = current_user.role == 'admin'
    is_owner = current_user.role == 'user' and issue.user_id == current_user.id
    is_assigned_worker = current_user.role == 'worker' and issue.assigned_worker_id == current_user.id

    if not (is_admin or is_owner or is_assigned_worker):
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({
        'id': issue.id,
        'status': issue.status,
        'progress': issue.progress,
        'completed': issue.progress >= 100
    }), 200

@issues_bp.route('/assign', methods=['POST'])
@login_required
def assign_issue():
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can assign issues'}), 403
    data = request.get_json()
    issue_id = data.get('issue_id')
    worker_id = data.get('worker_id')
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404
    worker = User.query.get(worker_id)
    if not worker or worker.role != 'worker':
        return jsonify({'error': 'Invalid worker'}), 400
    issue.assigned_worker_id = worker_id
    issue.status = 'assigned'
    db.session.commit()
    return jsonify({'message': 'Issue assigned successfully'}), 200

@issues_bp.route('/workers', methods=['GET'])
@login_required
def get_workers():
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can view workers'}), 403
    workers = User.query.filter_by(role='worker').order_by(User.username.asc()).all()
    return jsonify([{'id': w.id, 'username': w.username} for w in workers]), 200

@issues_bp.route('/update-status', methods=['POST'])
@login_required
def update_status():
    if current_user.role != 'worker':
        return jsonify({'error': 'Only workers can update status'}), 403
    data = request.get_json()
    issue_id = data.get('issue_id')
    status = data.get('status')
    issue = Issue.query.get(issue_id)
    if not issue or issue.assigned_worker_id != current_user.id:
        return jsonify({'error': 'Issue not found or not assigned to you'}), 404
    issue.status = status
    db.session.commit()
    return jsonify({'message': 'Status updated successfully'}), 200

@issues_bp.route('/issues/<int:issue_id>/progress', methods=['POST'])
@login_required
def update_progress(issue_id):
    if current_user.role != 'worker':
        return jsonify({'error': 'Only workers can update progress'}), 403

    issue = Issue.query.get(issue_id)
    if not issue or issue.assigned_worker_id != current_user.id:
        return jsonify({'error': 'Issue not found or not assigned to you'}), 404

    data = request.get_json() or {}
    progress = data.get('progress')
    try:
        progress = int(progress)
    except (TypeError, ValueError):
        return jsonify({'error': 'Progress must be an integer between 0 and 100'}), 400

    if progress < 0 or progress > 100:
        return jsonify({'error': 'Progress must be between 0 and 100'}), 400

    issue.progress = progress
    if progress >= 100:
        issue.progress = 100
        issue.status = 'resolved'
    elif progress > 0 and issue.status in ('pending', 'assigned'):
        issue.status = 'in-progress'

    db.session.commit()
    return jsonify({
        'message': 'Progress updated successfully',
        'id': issue.id,
        'status': issue.status,
        'progress': issue.progress,
        'completed': issue.progress >= 100
    }), 200


@issues_bp.route('/issues/<int:issue_id>/progress-images', methods=['POST'])
@login_required
def upload_progress_image(issue_id):
    if current_user.role != 'worker':
        return jsonify({'error': 'Only workers can upload progress images'}), 403

    issue = Issue.query.get(issue_id)
    if not issue or issue.assigned_worker_id != current_user.id:
        return jsonify({'error': 'Issue not found or not assigned to you'}), 404

    image = request.files.get('image')
    if not image:
        return jsonify({'error': 'Image is required'}), 400

    filename = secure_filename(image.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    upload_folder = _abs_upload_folder()
    progress_folder = os.path.join(upload_folder, 'progress')
    if not os.path.exists(progress_folder):
        os.makedirs(progress_folder)

    stored_filename = f"issue{issue_id}_worker{current_user.id}_{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(progress_folder, stored_filename)
    image.save(file_path)

    rel_path = os.path.join('progress', stored_filename)
    rec = IssueProgressImage(issue_id=issue_id, worker_id=current_user.id, image_path=rel_path)
    db.session.add(rec)
    db.session.commit()

    return jsonify({
        'message': 'Progress image uploaded',
        'id': rec.id,
        'issue_id': rec.issue_id,
        'worker_id': rec.worker_id,
        'created_at': rec.created_at.isoformat() if rec.created_at else None,
        'url': url_for('issues.get_progress_image_file', image_id=rec.id)
    }), 201


@issues_bp.route('/issues/<int:issue_id>/progress-images', methods=['GET'])
@login_required
def list_progress_images(issue_id):
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404

    is_admin = current_user.role == 'admin'
    is_owner = current_user.role == 'user' and issue.user_id == current_user.id
    is_assigned_worker = current_user.role == 'worker' and issue.assigned_worker_id == current_user.id
    if not (is_admin or is_owner or is_assigned_worker):
        return jsonify({'error': 'Access denied'}), 403

    images = IssueProgressImage.query.filter_by(issue_id=issue_id).order_by(IssueProgressImage.id.desc()).all()
    return jsonify([
        {
            'id': img.id,
            'issue_id': img.issue_id,
            'worker_id': img.worker_id,
            'created_at': img.created_at.isoformat() if img.created_at else None,
            'url': url_for('issues.get_progress_image_file', image_id=img.id)
        }
        for img in images
    ]), 200


@issues_bp.route('/issues/progress-images/<int:image_id>/file', methods=['GET'])
@login_required
def get_progress_image_file(image_id):
    img = IssueProgressImage.query.get(image_id)
    if not img:
        return jsonify({'error': 'Image not found'}), 404

    issue = Issue.query.get(img.issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404

    is_admin = current_user.role == 'admin'
    is_owner = current_user.role == 'user' and issue.user_id == current_user.id
    is_assigned_worker = current_user.role == 'worker' and issue.assigned_worker_id == current_user.id
    if not (is_admin or is_owner or is_assigned_worker):
        return jsonify({'error': 'Access denied'}), 403

    progress_folder = os.path.join(_abs_upload_folder(), 'progress')
    filename = os.path.basename(img.image_path)
    primary_path = os.path.join(progress_folder, filename)
    if os.path.exists(primary_path):
        return send_from_directory(progress_folder, filename)

    legacy_base = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    legacy_progress_folder = os.path.join(os.path.abspath(legacy_base), 'progress')
    legacy_path = os.path.join(legacy_progress_folder, filename)
    if os.path.exists(legacy_path):
        return send_from_directory(legacy_progress_folder, filename)

    return jsonify({'error': 'File not found'}), 404

@issues_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    message = data.get('message')
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    response = send_message_to_gemini(current_user.id, message)
    # Save to chat log
    chat_log = ChatLog(user_id=current_user.id, message=message, response=response)
    db.session.add(chat_log)
    db.session.commit()
    return jsonify({'response': response}), 200


@issues_bp.route('/admin/users', methods=['GET'])
@login_required
def admin_list_users():
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can manage users'}), 403

    users = User.query.order_by(User.id.asc()).all()
    out = []
    for u in users:
        out.append({
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'wallet_balance': int(getattr(u, 'wallet_balance', 0) or 0),
            'reputation_score': int(getattr(u, 'reputation_score', 0) or 0),
            'is_banned': bool(getattr(u, 'is_banned', False)),
        })
    return jsonify(out), 200


@issues_bp.route('/admin/users/<int:user_id>/ban', methods=['POST'])
@login_required
def admin_ban_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can manage users'}), 403

    u = User.query.get(user_id)
    if not u:
        return jsonify({'error': 'User not found'}), 404

    if u.role == 'admin':
        return jsonify({'error': 'Cannot ban admin accounts'}), 400

    data = request.get_json() or {}
    banned = bool(data.get('banned'))
    u.is_banned = banned
    db.session.commit()
    return jsonify({'message': 'Updated', 'id': u.id, 'is_banned': bool(u.is_banned)}), 200


@issues_bp.route('/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can manage users'}), 403

    if int(current_user.id) == int(user_id):
        return jsonify({'error': 'Cannot delete your own account'}), 400

    u = User.query.get(user_id)
    if not u:
        return jsonify({'error': 'User not found'}), 404

    if u.role == 'admin':
        return jsonify({'error': 'Cannot delete admin accounts'}), 400

    issues = Issue.query.filter_by(user_id=u.id).all()
    for issue in issues:
        _delete_issue_with_files(issue)

    worker_progress = IssueProgressImage.query.filter_by(worker_id=u.id).all()
    for row in worker_progress:
        try:
            upload_folder = _abs_upload_folder()
            abs_path = os.path.join(upload_folder, row.image_path) if row.image_path else None
            _safe_remove_file(abs_path)
        except Exception:
            pass
        db.session.delete(row)

    CoinTransaction.query.filter_by(user_id=u.id).delete(synchronize_session=False)
    FastagRedemption.query.filter_by(user_id=u.id).delete(synchronize_session=False)

    ChatLog.query.filter_by(user_id=u.id).delete(synchronize_session=False)

    db.session.delete(u)
    db.session.commit()

    return jsonify({'message': 'User deleted'}), 200


@issues_bp.route('/wallet', methods=['GET'])
@login_required
def get_wallet():
    return jsonify({
        'user_id': current_user.id,
        'wallet_balance': int(getattr(current_user, 'wallet_balance', 0) or 0),
        'reputation_score': int(getattr(current_user, 'reputation_score', 0) or 0)
    }), 200


@issues_bp.route('/fastag/redeem', methods=['POST'])
@login_required
def fastag_redeem():
    if current_user.role != 'user':
        return jsonify({'error': 'Only users can request FASTag redemption'}), 403

    data = request.get_json() or {}
    vehicle_number = data.get('vehicle_number')
    coins_to_spend = data.get('coins')
    if not vehicle_number:
        return jsonify({'error': 'vehicle_number is required'}), 400

    ok, out = redeem_fastag(current_user.id, vehicle_number, coins_to_spend)
    if not ok:
        return jsonify(out), 400
    return jsonify(out), 201


@issues_bp.route('/fastag/payouts/process', methods=['POST'])
@login_required
def fastag_process_payouts():
    if current_user.role != 'admin':
        return jsonify({'error': 'Only admins can process payouts'}), 403

    data = request.get_json() or {}
    success_rate = data.get('success_rate', 0.9)
    try:
        success_rate = float(success_rate)
    except (TypeError, ValueError):
        success_rate = 0.9

    summary = process_pending_payouts(success_rate=success_rate)
    return jsonify(summary), 200
