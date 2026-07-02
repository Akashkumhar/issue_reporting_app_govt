from flask import Flask, render_template, send_from_directory, redirect, url_for
from flask_login import LoginManager, login_required, current_user, logout_user
from dotenv import load_dotenv
import logging
import os
from sqlalchemy import inspect, text

from db import db, bcrypt, login_manager

def create_app():
    load_dotenv()  # Load environment variables from .env file

    # Configure logging to see errors in the console during development
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key_here'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['UPLOAD_FOLDER'] = 'uploads'

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'frontend_login'

    # Import models
    import models

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # Create database tables
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        if 'user' in inspector.get_table_names():
            user_columns = [col['name'] for col in inspector.get_columns('user')]
            if 'wallet_balance' not in user_columns:
                db.session.execute(text('ALTER TABLE user ADD COLUMN wallet_balance INTEGER NOT NULL DEFAULT 0'))
                db.session.commit()
            if 'reputation_score' not in user_columns:
                db.session.execute(text('ALTER TABLE user ADD COLUMN reputation_score INTEGER NOT NULL DEFAULT 0'))
                db.session.commit()
            if 'is_banned' not in user_columns:
                db.session.execute(text('ALTER TABLE user ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0'))
                db.session.commit()
        if 'issue' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('issue')]
            if 'progress' not in columns:
                db.session.execute(text('ALTER TABLE issue ADD COLUMN progress INTEGER NOT NULL DEFAULT 0'))
                db.session.commit()
            if 'created_at' not in columns:
                db.session.execute(text('ALTER TABLE issue ADD COLUMN created_at DATETIME'))
                db.session.commit()
                db.session.execute(text('UPDATE issue SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL'))
                db.session.commit()
            if 'image_hash' not in columns:
                db.session.execute(text('ALTER TABLE issue ADD COLUMN image_hash TEXT'))
                db.session.commit()

    # Import and register blueprints here
    import auth
    import issues
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(issues.issues_bp)

    frontend_dir = os.path.join(app.root_path, 'frontend')

    @app.route('/frontend')
    def frontend_index():
        return redirect(url_for('frontend_login'))

    @app.route('/frontend/login')
    def frontend_login():
        return send_from_directory(frontend_dir, 'login.html')

    @app.route('/frontend/logout')
    @login_required
    def frontend_logout():
        logout_user()
        return redirect(url_for('frontend_login'))

    @app.route('/frontend/static/<path:filename>')
    def frontend_static(filename):
        return send_from_directory(frontend_dir, filename)

    @app.route('/frontend/admin')
    @login_required
    def frontend_admin():
        if current_user.role != 'admin':
            return "Access denied", 403
        return send_from_directory(frontend_dir, 'admin.html')

    @app.route('/frontend/user')
    @login_required
    def frontend_user():
        if current_user.role != 'user':
            return "Access denied", 403
        return send_from_directory(frontend_dir, 'user.html')

    @app.route('/frontend/worker')
    @login_required
    def frontend_worker():
        if current_user.role != 'worker':
            return "Access denied", 403
        return send_from_directory(frontend_dir, 'worker.html')

    @app.route('/frontend/report')
    @login_required
    def frontend_report():
        if current_user.role != 'user':
            return "Access denied", 403
        return send_from_directory(frontend_dir, 'report.html')

    @app.route('/')
    @login_required
    def index():
        if current_user.role == 'user':
            return render_template('user_dashboard.html')
        elif current_user.role == 'admin':
            return render_template('admin_dashboard.html')
        elif current_user.role == 'worker':
            return render_template('worker_dashboard.html')
        return "Welcome to RoadSense"

    @app.route('/admin_dashboard')
    @login_required
    def admin_dashboard():
        if current_user.role != 'admin':
            return "Access denied", 403
        return render_template('admin_dashboard.html')

    @app.route('/user_dashboard')
    @login_required
    def user_dashboard():
        if current_user.role != 'user':
            return "Access denied", 403
        return render_template('user_dashboard.html')

    @app.route('/worker_dashboard')
    @login_required
    def worker_dashboard():
        if current_user.role != 'worker':
            return "Access denied", 403
        return render_template('worker_dashboard.html')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
