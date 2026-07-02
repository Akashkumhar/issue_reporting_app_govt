from app import create_app
from models import User
from db import db, bcrypt

app = create_app()

with app.app_context():
    db.create_all()

    # Create admin user
    if not User.query.filter_by(username='admin').first():
        admin_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(username='admin', password_hash=admin_hash, role='admin')
        db.session.add(admin)

    # Create user
    if not User.query.filter_by(username='user').first():
        user_hash = bcrypt.generate_password_hash('user123').decode('utf-8')
        user = User(username='user', password_hash=user_hash, role='user')
        db.session.add(user)

    # Create worker
    if not User.query.filter_by(username='worker').first():
        worker_hash = bcrypt.generate_password_hash('worker123').decode('utf-8')
        worker = User(username='worker', password_hash=worker_hash, role='worker')
        db.session.add(worker)

    db.session.commit()
    print("Users seeded successfully!")
