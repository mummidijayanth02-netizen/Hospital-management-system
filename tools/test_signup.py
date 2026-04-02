from app import app

with app.test_client() as c:
    resp = c.post('/signup/patient', data={
        'name': 'TestUser3',
        'email': 'testuser3@example.com',
        'phone': '999',
        'password': 'pass',
        'confirm_password': 'pass'
    })
    print('status', resp.status_code)
    print(resp.get_data(as_text=True))
