from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.services.db_service import DBService
import uuid

auth_bp = Blueprint('auth', __name__)

from models import db, User, Patient, Doctor, Department
from app import mongo
from config import Config
from datetime import datetime

DB_BACKEND = Config.DB_BACKEND

# Authentication Routes

@auth_bp.route('/login')
def login():
    return render_template('login.html')


@auth_bp.route('/login/patient', methods=['POST'])
def login_patient():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return render_template('login.html', error='Email and password required'), 400
    
    if DB_BACKEND == 'sqlite':
        user = User.query.filter_by(email=email, role='patient').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = 'patient'
            return redirect(url_for('patient.dashboard'))
    else:
        user = mongo.db.users.find_one({'email': email, 'role': 'patient'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'patient'
            return redirect(url_for('patient.dashboard'))
    
    return render_template('login.html', error='Invalid email or password'), 401


@auth_bp.route('/login/doctor', methods=['POST'])
def login_doctor():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return render_template('login.html', error='Email and password required'), 400
    
    if DB_BACKEND == 'sqlite':
        user = User.query.filter_by(email=email, role='doctor').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = 'doctor'
            return redirect(url_for('doctor.dashboard'))
    else:
        user = mongo.db.users.find_one({'email': email, 'role': 'doctor'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'doctor'
            return redirect(url_for('doctor.dashboard'))
    
    return render_template('login.html', error='Invalid email or password'), 401


@auth_bp.route('/signup/patient', methods=['GET', 'POST'])
def signup_patient():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([name, email, phone, password, confirm_password]):
            return render_template('signup_patient.html', error='All fields required'), 400
        
        if password != confirm_password:
            return render_template('signup_patient.html', error='Passwords do not match'), 400
        
        if DB_BACKEND == 'sqlite':
            if User.query.filter_by(email=email).first():
                return render_template('signup_patient.html', error='Email already registered'), 400
            if Patient.query.filter_by(phone=phone).first():
                return render_template('signup_patient.html', error='Phone number already registered'), 400
            
            user = User(email=email, role='patient')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            patient = Patient(user_id=user.id, name=name, phone=phone, email=email)
            db.session.add(patient)
            db.session.commit()
            
            session['user_id'] = user.id
        else:
            if mongo.db.users.find_one({'email': email}):
                return render_template('signup_patient.html', error='Email already registered'), 400
            if mongo.db.patients.find_one({'phone': phone}):
                return render_template('signup_patient.html', error='Phone number already registered'), 400
            
            res = mongo.db.users.insert_one({
                'email': email,
                'password_hash': generate_password_hash(password),
                'role': 'patient',
                'created_at': datetime.utcnow()
            })
            user_id = str(res.inserted_id)
            
            mongo.db.patients.insert_one({
                'user_id': user_id,
                'name': name,
                'phone': phone,
                'email': email
            })
            
            session['user_id'] = user_id
            
        session['role'] = 'patient'
        return redirect(url_for('patient.dashboard'))
    
    return render_template('signup_patient.html')


@auth_bp.route('/signup/doctor', methods=['GET', 'POST'])
def signup_doctor():
    if DB_BACKEND == 'sqlite':
        departments = Department.query.all()
    else:
        departments = list(mongo.db.departments.find({}))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        department_id = request.form.get('department_id')
        daily_slot_limit = request.form.get('daily_slot_limit', 10)
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([name, email, department_id, password, confirm_password]):
            return render_template('signup_doctor.html', error='All fields required', departments=departments), 400
        
        if password != confirm_password:
            return render_template('signup_doctor.html', error='Passwords do not match', departments=departments), 400
        
        if DB_BACKEND == 'sqlite':
            if User.query.filter_by(email=email).first():
                return render_template('signup_doctor.html', error='Email already registered', departments=departments), 400
            
            # Create user and doctor
            user = User(email=email, role='doctor')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            doctor = Doctor(user_id=user.id, name=name, department_id=int(department_id), daily_slot_limit=int(daily_slot_limit))
            db.session.add(doctor)
            db.session.commit()
            
            session['user_id'] = user.id
        else:
            if mongo.db.users.find_one({'email': email}):
                return render_template('signup_doctor.html', error='Email already registered', departments=departments), 400
            
            res = mongo.db.users.insert_one({
                'email': email,
                'password_hash': generate_password_hash(password),
                'role': 'doctor',
                'created_at': datetime.utcnow()
            })
            user_id = str(res.inserted_id)
            
            cur = mongo.db.doctors.find_one(sort=[('id', -1)])
            nid = (cur['id'] if cur else 0) + 1
            
            mongo.db.doctors.insert_one({
                'id': nid,
                'user_id': user_id,
                'name': name,
                'department_id': int(department_id),
                'daily_slot_limit': int(daily_slot_limit)
            })
            session['user_id'] = user_id
            
        session['role'] = 'doctor'
        return redirect(url_for('doctor.dashboard'))
    
    return render_template('signup_doctor.html', departments=departments)




@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


