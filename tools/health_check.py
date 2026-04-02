import urllib.request, json, sys

def check():
    paths=['/','/book','/admin']
    for p in paths:
        try:
            resp=urllib.request.urlopen('http://127.0.0.1:5000'+p, timeout=5)
            print(p, resp.getcode())
        except Exception as e:
            print(p, 'ERROR', repr(e))
    # test recommend
    try:
        req=urllib.request.Request('http://127.0.0.1:5000/api/recommend', data=json.dumps({'symptoms':[1]}).encode('utf-8'), headers={'Content-Type':'application/json'})
        r=urllib.request.urlopen(req, timeout=5)
        body=r.read(2000).decode('utf-8')
        print('/api/recommend', r.getcode(), body[:400])
    except Exception as e:
        print('/api/recommend', 'ERROR', repr(e))
    # book a test appointment
    try:
        req=urllib.request.Request('http://127.0.0.1:5000/api/book', data=json.dumps({'name':'Test User','phone':'9999999999','email':'t@example.com','doctor_id':1,'date':'2026-03-01'}).encode('utf-8'), headers={'Content-Type':'application/json'})
        r=urllib.request.urlopen(req, timeout=5)
        print('/api/book', r.getcode(), r.read(400).decode())
    except Exception as e:
        print('/api/book', 'ERROR', repr(e))
    # list appointments
    try:
        resp=urllib.request.urlopen('http://127.0.0.1:5000/api/appointments', timeout=5)
        data=resp.read(2000).decode('utf-8')
        print('/api/appointments', resp.getcode(), data[:800])
    except Exception as e:
        print('/api/appointments', 'ERROR', repr(e))

if __name__ == '__main__':
    check()
