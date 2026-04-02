// Utility for API calls
async function postJson(url, data) {
  const res = await fetch(url, {
    method: 'POST', 
    headers: {'Content-Type':'application/json'}, 
    body: JSON.stringify(data)
  });
  return res.json();
}

document.addEventListener('DOMContentLoaded', () => {
  
  // ----------------------------------------------------
  // INDUSTRY GRADE BOOTSTRAP 5 FORM VALIDATION
  // ----------------------------------------------------
  const forms = document.querySelectorAll('.needs-validation');
  Array.prototype.slice.call(forms).forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add('was-validated');
    }, false);
  });

  // ----------------------------------------------------
  // BOOKING PAGE LOGIC
  // ----------------------------------------------------
  const recommendBtn = document.getElementById('recommendBtn');
  const recommendations = document.getElementById('recommendations');

  // Protect against null references on pages that don't have this button
  if (recommendBtn && recommendations) {
    recommendBtn.addEventListener('click', async () => {
      const checked = Array.from(document.querySelectorAll('#symptomsList input[type=checkbox]:checked')).map(i => parseInt(i.value));
      const date = document.getElementById('dateInput').value;
      const data = await postJson('/api/recommend', {symptoms: checked, date});

      // render
      recommendations.innerHTML = '';
      const deptCard = document.createElement('div');
      deptCard.className = 'glass-card p-4 mb-3';
      deptCard.innerHTML = `<h5 class="fw-bold mb-3 text-primary"><i class="bi bi-diagram-3 me-2"></i>Recommended Departments</h5>` 
        + data.departments.map(d => `<div class="mb-1"><span class="fw-medium">${d.name}</span> <span class="badge bg-secondary ms-2">Score: ${d.score}</span></div>`).join('');
      recommendations.appendChild(deptCard);

      const docCard = document.createElement('div');
      docCard.className = 'glass-card p-4 border-info border-start border-4';
      docCard.innerHTML = `<h5 class="fw-bold mb-3 text-info"><i class="bi bi-person-lines-fill me-2"></i>Available Doctors</h5>`;
      
      if (data.doctors.length === 0) {
        docCard.innerHTML += '<div class="text-muted">No doctors found for this recommendation.</div>';
      } else {
        const list = document.createElement('div');
        data.doctors.forEach(d => {
          const el = document.createElement('div');
          el.className = 'd-flex justify-content-between align-items-center py-2 border-bottom';
          el.innerHTML = `
            <div class="fw-medium text-dark">${d.name}</div>
            <div>
              ${d.available ? '<span class="badge bg-success rounded-pill px-3 me-2">Available</span>' : '<span class="badge bg-danger rounded-pill px-3 me-2">Full</span>'} 
              <button class="btn btn-sm btn-primary fw-bold shadow-sm" data-doc="${d.id}" ${d.available ? '' : 'disabled'}>
                 Book Slot
              </button>
            </div>`;
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
          
          if (!name || !phone || !date) { 
            alert('Please fill out your name, phone, and preferred date to book.'); 
            return; 
          }

          const res = await postJson('/api/book', {name, phone, email, doctor_id: docId, date});
          if (res.success) {
            alert('Booking Successful! Your Appointment ID is: ' + res.appointment_id);
            btn.disabled = true;
            btn.innerText = 'Booked';
            btn.classList.replace('btn-primary', 'btn-secondary');
            const badge = btn.parentElement.querySelector('.bg-success');
            if(badge) {
              badge.classList.replace('bg-success', 'bg-danger');
              badge.innerText = 'Reserved';
            }
          } else {
            alert('Booking Failed: ' + res.message);
          }
        });
      });
    });
  }

  // ----------------------------------------------------
  // ADMIN INTERACTIONS
  // ----------------------------------------------------
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
    if (addDoc) {
      addDoc.addEventListener('click', async () => {
        const name = document.getElementById('docName').value.trim();
        const dept = document.getElementById('docDept').value;
        const slots = document.getElementById('docSlots').value || 0;
        if (!name || !dept) return alert('Name and department required');
        const res = await postJson('/api/admin/doctors', {name, department_id: parseInt(dept), daily_slot_limit: parseInt(slots)});
        if (res.success) location.reload(); else alert('Failed');
      });
    }
  }

  // ----------------------------------------------------
  // APPOINTMENTS PAGE EXPORTS
  // ----------------------------------------------------
  const applyFilter = document.getElementById('applyFilter');
  if (applyFilter) {
    const fetchAndRender = async () => {
      const docId = document.getElementById('filterDoc').value;
      const date = document.getElementById('filterDate').value;
      const qs = new URLSearchParams();
      if (docId) qs.set('doctor_id', docId);
      if (date) qs.set('date', date);
      const res = await fetch('/api/appointments?' + qs.toString());
      const appts = await res.json();
      const container = document.getElementById('apptTable');
      
      container.innerHTML = `
        <table class="table table-hover">
          <thead class="table-light"><tr><th>Patient</th><th>Doctor</th><th>Date</th><th>Time</th><th>Status</th></tr></thead>
          <tbody>
            ${appts.map(a => `<tr><td>${a.patient}</td><td>${a.doctor}</td><td>${a.date}</td><td>${a.time}</td><td><span class="badge bg-secondary">${a.status}</span></td></tr>`).join('')}
          </tbody>
        </table>`;
    };

    applyFilter.addEventListener('click', fetchAndRender);

    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        const docId = document.getElementById('filterDoc').value;
        const date = document.getElementById('filterDate').value;
        const qs = new URLSearchParams();
        if (docId) qs.set('doctor_id', docId);
        if (date) qs.set('date', date);
        window.location = '/api/appointments/export?' + qs.toString();
      });
    }
  }
});
