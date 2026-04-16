from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.services.db_service import DBService
import uuid

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        backend = current_app.config['DB_BACKEND']
        user = None
        
        if backend == 'sqlite':
            from models import User
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['role'] = user.role
                return redirect(url_for(f'{user.role}.dashboard'))
        else:
            from app import mongo
            user = mongo.db.users.find_one({'email': email})
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['_id']
                session['role'] = user['role']
                return redirect(url_for(f'{user["role"]}.dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET'])
def signup_choice():
    return render_template('signup_choice.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

# More registration routes (Doctor/Patient) would go here or in sub-blueprints...
