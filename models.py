from db import db
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # admin, user, worker

    wallet_balance = db.Column(db.Integer, nullable=False, default=0)
    reputation_score = db.Column(db.Integer, nullable=False, default=0)

    is_banned = db.Column(db.Boolean, nullable=False, default=False)

    # Relationship to issues
    issues = db.relationship('Issue', backref='user', lazy=True, foreign_keys='Issue.user_id')

class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200))
    image_hash = db.Column(db.String(64))
    status = db.Column(db.String(50), default='pending')  # pending, assigned, in-progress, resolved
    progress = db.Column(db.Integer, nullable=False, default=0)
    assigned_worker_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relationship to assigned worker
    assigned_worker = db.relationship('User', foreign_keys=[assigned_worker_id])


class IssueProgressImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_path = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    issue = db.relationship('Issue', foreign_keys=[issue_id])
    worker = db.relationship('User', foreign_keys=[worker_id])


class CoinTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    coins_delta = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    ref_type = db.Column(db.String(50))
    ref_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('User', foreign_keys=[user_id])


class FastagRedemption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vehicle_number = db.Column(db.String(50), nullable=False)
    amount_rupees = db.Column(db.Integer, nullable=False)
    coins_spent = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDING')
    transaction_ref = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    user = db.relationship('User', foreign_keys=[user_id])

class ChatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
