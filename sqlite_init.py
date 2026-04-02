from models import db, Patient, Department, Symptom, Doctor, User
import sqlite3


def init_db():
    # create tables for all models
    db.create_all()
    # debug: print metadata tables
    print('metadata tables:', list(db.metadata.tables.keys()))

    # Seed only if empty
    if Department.query.count() == 0:
        gen = Department(name='General Medicine')
        ent = Department(name='ENT')
        ortho = Department(name='Orthopedics')
        derm = Department(name='Dermatology')
        ped = Department(name='Pediatrics')
        db.session.add_all([gen, ent, ortho, derm, ped])
        db.session.commit()

        # Symptoms
        s_cough = Symptom(name='cough')
        s_fever = Symptom(name='fever')
        s_headache = Symptom(name='headache')
        s_ear_pain = Symptom(name='ear pain')
        s_rash = Symptom(name='skin rash')
        s_broken = Symptom(name='broken bone')
        db.session.add_all([s_cough, s_fever, s_headache, s_ear_pain, s_rash, s_broken])
        db.session.commit()

        # Map symptoms to departments (rule-based mapping)
        gen.symptoms.extend([s_cough, s_fever, s_headache])
        ent.symptoms.append(s_ear_pain)
        derm.symptoms.append(s_rash)
        ortho.symptoms.append(s_broken)
        ped.symptoms.extend([s_fever, s_cough])
        db.session.commit()

        # Create doctor users and doctors
        # Doctor 1
        user1 = User(email='asha@hospital.com', role='doctor')
        user1.set_password('password123')
        db.session.add(user1)
        db.session.commit()
        d1 = Doctor(user_id=user1.id, name='Dr. Asha', department=gen, daily_slot_limit=8)
        
        # Doctor 2
        user2 = User(email='rao@hospital.com', role='doctor')
        user2.set_password('password123')
        db.session.add(user2)
        db.session.commit()
        d2 = Doctor(user_id=user2.id, name='Dr. Rao', department=ent, daily_slot_limit=5)
        
        # Doctor 3
        user3 = User(email='kumar@hospital.com', role='doctor')
        user3.set_password('password123')
        db.session.add(user3)
        db.session.commit()
        d3 = Doctor(user_id=user3.id, name='Dr. Kumar', department=ortho, daily_slot_limit=6)
        
        # Doctor 4
        user4 = User(email='meera@hospital.com', role='doctor')
        user4.set_password('password123')
        db.session.add(user4)
        db.session.commit()
        d4 = Doctor(user_id=user4.id, name='Dr. Meera', department=derm, daily_slot_limit=4)
        
        # Doctor 5
        user5 = User(email='priya@hospital.com', role='doctor')
        user5.set_password('password123')
        db.session.add(user5)
        db.session.commit()
        d5 = Doctor(user_id=user5.id, name='Dr. Priya', department=ped, daily_slot_limit=7)
        
        db.session.add_all([d1, d2, d3, d4, d5])
        db.session.commit()
