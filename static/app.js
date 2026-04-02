async function postJson(url, data) {
  const res = await fetch(url, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data)});
  return res.json();
}

document.addEventListener('DOMContentLoaded', () => {
  const recommendBtn = document.getElementById('recommendBtn');
  const recommendations = document.getElementById('recommendations');

  recommendBtn.addEventListener('click', async () => {
    const checked = Array.from(document.querySelectorAll('#symptomsList input[type=checkbox]:checked')).map(i=>parseInt(i.value));
    const date = document.getElementById('dateInput').value;
    const data = await postJson('/api/recommend', {symptoms: checked, date});

    // render
    recommendations.innerHTML = '';
    const deptCard = document.createElement('div');
    deptCard.className = 'card p-3';
    deptCard.innerHTML = `<h5>Recommended Departments</h5>` + data.departments.map(d=>`<div>${d.name} (${d.score})</div>`).join('');
    recommendations.appendChild(deptCard);

    const docCard = document.createElement('div');
    docCard.className = 'card p-3 mt-3';
    docCard.innerHTML = `<h5>Available Doctors (Top Dept)</h5>`;
    if (data.doctors.length===0) docCard.innerHTML += '<div>No doctors found</div>';
    else {
      const list = document.createElement('div');
      data.doctors.forEach(d=>{
        const el = document.createElement('div');
        el.innerHTML = `<div class="d-flex justify-content-between align-items-center py-1"><div>${d.name}</div><div>${d.available?'<span class="available">Available</span>':'<span class="unavailable">Full</span>'} <button class="btn btn-sm btn-success ms-2" data-doc="${d.id}" ${d.available? '':'disabled'}>Book</button></div></div>`;
        list.appendChild(el);
      });
      docCard.appendChild(list);
    }
    recommendations.appendChild(docCard);

    // attach booking handlers
    recommendations.querySelectorAll('button[data-doc]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const docId = parseInt(btn.getAttribute('data-doc'));
        const form = document.getElementById('bookingForm');
        const name = form.elements['name'].value;
        const phone = form.elements['phone'].value;
        const email = form.elements['email'].value;
        const date = document.getElementById('dateInput').value;
        if (!name || !phone || !date) { alert('Please fill name, phone and date'); return; }

        const res = await postJson('/api/book', {name, phone, email, doctor_id:docId, date});
        if (res.success) {
          alert('Booked! Appointment ID: ' + res.appointment_id);
          btn.disabled = true;
          btn.parentElement.querySelector('.available').className = 'unavailable';
        } else {
          alert('Failed: ' + res.message);
        }
      });
    });
  });
  // Admin interactions
  const addDept = document.getElementById('addDept');
  if (addDept) {
    addDept.addEventListener('click', async () => {
      const name = document.getElementById('deptName').value.trim();
      if (!name) return alert('Name required');
      const res = await postJson('/api/admin/departments', {name});
      if (res.success) location.reload();
      else alert('Failed');
    });

    const addDoc = document.getElementById('addDoc');
    addDoc.addEventListener('click', async () => {
      const name = document.getElementById('docName').value.trim();
      const dept = document.getElementById('docDept').value;
      const slots = document.getElementById('docSlots').value || 0;
      if (!name || !dept) return alert('Name and department required');
      const res = await postJson('/api/admin/doctors', {name, department_id: parseInt(dept), daily_slot_limit: parseInt(slots)});
      if (res.success) location.reload(); else alert('Failed');
    });
  }

  // Appointments page interactions
  const applyFilter = document.getElementById('applyFilter');
  if (applyFilter) {
    const loadDoctors = async () => {
      const docs = await postJson('/api/admin/doctors', {});
      // /api/admin/doctors returns list on GET; our postJson used, so fetch manually
    };

    const fetchAndRender = async () => {
      const docId = document.getElementById('filterDoc').value;
      const date = document.getElementById('filterDate').value;
      const qs = new URLSearchParams();
      if (docId) qs.set('doctor_id', docId);
      if (date) qs.set('date', date);
      const res = await fetch('/api/appointments?' + qs.toString());
      const appts = await res.json();
      const container = document.getElementById('apptTable');
      container.innerHTML = '<table class="table"><thead><tr><th>Patient</th><th>Doctor</th><th>Date</th><th>Time</th><th>Status</th></tr></thead><tbody>' + appts.map(a=>`<tr><td>${a.patient}</td><td>${a.doctor}</td><td>${a.date}</td><td>${a.time}</td><td>${a.status}</td></tr>`).join('') + '</tbody></table>';
    };

    applyFilter.addEventListener('click', fetchAndRender);

    const exportBtn = document.getElementById('exportBtn');
    exportBtn.addEventListener('click', ()=>{
      const docId = document.getElementById('filterDoc').value;
      const date = document.getElementById('filterDate').value;
      const qs = new URLSearchParams();
      if (docId) qs.set('doctor_id', docId);
      if (date) qs.set('date', date);
      window.location = '/api/appointments/export?' + qs.toString();
    });
  }
});
