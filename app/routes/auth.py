from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from app.services.db_service import DBService
import uuid

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET'])
def login():
    return render_template('login.html')


@auth_bp.route('/login/patient', methods=['POST'])
def login_patient():
    email = request.form.get('email')
    password = request.form.get('password')
    backend = current_app.config['DB_BACKEND']

    if backend == 'sqlite':
        from models import User
        user = User.query.filter_by(email=email, role='patient').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = 'patient'
            return redirect(url_for('patient.dashboard'))
    else:
        from app import mongo
        user = mongo.db.users.find_one({'email': email, 'role': 'patient'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'patient'
            return redirect(url_for('patient.dashboard'))

    return render_template('login.html', error='Invalid credentials')


@auth_bp.route('/login/doctor', methods=['POST'])
def login_doctor():
    email = request.form.get('email')
    password = request.form.get('password')
    backend = current_app.config['DB_BACKEND']

    if backend == 'sqlite':
        from models import User
        user = User.query.filter_by(email=email, role='doctor').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = 'doctor'
            return redirect(url_for('doctor.dashboard'))
    else:
        from app import mongo
        user = mongo.db.users.find_one({'email': email, 'role': 'doctor'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'doctor'
            return redirect(url_for('doctor.dashboard'))

    return render_template('login.html', error='Invalid credentials')


@auth_bp.route('/signup/patient', methods=['GET', 'POST'])
def signup_patient():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if password != confirm:
            return render_template('signup_patient.html', error='Passwords do not match')

        backend = current_app.config['DB_BACKEND']

        if backend == 'sqlite':
            from models import User, Patient
            from app import db
            if User.query.filter_by(email=email).first():
                return render_template('signup_patient.html', error='Email already registered')
            user = User(email=email, role='patient')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            patient = Patient(user_id=user.id, name=name, phone=phone, email=email)
            db.session.add(patient)
            db.session.commit()
            session['user_id'] = user.id
            session['role'] = 'patient'
        else:
            from app import mongo
            if mongo.db.users.find_one({'email': email}):
                return render_template('signup_patient.html', error='Email already registered')
            user_id = str(uuid.uuid4())
            mongo.db.users.insert_one({
                '_id': user_id,
                'email': email,
                'password_hash': generate_password_hash(password),
                'role': 'patient'
            })
            mongo.db.patients.insert_one({
                '_id': str(uuid.uuid4()),
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
    backend = current_app.config['DB_BACKEND']

    # Load departments for the form dropdown
    departments = []
    if backend == 'sqlite':
        from models import Department
        departments = Department.query.all()
    else:
        from app import mongo
        departments = list(mongo.db.departments.find())

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        department_id = request.form.get('department_id')
        daily_slot_limit = request.form.get('daily_slot_limit', 10)
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if password != confirm:
            return render_template('signup_doctor.html', departments=departments, error='Passwords do not match')

        if backend == 'sqlite':
            from models import User, Doctor
            from app import db
            if User.query.filter_by(email=email).first():
                return render_template('signup_doctor.html', departments=departments, error='Email already registered')
            user = User(email=email, role='doctor')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            doctor = Doctor(user_id=user.id, name=name, department_id=int(department_id), daily_slot_limit=int(daily_slot_limit))
            db.session.add(doctor)
            db.session.commit()
            session['user_id'] = user.id
            session['role'] = 'doctor'
        else:
            from app import mongo
            if mongo.db.users.find_one({'email': email}):
                return render_template('signup_doctor.html', departments=departments, error='Email already registered')
            user_id = str(uuid.uuid4())
            mongo.db.users.insert_one({
                '_id': user_id,
                'email': email,
                'password_hash': generate_password_hash(password),
                'role': 'doctor'
            })
            mongo.db.doctors.insert_one({
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
