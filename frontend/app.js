async function apiFetch(url, options = {}) {
    const opts = {
        credentials: 'same-origin',
        ...options
    };

    if (opts.body && !(opts.body instanceof FormData)) {
        opts.headers = {
            'Content-Type': 'application/json',
            ...(opts.headers || {})
        };
        opts.body = JSON.stringify(opts.body);
    }

    const res = await fetch(url, opts);
    let data = null;
    try {
        data = await res.json();
    } catch {
        data = null;
    }

    if (!res.ok) {
        const err = new Error((data && (data.error || data.message)) || `Request failed: ${res.status}`);
        err.status = res.status;
        err.data = data;
        throw err;
    }

    return data;
}

function redirectForRole(role) {
    if (role === 'admin') window.location.href = '/frontend/admin';
    else if (role === 'worker') window.location.href = '/frontend/worker';
    else window.location.href = '/frontend/user';
}

async function requireAuth(expectedRole) {
    const me = await apiFetch('/api/me');
    if (expectedRole && me.role !== expectedRole) {
        redirectForRole(me.role);
        return null;
    }
    return me;
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function renderProgressCell(progress) {
    const safe = Math.max(0, Math.min(100, parseInt(progress || 0)));
    return `
        <div class="progress">
            <div class="progress-bar" style="width: ${safe}%"></div>
        </div>
        <div class="muted">${safe}%</div>
    `;
}

async function loadProgressImages(issueId, containerEl) {
    if (!containerEl) return;
    containerEl.innerHTML = '<div class="muted">Loading photos...</div>';
    try {
        const images = await apiFetch(`/issues/${issueId}/progress-images`);
        if (!images || !images.length) {
            containerEl.innerHTML = '<div class="muted">No progress photos uploaded yet.</div>';
            return;
        }
        const html = images.map(img => {
            const dt = img.created_at ? new Date(img.created_at).toLocaleString() : '';
            return `
                <a class="thumb" href="${img.url}" target="_blank" rel="noopener">
                    <img src="${img.url}" alt="progress" />
                    <div class="thumb-meta muted">${dt}</div>
                </a>
            `;
        }).join('');
        containerEl.innerHTML = `<div class="thumb-grid">${html}</div>`;
    } catch (err) {
        containerEl.innerHTML = '<div class="muted">Failed to load photos.</div>';
    }
}

async function uploadProgressImage(issueId, fileInputEl, galleryEl) {
    if (!fileInputEl || !fileInputEl.files || !fileInputEl.files.length) {
        alert('Please choose an image first');
        return;
    }
    const fd = new FormData();
    fd.append('image', fileInputEl.files[0]);
    try {
        await apiFetch(`/issues/${issueId}/progress-images`, { method: 'POST', body: fd });
        fileInputEl.value = '';
        await loadProgressImages(issueId, galleryEl);
        alert('Progress photo uploaded');
    } catch (err) {
        alert(err.message || 'Failed to upload photo');
    }
}

async function initLoginPage() {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const alertBox = document.getElementById('alert');
    const container = document.getElementById('container');
    const signUpBtn = document.getElementById('signUp');
    const signInBtn = document.getElementById('signIn');

    function showAlert(msg) {
        if (!alertBox) return;
        alertBox.style.display = 'block';
        alertBox.textContent = msg;
    }

    if (signUpBtn && container) {
        signUpBtn.addEventListener('click', () => {
            container.classList.add('right-panel-active');
            if (alertBox) alertBox.style.display = 'none';
        });
    }
    if (signInBtn && container) {
        signInBtn.addEventListener('click', () => {
            container.classList.remove('right-panel-active');
            if (alertBox) alertBox.style.display = 'none';
        });
    }

    try {
        const me = await apiFetch('/api/me');
        if (me && me.role) {
            redirectForRole(me.role);
            return;
        }
    } catch {
        // not logged in
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            alertBox.style.display = 'none';

            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            try {
                const data = await apiFetch('/api/login', { method: 'POST', body: { username, password } });
                redirectForRole(data.role);
            } catch (err) {
                showAlert(err.message || 'Login failed');
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            alertBox.style.display = 'none';

            const username = document.getElementById('reg-username').value;
            const password = document.getElementById('reg-password').value;
            const role = document.getElementById('reg-role').value;

            try {
                await apiFetch('/api/register', { method: 'POST', body: { username, password, role } });
                if (container) container.classList.remove('right-panel-active');
                showAlert('Registered successfully. You can now login.');
            } catch (err) {
                showAlert(err.message || 'Registration failed');
            }
        });
    }
}

async function initAdminPage() {
    const me = await requireAuth('admin');
    if (!me) return;
    setText('me', me.username);

    const tbody = document.querySelector('#issues-table tbody');
    const usersTbody = document.querySelector('#users-table tbody');
    if (!tbody) return;

    try {
        const [workers, issues, users] = await Promise.all([
            apiFetch('/workers'),
            apiFetch('/issues'),
            usersTbody ? apiFetch('/admin/users') : Promise.resolve([])
        ]);

        const workersById = {};
        (workers || []).forEach(w => { workersById[w.id] = w.username; });

        tbody.innerHTML = '';
        if (!issues.length) {
            tbody.innerHTML = '<tr><td colspan="8">No issues found.</td></tr>';
            return;
        }

        issues.forEach(issue => {
            const tr = document.createElement('tr');
            const selectId = `worker-select-${issue.id}`;
            const galleryId = `admin-photos-${issue.id}`;
            const toggleId = `admin-photos-toggle-${issue.id}`;
            const assigned = issue.assigned_worker_id ? (workersById[issue.assigned_worker_id] || issue.assigned_worker_id) : 'Unassigned';

            tr.innerHTML = `
                <td>${issue.id}</td>
                <td>${issue.user_id}</td>
                <td>${issue.status}</td>
                <td>${renderProgressCell(issue.progress)}</td>
                <td>${assigned}</td>
                <td>
                    <select id="${selectId}">
                        <option value="">Select worker</option>
                        ${(workers || []).map(w => '<option value="' + w.id + '" ' + (w.id === issue.assigned_worker_id ? 'selected' : '') + '>' + w.username + '</option>').join('')}
                    </select>
                    <button type="button" data-issue-id="${issue.id}" data-select-id="${selectId}">Assign</button>
                </td>
                <td>
                    <button type="button" class="secondary" id="${toggleId}" data-issue-id="${issue.id}">View</button>
                    <div class="gallery" id="${galleryId}" style="display:none; margin-top: 0.5rem;"></div>
                </td>
                <td>${issue.description}</td>
            `;

            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('button[data-issue-id].secondary').forEach(btn => {
            btn.addEventListener('click', async () => {
                const issueId = parseInt(btn.getAttribute('data-issue-id'));
                const galleryEl = document.getElementById(`admin-photos-${issueId}`);
                if (!galleryEl) return;
                const isHidden = galleryEl.style.display === 'none' || galleryEl.style.display === '';
                if (isHidden) {
                    galleryEl.style.display = 'block';
                    await loadProgressImages(issueId, galleryEl);
                    btn.textContent = 'Hide';
                } else {
                    galleryEl.style.display = 'none';
                    btn.textContent = 'View';
                }
            });
        });

        tbody.querySelectorAll('button[data-issue-id][data-select-id]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const issueId = parseInt(btn.getAttribute('data-issue-id'));
                const selectId = btn.getAttribute('data-select-id');
                const select = document.getElementById(selectId);
                const workerId = select.value;
                if (!workerId) {
                    alert('Please select a worker');
                    return;
                }

                try {
                    await apiFetch('/assign', { method: 'POST', body: { issue_id: issueId, worker_id: parseInt(workerId) } });
                    window.location.reload();
                } catch (err) {
                    alert(err.message || 'Failed to assign');
                }
            });
        });

        if (usersTbody) {
            usersTbody.innerHTML = '';
            if (!users || !users.length) {
                usersTbody.innerHTML = '<tr><td colspan="7">No users found.</td></tr>';
            } else {
                users.forEach(u => {
                    const tr = document.createElement('tr');
                    const bannedText = u.is_banned ? 'Yes' : 'No';
                    const canManage = u.role !== 'admin' && parseInt(u.id) !== parseInt(me.id);
                    const banLabel = u.is_banned ? 'Unban' : 'Ban';

                    tr.innerHTML = `
                        <td>${u.id}</td>
                        <td>${u.username}</td>
                        <td>${u.role}</td>
                        <td>${bannedText}</td>
                        <td>${u.wallet_balance ?? 0}</td>
                        <td>${u.reputation_score ?? 0}</td>
                        <td>
                            ${canManage ? `<button type="button" data-user-id="${u.id}" data-user-banned="${u.is_banned ? '1' : '0'}" data-action="ban">${banLabel}</button>` : ''}
                            ${canManage ? `<button type="button" class="secondary" data-user-id="${u.id}" data-action="delete">Delete</button>` : ''}
                        </td>
                    `;
                    usersTbody.appendChild(tr);
                });

                usersTbody.querySelectorAll('button[data-action="ban"]').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const userId = parseInt(btn.getAttribute('data-user-id'));
                        const isBanned = btn.getAttribute('data-user-banned') === '1';
                        try {
                            await apiFetch(`/admin/users/${userId}/ban`, { method: 'POST', body: { banned: !isBanned } });
                            window.location.reload();
                        } catch (err) {
                            alert(err.message || 'Failed to update ban');
                        }
                    });
                });

                usersTbody.querySelectorAll('button[data-action="delete"]').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const userId = parseInt(btn.getAttribute('data-user-id'));
                        const ok = confirm('Delete this account? This will remove their issues and history.');
                        if (!ok) return;
                        try {
                            await apiFetch(`/admin/users/${userId}`, { method: 'DELETE' });
                            window.location.reload();
                        } catch (err) {
                            alert(err.message || 'Failed to delete user');
                        }
                    });
                });
            }
        }

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="8">Failed to load admin data.</td></tr>';
        if (usersTbody) usersTbody.innerHTML = '<tr><td colspan="7">Failed to load users.</td></tr>';
    }
}

async function initUserPage() {
    const me = await requireAuth('user');
    if (!me) return;
    setText('me', me.username);

    const walletEl = document.getElementById('wallet-balance');
    const repEl = document.getElementById('reputation-score');
    const redeemAlert = document.getElementById('redeem-alert');
    const redeemForm = document.getElementById('fastag-redeem-form');

    function showRedeemAlert(msg) {
        if (!redeemAlert) return;
        redeemAlert.style.display = 'block';
        redeemAlert.textContent = msg;
    }

    try {
        const lastReport = sessionStorage.getItem('lastReportReward');
        if (lastReport) {
            sessionStorage.removeItem('lastReportReward');
            const info = JSON.parse(lastReport);
            const conf = typeof info.ai_confidence === 'number' ? info.ai_confidence : null;
            if (info.reward_awarded) {
                const bal = (info.wallet_balance !== undefined && info.wallet_balance !== null) ? ` New balance: ${info.wallet_balance} coins.` : '';
                showRedeemAlert(`Reward awarded (+coins). AI confidence: ${conf !== null ? conf.toFixed(3) : 'n/a'}.${bal}`);
            } else {
                showRedeemAlert(`No reward awarded. Reason: ${info.reward_reason || 'unknown'}. AI confidence: ${conf !== null ? conf.toFixed(3) : 'n/a'}.`);
            }
        }
    } catch {
        // ignore
    }

    async function refreshWallet() {
        try {
            const wallet = await apiFetch('/wallet');
            if (walletEl) walletEl.textContent = String(wallet.wallet_balance ?? 0);
            if (repEl) repEl.textContent = String(wallet.reputation_score ?? 0);
        } catch (err) {
            console.error('Failed to load wallet:', err);
            showRedeemAlert(err.message || 'Failed to load wallet balance');
        }
    }

    await refreshWallet();

    if (redeemForm) {
        redeemForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (redeemAlert) redeemAlert.style.display = 'none';

            const vehicle_number = document.getElementById('vehicle-number')?.value;
            const coins = parseInt(document.getElementById('coins')?.value);

            if (!coins || coins < 5000) {
                showRedeemAlert('Minimum 5000 coins required');
                return;
            }

            try {
                const data = await apiFetch('/fastag/redeem', {
                    method: 'POST',
                    body: { vehicle_number, coins }
                });
                showRedeemAlert(`Request created: ${data.status} (₹${data.amount_rupees}). Ref: ${data.transaction_ref}`);
                await refreshWallet();
            } catch (err) {
                showRedeemAlert(err.message || 'Failed to create redemption request');
            }
        });
    }

    const tbody = document.querySelector('#my-issues-table tbody');
    if (!tbody) return;

    try {
        const issues = await apiFetch('/issues/mine');
        tbody.innerHTML = '';
        if (!issues.length) {
            tbody.innerHTML = '<tr><td colspan="6">No issues reported yet.</td></tr>';
            return;
        }

        issues.forEach(issue => {
            const completed = parseInt(issue.progress || 0) >= 100;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${issue.id}</td>
                <td>${issue.status}</td>
                <td>${renderProgressCell(issue.progress)}</td>
                <td>${issue.description}</td>
                <td>${completed ? '<span class="badge success">Complaint is completed.</span>' : '<span class="badge">In progress</span>'}</td>
                <td><button type="button" class="secondary" data-delete-issue-id="${issue.id}">Delete</button></td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('button[data-delete-issue-id]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const issueId = parseInt(btn.getAttribute('data-delete-issue-id'));
                const ok = confirm('Delete this complaint? This cannot be undone.');
                if (!ok) return;
                try {
                    await apiFetch(`/issues/${issueId}`, { method: 'DELETE' });
                    await refreshWallet();
                    window.location.reload();
                } catch (err) {
                    showRedeemAlert(err.message || 'Failed to delete complaint');
                }
            });
        });
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6">Failed to load issues.</td></tr>';
    }
}

async function initWorkerPage() {
    const me = await requireAuth('worker');
    if (!me) return;
    setText('me', me.username);

    const tbody = document.querySelector('#assigned-issues-table tbody');
    if (!tbody) return;

    try {
        const issues = await apiFetch('/issues/assigned');
        tbody.innerHTML = '';
        if (!issues.length) {
            tbody.innerHTML = '<tr><td colspan="6">No issues assigned yet.</td></tr>';
            return;
        }

        issues.forEach(issue => {
            const tr = document.createElement('tr');
            const selectId = `progress-select-${issue.id}`;
            const fileId = `photo-file-${issue.id}`;
            const uploadBtnId = `photo-upload-${issue.id}`;
            const galleryId = `worker-photos-${issue.id}`;
            const viewBtnId = `photo-view-${issue.id}`;
            tr.innerHTML = `
                <td>${issue.id}</td>
                <td id="status-${issue.id}">${issue.status}</td>
                <td>
                    <div class="progress">
                        <div class="progress-bar" id="progress-bar-${issue.id}" style="width: ${issue.progress}%"></div>
                    </div>
                    <div class="muted" id="progress-${issue.id}">${issue.progress}%</div>
                </td>
                <td>
                    <select id="${selectId}">
                        ${[0,10,20,30,40,50,60,70,80,90,100].map(p => '<option value="' + p + '" ' + (p === issue.progress ? 'selected' : '') + '>' + p + '%</option>').join('')}
                    </select>
                    <button type="button" data-issue-id="${issue.id}" data-select-id="${selectId}">Update</button>
                </td>
                <td>
                    <div class="photo-actions">
                        <input type="file" id="${fileId}" accept="image/*" />
                        <button type="button" id="${uploadBtnId}" data-issue-id="${issue.id}">Upload</button>
                        <button type="button" class="secondary" id="${viewBtnId}" data-issue-id="${issue.id}">View</button>
                    </div>
                    <div class="gallery" id="${galleryId}" style="display:none; margin-top: 0.5rem;"></div>
                </td>
                <td>${issue.description}</td>
            `;
            tbody.appendChild(tr);
        });

        tbody.querySelectorAll('button[id^="photo-upload-"]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const issueId = parseInt(btn.getAttribute('data-issue-id'));
                const fileInput = document.getElementById(`photo-file-${issueId}`);
                const galleryEl = document.getElementById(`worker-photos-${issueId}`);
                await uploadProgressImage(issueId, fileInput, galleryEl);
            });
        });

        tbody.querySelectorAll('button[id^="photo-view-"]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const issueId = parseInt(btn.getAttribute('data-issue-id'));
                const galleryEl = document.getElementById(`worker-photos-${issueId}`);
                if (!galleryEl) return;
                const isHidden = galleryEl.style.display === 'none' || galleryEl.style.display === '';
                if (isHidden) {
                    galleryEl.style.display = 'block';
                    await loadProgressImages(issueId, galleryEl);
                    btn.textContent = 'Hide';
                } else {
                    galleryEl.style.display = 'none';
                    btn.textContent = 'View';
                }
            });
        });

        tbody.querySelectorAll('button[data-issue-id][data-select-id]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const issueId = parseInt(btn.getAttribute('data-issue-id'));
                const selectId = btn.getAttribute('data-select-id');
                const select = document.getElementById(selectId);
                const progress = parseInt(select.value);

                try {
                    const data = await apiFetch(`/issues/${issueId}/progress`, { method: 'POST', body: { progress } });
                    document.getElementById(`progress-${issueId}`).textContent = `${data.progress}%`;
                    document.getElementById(`status-${issueId}`).textContent = data.status;
                    const bar = document.getElementById(`progress-bar-${issueId}`);
                    if (bar) bar.style.width = `${data.progress}%`;
                    if (data.completed) alert('Progress is 100%. Complaint marked as completed.');
                } catch (err) {
                    alert(err.message || 'Failed to update progress');
                }
            });
        });

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6">Failed to load assigned issues.</td></tr>';
    }
}

async function initReportPage() {
    const me = await requireAuth('user');
    if (!me) return;
    setText('me', me.username);

    const form = document.getElementById('report-form');
    const alertBox = document.getElementById('alert');

    function showAlert(msg) {
        if (!alertBox) return;
        alertBox.style.display = 'block';
        alertBox.textContent = msg;
    }

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            alertBox.style.display = 'none';

            const fd = new FormData(form);
            try {
                const out = await apiFetch('/report', { method: 'POST', body: fd });
                try {
                    sessionStorage.setItem('lastReportReward', JSON.stringify(out));
                } catch {
                    // ignore
                }
                window.location.href = '/frontend/user';
            } catch (err) {
                showAlert(err.message || 'Failed to submit issue');
            }
        });
    }

    if (window.L) {
        const map = L.map('map').setView([20.5937, 78.9629], 5);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        let marker;
        map.on('click', function(e) {
            if (marker) map.removeLayer(marker);
            marker = L.marker(e.latlng).addTo(map);
            const lat = document.getElementById('lat');
            const lng = document.getElementById('lng');
            if (lat) lat.value = e.latlng.lat;
            if (lng) lng.value = e.latlng.lng;
        });
    }
}

window.FrontendApp = {
    initLoginPage,
    initAdminPage,
    initUserPage,
    initWorkerPage,
    initReportPage
};
