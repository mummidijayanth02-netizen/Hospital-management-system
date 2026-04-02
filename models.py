from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Association table: department <-> symptom
department_symptoms = db.Table('department_symptoms',
    db.Column('department_id', db.Integer, db.ForeignKey('department.id'), primary_key=True),
    db.Column('symptom_id', db.Integer, db.ForeignKey('symptom.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False)  # 'patient' or 'doctor'
    created_at = db.Column(db.DateTime, default=db.func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    name = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(32), unique=True)
    email = db.Column(db.String(128))
    user = db.relationship('User', uselist=False)


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    symptoms = db.relationship('Symptom', secondary=department_symptoms, back_populates='departments')


class Symptom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    departments = db.relationship('Department', secondary=department_symptoms, back_populates='symptoms')


class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    name = db.Column(db.String(128), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    department = db.relationship('Department')
    daily_slot_limit = db.Column(db.Integer, default=10)
    user = db.relationship('User', uselist=False)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'))
    date = db.Column(db.String(20), nullable=False)  # YYYY-MM-DD
    time = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(32), default='scheduled')

    patient = db.relationship('Patient')
    doctor = db.relationship('Doctor')
