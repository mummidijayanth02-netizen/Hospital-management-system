def init_db(mongo):
    # Seed MongoDB collections if empty. Uses numeric 'id' fields for simple frontend integration.
    if mongo.db.departments.count_documents({}) == 0:
        # Departments with numeric id and linked symptom_ids
        departments = [
            {'id': 1, 'name': 'General Medicine', 'symptom_ids': [1,2,3]},
            {'id': 2, 'name': 'ENT', 'symptom_ids': [4]},
            {'id': 3, 'name': 'Orthopedics', 'symptom_ids': [6]},
            {'id': 4, 'name': 'Dermatology', 'symptom_ids': [5]},
            {'id': 5, 'name': 'Pediatrics', 'symptom_ids': [1,2]}
        ]
        mongo.db.departments.insert_many(departments)

        # Symptoms with numeric ids
        symptoms = [
            {'id': 1, 'name': 'cough'},
            {'id': 2, 'name': 'fever'},
            {'id': 3, 'name': 'headache'},
            {'id': 4, 'name': 'ear pain'},
            {'id': 5, 'name': 'skin rash'},
            {'id': 6, 'name': 'broken bone'}
        ]
        mongo.db.symptoms.insert_many(symptoms)

        # Doctors with numeric ids mapped to department ids
        doctors = [
            {'id': 1, 'name': 'Dr. Asha', 'department_id': 1, 'daily_slot_limit': 8},
            {'id': 2, 'name': 'Dr. Rao', 'department_id': 2, 'daily_slot_limit': 5},
            {'id': 3, 'name': 'Dr. Kumar', 'department_id': 3, 'daily_slot_limit': 6},
            {'id': 4, 'name': 'Dr. Meera', 'department_id': 4, 'daily_slot_limit': 4},
            {'id': 5, 'name': 'Dr. Priya', 'department_id': 5, 'daily_slot_limit': 7}
        ]
        mongo.db.doctors.insert_many(doctors)

        # ensure indexes for faster lookups
        mongo.db.departments.create_index('id', unique=True)
        mongo.db.symptoms.create_index('id', unique=True)
        mongo.db.doctors.create_index('id', unique=True)
        mongo.db.patients.create_index('phone', unique=True)
        mongo.db.appointments.create_index([('doctor_id', 1), ('date', 1)])
        mongo.db.prescriptions.create_index('appointment_id')
        mongo.db.notifications.create_index([('user_id', 1), ('created_at', -1)])
