from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env if present
load_dotenv()

# Backend selection: 'mongo' or 'sqlite'. Default is 'mongo'.
DB_BACKEND = os.environ.get('DB_BACKEND', os.environ.get('DATABASE', 'mongo')).lower()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

if DB_BACKEND == 'sqlite':
    # SQLAlchemy setup (local SQLite)
    from models import db, Patient, Department, Symptom, Doctor, Appointment, department_symptoms, User
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///hospital.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    from sqlite_init import init_db as init_sqlite_db
    mongo = None

    # perform initialization immediately so it runs under flask run as well
    with app.app_context():
        try:
            init_sqlite_db()
        except Exception as e:
            print('Warning: SQLite DB initialization failed during import:', e)
else:
    # MongoDB setup
    from flask_pymongo import PyMongo
    from bson.objectid import ObjectId
    import certifi
    
    app.config['MONGO_URI'] = os.environ.get('MONGODB_URI') or 'mongodb+srv://jayanth:REPLACE_PASSWORD@cluster0.qmmn2m9.mongodb.net/hospital?retryWrites=true&w=majority'
    mongo = PyMongo(app, tlsCAFile=certifi.where())

    # initialize mongo too
    try:
        from db_init import init_db
        init_db(mongo)
    except Exception as e:
        print('Warning: MongoDB initialization failed during import:', e)


# Seed initialization will be run when starting the app directly.

# Context processor for current user
@app.context_processor
def inject_user():
    user = None
    patient = None
    doctor = None
    if 'user_id' in session:
        if DB_BACKEND == 'sqlite':
            user = User.query.get(session.get('user_id'))
            if session.get('role') == 'patient' and user:
                patient = Patient.query.filter_by(user_id=user.id).first()
            elif session.get('role') == 'doctor' and user:
                doctor = Doctor.query.filter_by(user_id=user.id).first()
        else:
            try:
                from bson.objectid import ObjectId
                user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
                if session.get('role') == 'patient' and user:
                    patient = mongo.db.patients.find_one({'user_id': str(user['_id'])})
                elif session.get('role') == 'doctor' and user:
                    doctor = mongo.db.doctors.find_one({'user_id': str(user['_id'])})
                    if doctor:
                        doctor['department'] = mongo.db.departments.find_one({'id': doctor.get('department_id')})
            except Exception:
                pass
    return {'current_user': user, 'patient': patient, 'doctor': doctor}


# Authentication Routes

@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login/patient', methods=['POST'])
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
            return redirect(url_for('patient_dashboard'))
    else:
        user = mongo.db.users.find_one({'email': email, 'role': 'patient'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'patient'
            return redirect(url_for('patient_dashboard'))
    
    return render_template('login.html', error='Invalid email or password'), 401


@app.route('/login/doctor', methods=['POST'])
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
            return redirect(url_for('doctor_dashboard'))
    else:
        user = mongo.db.users.find_one({'email': email, 'role': 'doctor'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'doctor'
            return redirect(url_for('doctor_dashboard'))
    
    return render_template('login.html', error='Invalid email or password'), 401


@app.route('/signup/patient', methods=['GET', 'POST'])
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
        return redirect(url_for('patient_dashboard'))
    
    return render_template('signup_patient.html')


@app.route('/signup/doctor', methods=['GET', 'POST'])
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
        return redirect(url_for('doctor_dashboard'))
    
    return render_template('signup_doctor.html', departments=departments)


@app.route('/patient/dashboard')
def patient_dashboard():
    if 'user_id' not in session or session.get('role') != 'patient':
        return redirect(url_for('login'))
    
    if DB_BACKEND == 'sqlite':
        user = User.query.get(session.get('user_id'))
        patient = Patient.query.filter_by(user_id=user.id).first()
        if not patient:
            return redirect(url_for('login'))
        appointments = Appointment.query.filter_by(patient_id=patient.id).all()
    else:
        from bson.objectid import ObjectId
        user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
        patient = mongo.db.patients.find_one({'user_id': str(user['_id'])}) if user else None
        if not patient:
            return redirect(url_for('login'))
        
        appts_cursor = mongo.db.appointments.find({'patient_id': str(patient['_id'])})
        appointments = []
        for a in appts_cursor:
            a['id'] = str(a.get('_id'))
            doc = mongo.db.doctors.find_one({'id': a['doctor_id']})
            if doc:
                dept = mongo.db.departments.find_one({'id': doc.get('department_id')})
                doc['department'] = dept
            a['doctor'] = doc
            appointments.append(a)
            
    return render_template('patient_dashboard.html', patient=patient, appointments=appointments)


@app.route('/doctor/dashboard')
def doctor_dashboard():
    if 'user_id' not in session or session.get('role') != 'doctor':
        return redirect(url_for('login'))
    
    if DB_BACKEND == 'sqlite':
        user = User.query.get(session.get('user_id'))
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if not doctor:
            return redirect(url_for('login'))
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    else:
        from bson.objectid import ObjectId
        user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
        doctor = mongo.db.doctors.find_one({'user_id': str(user['_id'])}) if user else None
        if not doctor:
            return redirect(url_for('login'))
            
        dept = mongo.db.departments.find_one({'id': doctor.get('department_id')})
        if doctor:
            doctor['department'] = dept
        
        appts_cursor = mongo.db.appointments.find({'doctor_id': doctor['id']})
        appointments = []
        for a in appts_cursor:
            a['id'] = str(a.get('_id'))
            pat = mongo.db.patients.find_one({'_id': ObjectId(a['patient_id'])})
            if pat:
                a['patient'] = pat
            appointments.append(a)
            
    return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


def index():
    return render_template('index.html')

# simple diagnostic route to show which backend is active (useful for
# debugging environment variable issues)
@app.route('/_debug_backend')
def debug_backend():
    return jsonify({'DB_BACKEND': DB_BACKEND})


@app.route('/book')
def book_page():
    if DB_BACKEND == 'sqlite':
        symptoms = Symptom.query.all()
    else:
        symptoms = list(mongo.db.symptoms.find({}))
    return render_template('book.html', symptoms=symptoms)


@app.route('/admin')
def admin_page():
    if DB_BACKEND == 'sqlite':
        departments = Department.query.all()
        doctors = Doctor.query.all()
        symptoms = Symptom.query.all()
    else:
        departments = list(mongo.db.departments.find({}))
        doctors = list(mongo.db.doctors.find({}))
        symptoms = list(mongo.db.symptoms.find({}))
    return render_template('admin.html', departments=departments, doctors=doctors, symptoms=symptoms)


@app.route('/api/recommend', methods=['POST'])
def recommend():
    data = request.json or {}
    symptom_ids = data.get('symptoms', [])
    date_str = data.get('date')
    if DB_BACKEND == 'sqlite':
        # Score departments by symptom mapping via association table
        dept_scores = {}
        for sid in symptom_ids:
            deps = Department.query.join(department_symptoms).filter(department_symptoms.c.symptom_id == sid).all()
            for d in deps:
                dept_scores[d.id] = dept_scores.get(d.id, 0) + 1

        dept_list = []
        if dept_scores:
            for dept_id, score in sorted(dept_scores.items(), key=lambda x: -x[1]):
                d = Department.query.get(dept_id)
                if d:
                    dept_list.append({'id': d.id, 'name': d.name, 'score': score})
        else:
            for d in Department.query.all():
                dept_list.append({'id': d.id, 'name': d.name, 'score': 0})

        recommended = []
        if dept_list:
            top_dept_id = dept_list[0]['id']
            docs = Doctor.query.filter_by(department_id=top_dept_id).all()
            for doc in docs:
                available = True
                if date_str:
                    try:
                        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        count = Appointment.query.filter_by(doctor_id=doc.id, date=str(appt_date)).count()
                        if count >= doc.daily_slot_limit:
                            available = False
                    except Exception:
                        pass
                recommended.append({'id': doc.id, 'name': doc.name, 'available': available, 'daily_slot_limit': doc.daily_slot_limit})

        return jsonify({'departments': dept_list, 'doctors': recommended})
    else:
        # Mongo path (existing)
        dept_scores = {}
        for sid in symptom_ids:
            matches = mongo.db.departments.find({'symptom_ids': sid})
            for dept in matches:
                did = dept.get('id')
                dept_scores[did] = dept_scores.get(did, 0) + 1

        dept_list = []
        if dept_scores:
            for dept_id, score in sorted(dept_scores.items(), key=lambda x: -x[1]):
                dept = mongo.db.departments.find_one({'id': dept_id})
                if dept:
                    dept_list.append({'id': dept['id'], 'name': dept['name'], 'score': score})
        else:
            for d in mongo.db.departments.find():
                dept_list.append({'id': d['id'], 'name': d['name'], 'score': 0})

        recommended = []
        if dept_list:
            top_dept_id = dept_list[0]['id']
            for doc in mongo.db.doctors.find({'department_id': top_dept_id}):
                available = True
                if date_str:
                    try:
                        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        count = mongo.db.appointments.count_documents({'doctor_id': doc['id'], 'date': str(appt_date)})
                        if count >= doc.get('daily_slot_limit', 0):
                            available = False
                    except Exception:
                        pass
                recommended.append({'id': doc['id'], 'name': doc['name'], 'available': available, 'daily_slot_limit': doc.get('daily_slot_limit', 0)})

        return jsonify({'departments': dept_list, 'doctors': recommended})


@app.route('/api/book', methods=['POST'])
def book():
    data = request.json or {}
    patient_name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    doctor_id = data.get('doctor_id')
    date_str = data.get('date')

    if not (patient_name and doctor_id and date_str):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    if DB_BACKEND == 'sqlite':
        # find or create patient
        patient = Patient.query.filter_by(phone=phone).first()
        if not patient:
            patient = Patient(name=patient_name, phone=phone, email=email)
            db.session.add(patient)
            db.session.commit()

        # check doctor
        doctor = Doctor.query.get(int(doctor_id))
        if not doctor:
            return jsonify({'success': False, 'message': 'Doctor not found'}), 404

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid date format; use YYYY-MM-DD'}), 400

        count = Appointment.query.filter_by(doctor_id=doctor.id, date=str(appt_date)).count()
        if count >= doctor.daily_slot_limit:
            return jsonify({'success': False, 'message': 'No slots available for selected doctor on this date'}), 409

        appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, date=str(appt_date), time=data.get('time', ''), status='scheduled')
        db.session.add(appt)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Appointment booked', 'appointment_id': appt.id})
    else:
        # mongo path
        patient = mongo.db.patients.find_one({'phone': phone})
        if not patient:
            res = mongo.db.patients.insert_one({'name': patient_name, 'phone': phone, 'email': email})
            patient_id = str(res.inserted_id)
        else:
            patient_id = str(patient['_id'])

        doctor = mongo.db.doctors.find_one({'id': int(doctor_id)})
        if not doctor:
            return jsonify({'success': False, 'message': 'Doctor not found'}), 404

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid date format; use YYYY-MM-DD'}), 400

        count = mongo.db.appointments.count_documents({'doctor_id': doctor['id'], 'date': str(appt_date)})
        if count >= doctor.get('daily_slot_limit', 0):
            return jsonify({'success': False, 'message': 'No slots available for selected doctor on this date'}), 409

        appt = {
            'patient_id': patient_id,
            'doctor_id': doctor['id'],
            'date': str(appt_date),
            'time': data.get('time', ''),
            'status': 'scheduled',
            'created_at': datetime.utcnow()
        }

        res = mongo.db.appointments.insert_one(appt)
        return jsonify({'success': True, 'message': 'Appointment booked', 'appointment_id': str(res.inserted_id)})


# Admin CRUD APIs


@app.route('/api/admin/departments', methods=['GET', 'POST'])
def admin_departments():
    if DB_BACKEND == 'sqlite':
        if request.method == 'GET':
            depts = Department.query.all()
            return jsonify([{'id': d.id, 'name': d.name, 'symptom_ids': [s.id for s in d.symptoms]} for d in depts])
        data = request.json or {}
        name = data.get('name')
        symptom_ids = data.get('symptom_ids', [])
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        dept = Department(name=name)
        db.session.add(dept)
        db.session.commit()
        # attach symptoms
        for sid in symptom_ids:
            s = Symptom.query.get(sid)
            if s:
                dept.symptoms.append(s)
        db.session.commit()
        return jsonify({'success': True, 'department': {'id': dept.id, 'name': dept.name}})
    else:
        if request.method == 'GET':
            depts = list(mongo.db.departments.find())
            return jsonify(depts)
        data = request.json or {}
        name = data.get('name')
        symptom_ids = data.get('symptom_ids', [])
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        # assign numeric id
        cur = mongo.db.departments.find_one(sort=[('id', -1)])
        nid = (cur['id'] if cur else 0) + 1
        doc = {'id': nid, 'name': name, 'symptom_ids': symptom_ids}
        mongo.db.departments.insert_one(doc)
        return jsonify({'success': True, 'department': doc})


@app.route('/api/admin/departments/<int:dept_id>', methods=['PUT', 'DELETE'])
def admin_department_modify(dept_id):
    if DB_BACKEND == 'sqlite':
        if request.method == 'DELETE':
            Department.query.filter_by(id=dept_id).delete()
            db.session.commit()
            return jsonify({'success': True})
        data = request.json or {}
        dept = Department.query.get(dept_id)
        if not dept:
            return jsonify({'success': False}), 404
        dept.name = data.get('name')
        dept.symptoms = []
        for sid in data.get('symptom_ids', []):
            s = Symptom.query.get(sid)
            if s:
                dept.symptoms.append(s)
        db.session.commit()
        return jsonify({'success': True})
    else:
        if request.method == 'DELETE':
            mongo.db.departments.delete_one({'id': dept_id})
            return jsonify({'success': True})
        data = request.json or {}
        mongo.db.departments.update_one({'id': dept_id}, {'$set': {'name': data.get('name'), 'symptom_ids': data.get('symptom_ids', [])}})
        return jsonify({'success': True})


@app.route('/api/admin/symptoms', methods=['GET', 'POST'])
def admin_symptoms():
    if DB_BACKEND == 'sqlite':
        if request.method == 'GET':
            return jsonify([{'id': s.id, 'name': s.name} for s in Symptom.query.all()])
        data = request.json or {}
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        s = Symptom(name=name)
        db.session.add(s)
        db.session.commit()
        return jsonify({'success': True, 'symptom': {'id': s.id, 'name': s.name}})
    else:
        if request.method == 'GET':
            return jsonify(list(mongo.db.symptoms.find()))
        data = request.json or {}
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        cur = mongo.db.symptoms.find_one(sort=[('id', -1)])
        nid = (cur['id'] if cur else 0) + 1
        doc = {'id': nid, 'name': name}
        mongo.db.symptoms.insert_one(doc)
        return jsonify({'success': True, 'symptom': doc})


@app.route('/api/admin/symptoms/<int:sym_id>', methods=['PUT', 'DELETE'])
def admin_symptom_modify(sym_id):
    if DB_BACKEND == 'sqlite':
        if request.method == 'DELETE':
            Symptom.query.filter_by(id=sym_id).delete()
            db.session.commit()
            # remove associations
            return jsonify({'success': True})
        data = request.json or {}
        s = Symptom.query.get(sym_id)
        if not s:
            return jsonify({'success': False}), 404
        s.name = data.get('name')
        db.session.commit()
        return jsonify({'success': True})
    else:
        if request.method == 'DELETE':
            mongo.db.symptoms.delete_one({'id': sym_id})
            # Also remove from departments
            mongo.db.departments.update_many({}, {'$pull': {'symptom_ids': sym_id}})
            return jsonify({'success': True})
        data = request.json or {}
        mongo.db.symptoms.update_one({'id': sym_id}, {'$set': {'name': data.get('name')}})
        return jsonify({'success': True})


@app.route('/api/admin/doctors', methods=['GET', 'POST'])
def admin_doctors():
    if DB_BACKEND == 'sqlite':
        if request.method == 'GET':
            return jsonify([{'id': d.id, 'name': d.name, 'department_id': d.department_id, 'daily_slot_limit': d.daily_slot_limit} for d in Doctor.query.all()])
        data = request.json or {}
        name = data.get('name')
        department_id = data.get('department_id')
        daily_slot_limit = int(data.get('daily_slot_limit', 0))
        if not (name and department_id):
            return jsonify({'success': False, 'message': 'Name and department required'}), 400
        doc = Doctor(name=name, department_id=int(department_id), daily_slot_limit=daily_slot_limit)
        db.session.add(doc)
        db.session.commit()
        return jsonify({'success': True, 'doctor': {'id': doc.id, 'name': doc.name}})
    else:
        if request.method == 'GET':
            return jsonify(list(mongo.db.doctors.find()))
        data = request.json or {}
        name = data.get('name')
        department_id = data.get('department_id')
        daily_slot_limit = int(data.get('daily_slot_limit', 0))
        if not (name and department_id):
            return jsonify({'success': False, 'message': 'Name and department required'}), 400
        cur = mongo.db.doctors.find_one(sort=[('id', -1)])
        nid = (cur['id'] if cur else 0) + 1
        doc = {'id': nid, 'name': name, 'department_id': int(department_id), 'daily_slot_limit': daily_slot_limit}
        mongo.db.doctors.insert_one(doc)
        return jsonify({'success': True, 'doctor': doc})


@app.route('/api/admin/doctors/<int:doc_id>', methods=['PUT', 'DELETE'])
def admin_doctor_modify(doc_id):
    if DB_BACKEND == 'sqlite':
        if request.method == 'DELETE':
            Doctor.query.filter_by(id=doc_id).delete()
            db.session.commit()
            return jsonify({'success': True})
        data = request.json or {}
        doc = Doctor.query.get(doc_id)
        if not doc:
            return jsonify({'success': False}), 404
        doc.name = data.get('name')
        doc.department_id = int(data.get('department_id'))
        doc.daily_slot_limit = int(data.get('daily_slot_limit', 0))
        db.session.commit()
        return jsonify({'success': True})
    else:
        if request.method == 'DELETE':
            mongo.db.doctors.delete_one({'id': doc_id})
            return jsonify({'success': True})
        data = request.json or {}
        mongo.db.doctors.update_one({'id': doc_id}, {'$set': {'name': data.get('name'), 'department_id': int(data.get('department_id')), 'daily_slot_limit': int(data.get('daily_slot_limit', 0))}})
        return jsonify({'success': True})


# Appointments listing and export
@app.route('/api/appointments', methods=['GET'])
def list_appointments():
    q = {}
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')
    if doctor_id:
        q['doctor_id'] = int(doctor_id)
    if date:
        q['date'] = date
    if DB_BACKEND == 'sqlite':
        qsql = Appointment.query
        if doctor_id:
            qsql = qsql.filter_by(doctor_id=int(doctor_id))
        if date:
            qsql = qsql.filter_by(date=date)
        appts = qsql.order_by(Appointment.id.desc()).all()
        out = []
        for a in appts:
            pat = Patient.query.get(a.patient_id)
            doc = Doctor.query.get(a.doctor_id)
            out.append({'id': a.id, 'patient': pat.name if pat else a.patient_id, 'doctor': doc.name if doc else a.doctor_id, 'date': a.date, 'time': a.time, 'status': a.status})
        return jsonify(out)
    else:
        appts = list(mongo.db.appointments.find(q).sort('created_at', -1))
        out = []
        for a in appts:
            pat = mongo.db.patients.find_one({'_id': ObjectId(a['patient_id'])})
            doc = mongo.db.doctors.find_one({'id': a['doctor_id']})
            out.append({'id': str(a.get('_id')), 'patient': pat.get('name') if pat else a.get('patient_id'), 'doctor': doc.get('name') if doc else a.get('doctor_id'), 'date': a.get('date'), 'time': a.get('time'), 'status': a.get('status')})
        return jsonify(out)


@app.route('/api/appointments/export', methods=['GET'])
def export_appointments():
    import csv
    from io import StringIO
    q = {}
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')
    if doctor_id:
        q['doctor_id'] = int(doctor_id)
    if date:
        q['date'] = date
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['AppointmentID', 'Patient', 'Doctor', 'Date', 'Time', 'Status'])
    if DB_BACKEND == 'sqlite':
        qsql = Appointment.query
        if doctor_id:
            qsql = qsql.filter_by(doctor_id=int(doctor_id))
        if date:
            qsql = qsql.filter_by(date=date)
        appts = qsql.order_by(Appointment.id.desc()).all()
        for a in appts:
            pat = Patient.query.get(a.patient_id)
            doc = Doctor.query.get(a.doctor_id)
            writer.writerow([a.id, pat.name if pat else a.patient_id, doc.name if doc else a.doctor_id, a.date, a.time, a.status])
    else:
        appts = list(mongo.db.appointments.find(q).sort('created_at', -1))
        for a in appts:
            pat = mongo.db.patients.find_one({'_id': ObjectId(a['patient_id'])})
            doc = mongo.db.doctors.find_one({'id': a['doctor_id']})
            writer.writerow([str(a.get('_id')), pat.get('name') if pat else a.get('patient_id'), doc.get('name') if doc else a.get('doctor_id'), a.get('date'), a.get('time'), a.get('status')])
    csv_data = si.getvalue()
    from flask import Response
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=appointments.csv'})


if __name__ == '__main__':
    # Initialize/seed DB before starting server
    if DB_BACKEND == 'sqlite':
        try:
            with app.app_context():
                init_sqlite_db()
        except Exception as e:
            print('Warning: SQLite DB initialization failed:', e)
    else:
        try:
            from db_init import init_db
            init_db(mongo)
        except Exception as e:
            print('Warning: MongoDB initialization failed:', e)

    # In development we used to run with debug=True which enables the
    # reloader.  Unfortunately the reloader spawns a child process which
    # doesn't inherit our custom DB_BACKEND environment variable, causing
    # the child to default back to MongoDB and then hang when it cannot
    # reach Atlas.  To keep behaviour predictable we disable the reloader
    # and only turn on debugging if FLASK_DEBUG is explicitly set.
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, use_reloader=False)
