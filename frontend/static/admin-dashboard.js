const API_BASE_URL = "/api";
let currentToken = localStorage.getItem("access_token");
let userRole = localStorage.getItem("token_role");

let allStudentsData = [];
let allFacultyData = [];
let allInsightsData = [];
let allSystemBranches = [];
let activeCharts = [];

document.addEventListener("DOMContentLoaded", async () => {
    if (!currentToken || userRole !== "Admin") {
        alert("Unauthorized access. Redirecting to login...");
        window.location.href = "/";
        return;
    }

    setupEventListeners();
    createFacultyModal();
    createBranchModal();

    // Fetch branches FIRST so all dropdowns can be populated
    await fetchBranches();
    populateAllBranchDropdowns();
    populateSemesterDropdowns();

    fetchOverview();
    fetchBranchData();
    fetchStudents();
    fetchFaculty();
    fetchAttendanceInsights();
    fetchDBInsights();
});

function setupEventListeners() {
    // Logout
    document.getElementById("logout-btn").addEventListener("click", logout);
    document.getElementById("logout-btn-header").addEventListener("click", logout);

    // Branch Data Filter
    document.getElementById("btn-filter-branch-data").addEventListener("click", () => {
        const dept = document.getElementById("branch-filter-dept").value;
        const sem = document.getElementById("branch-filter-sem").value;
        fetchBranchData(dept, sem);
    });

    // Student Filters
    document.getElementById("student-filter-dept").addEventListener("change", renderStudents);
    document.getElementById("student-filter-sem").addEventListener("change", renderStudents);

    // Faculty Filters
    document.getElementById("faculty-filter-dept").addEventListener("change", renderFaculty);
    document.getElementById("faculty-filter-role").addEventListener("change", renderFaculty);

    // Attendance Insights Filters
    document.getElementById("attendance-filter-branch").addEventListener("change", renderAttendanceInsights);

    // Student Search
    const searchInput = document.getElementById("admin-student-search");
    if(searchInput) {
        let debounceTimer;
        searchInput.addEventListener("input", (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchStudents(e.target.value);
            }, 300);
        });
    }

    // Admit card upload form
    const admitForm = document.getElementById("form-upload-admit-cards");
    if(admitForm) {
        admitForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById("admit-card-zip");
            if (!fileInput.files.length) return alert("Please select a ZIP file.");

            const formData = new FormData();
            formData.append("file", fileInput.files[0]);

            try {
                const res = await fetch(`${API_BASE_URL}/admin/upload-admit-cards`, {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${currentToken}` },
                    body: formData
                });
                const data = await res.json();
                if (res.ok) {
                    alert(data.message);
                    fetchStudents(); // Dynamic Update
                } else {
                    alert(data.detail || "Upload failed");
                }
            } catch (err) {
                console.error(err);
                alert("Error during upload.");
            }
        });
    }

    // Manage branch submit
    const manageForm = document.getElementById("form-manage-branch");
    if(manageForm) {
        manageForm.addEventListener("submit", submitManageBranch);
    }
}

async function fetchOverview() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/overview`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch overview");
        const data = await res.json();
        
        const grid = document.getElementById("admin-overview-stats");
        grid.innerHTML = `
            <div class="info-item admin-stat-card">
                <label>Total Fine Collected</label>
                <div class="info-value text-green">₹ ${data.total_fine_collected}</div>
            </div>
            <div class="info-item admin-stat-card">
                <label>Total Students</label>
                <div class="info-value">${data.total_students}</div>
            </div>
            <div class="info-item admin-stat-card">
                <label>Total Branches</label>
                <div class="info-value">${data.total_branches}</div>
            </div>
            <div class="info-item admin-stat-card">
                <label>Total Semesters Active</label>
                <div class="info-value">${data.total_semesters}</div>
            </div>
            <div class="info-item admin-stat-card warning">
                <label>Pending Student Requests</label>
                <div class="info-value text-red">${data.pending_requests}</div>
            </div>
        `;
    } catch (err) {
        console.error(err);
    }
}

async function fetchBranchData(department = "all", semester = "all") {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/branch-data?department=${encodeURIComponent(department)}&semester=${encodeURIComponent(semester)}`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch branch data");
        const data = await res.json();
        
        const tbody = document.getElementById("branch-data-tbody");
        tbody.innerHTML = "";
        
        if (data.data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center">No records found.</td></tr>`;
            return;
        }

        // Populate dropdowns once
        populateBranchFilters(data.data);

        data.data.forEach(row => {
            const tr = document.createElement("tr");
            if (row.is_active) tr.className = "active-sem-highlight";
            tr.innerHTML = `
                <td><strong>${row.department}</strong></td>
                <td>${row.semester} ${row.is_active ? '<span class="active-badge">Active</span>' : ''}</td>
                <td>${row.total_students}</td>
                <td>₹ ${row.total_fine_generated}</td>
                <td><span class="text-green">₹ ${row.total_fine_collected}</span></td>
                <td><span class="badge ${row.defaulters > 0 ? 'badge-pending' : 'badge-approved'}">${row.defaulters} Defaulters</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

let filtersPopulated = false;
function populateBranchFilters(data) {
    if(filtersPopulated) return;
    // Semesters only (branches come from allSystemBranches)
    const sFilter = document.getElementById("branch-filter-sem");
    [1, 2, 3, 4, 5, 6].forEach(s => {
        sFilter.innerHTML += `<option value="${s}">${s}th Semester</option>`;
    });
    filtersPopulated = true;
}

function populateAllBranchDropdowns() {
    const branchNames = allSystemBranches.map(b => b.name).sort();

    // Branch Data filter
    const branchDataDept = document.getElementById("branch-filter-dept");
    branchDataDept.innerHTML = '<option value="all">All Departments</option>';
    branchNames.forEach(n => { branchDataDept.innerHTML += `<option value="${n}">${n}</option>`; });

    // Student filter
    const studentDept = document.getElementById("student-filter-dept");
    studentDept.innerHTML = '<option value="all">All Departments</option>';
    branchNames.forEach(n => { studentDept.innerHTML += `<option value="${n}">${n}</option>`; });

    const studentSem = document.getElementById("student-filter-sem");
    studentSem.innerHTML = '<option value="all">All Semesters</option>';
    [1,2,3,4,5,6].forEach(s => { studentSem.innerHTML += `<option value="${s}">${s}th Semester</option>`; });

    // Faculty filter
    const facultyDept = document.getElementById("faculty-filter-dept");
    facultyDept.innerHTML = '<option value="all">All Departments</option>';
    branchNames.forEach(n => { facultyDept.innerHTML += `<option value="${n}">${n}</option>`; });

    // Attendance filter
    const attBranch = document.getElementById("attendance-filter-branch");
    attBranch.innerHTML = '<option value="all" style="color:black;">All Branches (Overall)</option>';
    branchNames.forEach(n => { attBranch.innerHTML += `<option value="${n}" style="color:black;">${n}</option>`; });
}

async function fetchStudents(search = "") {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/students?search=${search}`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch students");
        const data = await res.json();
        allStudentsData = data.students || [];
        renderStudents();
    } catch (err) {
        console.error(err);
    }
}

function renderStudents() {
    const deptFilter = document.getElementById("student-filter-dept").value;
    const semFilter = document.getElementById("student-filter-sem").value;
    
    let filtered = allStudentsData.filter(s => {
        const matchDept = deptFilter === "all" || s.department === deptFilter;
        const matchSem = semFilter === "all" || String(s.semester) === String(semFilter);
        return matchDept && matchSem;
    });

    const tbody = document.getElementById("admin-students-tbody");
    tbody.innerHTML = "";
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center">No students found matching filters.</td></tr>`;
        return;
    }

    filtered.forEach(s => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="clickable-cell">
                <div class="student-link">
                    <div class="avatar-sm">${s.name.charAt(0).toUpperCase()}</div> ${s.name}
                </div>
                <small class="text-light" style="margin-left: 45px;">Roll: ${s.roll_no}</small>
            </td>
            <td>${s.department} / ${s.semester}th</td>
            <td>${s.theory_attendance}%</td>
            <td>${s.practical_attendance}%</td>
            <td><span class="${s.total_fine > 0 ? 'text-red' : 'text-green'}">₹ ${s.total_fine}</span></td>
            <td><span class="badge badge-approved">${s.status}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

async function fetchFaculty() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/faculty`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch faculty");
        const data = await res.json();
        allFacultyData = data.faculty || [];
        renderFaculty();
    } catch (err) {
        console.error(err);
    }
}

function renderFaculty() {
    const deptFilter = document.getElementById("faculty-filter-dept").value;
    const roleFilter = document.getElementById("faculty-filter-role").value;
    
    let filtered = allFacultyData.filter(f => {
        const matchDept = deptFilter === "all" || f.department === deptFilter;
        const matchRole = roleFilter === "all" || f.role === roleFilter;
        return matchDept && matchRole;
    });

    const tbody = document.getElementById("admin-faculty-tbody");
    tbody.innerHTML = "";
    
    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center">No faculty found matching filters.</td></tr>`;
        return;
    }

    filtered.forEach(f => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${f.name} <br><small class="text-light">@${f.username}</small></td>
            <td>${f.department}</td>
            <td><span class="badge badge-pending">${f.role}</span></td>
            <td>
                <div class="action-btn-group">
                    <button class="btn btn-primary btn-sm" onclick="editFacultyRole(${f.id})"><i class="fa-solid fa-pen"></i> Edit Role</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteFaculty(${f.id})"><i class="fa-solid fa-trash"></i></button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function editFacultyRole(id) {
    const validRoles = [
        "ClassIncharge", "HOD", "PTI", "ANO", 
        "HostelSuperintendent_Boys", "HostelSuperintendent_Girls", 
        "Librarian", "CanteenOwner", "Admin"
    ];
    
    const newRole = prompt("Enter new role for this faculty:\n(Options: " + validRoles.join(", ") + ")");
    if (!newRole) return;
    
    // Normalize user input (remove spaces, match case-insensitively)
    const normalizedInput = newRole.replace(/\s+/g, '').toLowerCase();
    const matchedRole = validRoles.find(r => r.toLowerCase() === normalizedInput);
    
    if(!matchedRole) {
        alert("Invalid role entered! Must be one of: \n" + validRoles.join(", "));
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/admin/faculty/${id}/role`, {
            method: "PUT",
            headers: { 
                "Authorization": `Bearer ${currentToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ new_role: matchedRole })
        });
        const data = await res.json();
        if(res.ok) {
            alert(data.message);
            fetchFaculty();
            fetchOverview(); // Sync counts
        } else {
            alert(data.detail);
        }
    } catch (err) {
        console.error(err);
    }
}

async function deleteFaculty(id) {
    if(!confirm("Are you sure you want to delete this faculty member?")) return;
    try {
        const res = await fetch(`${API_BASE_URL}/admin/faculty/${id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        const data = await res.json();
        if(res.ok) {
            alert(data.message);
            fetchFaculty();
            fetchOverview(); // Sync counts
        } else {
            alert(data.detail);
        }
    } catch (err) {
        console.error(err);
    }
}

async function resetSystemData() {
    const code = prompt("Are you absolutely sure you want to erase ALL data? This cannot be undone. Type 'CONFIRM' to proceed.");
    if(code !== "CONFIRM") return;
    
    try {
        const res = await fetch(`${API_BASE_URL}/admin/reset`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        const data = await res.json();
        if(res.ok) {
            alert(data.message);
            window.location.reload();
        } else {
            alert(data.detail);
        }
    } catch (err) {
        console.error(err);
    }
}

function showAddFacultyModal() {
    document.getElementById("add-faculty-modal").style.display = "flex";
}

function hideAddFacultyModal() {
    document.getElementById("add-faculty-modal").style.display = "none";
}

async function submitAddFaculty(e) {
    e.preventDefault();
    const form = e.target;
    const validRoles = [
        "ClassIncharge", "HOD", "PTI", "ANO", 
        "HostelSuperintendent_Boys", "HostelSuperintendent_Girls", 
        "Librarian", "CanteenOwner", "Admin"
    ];
    
    // Normalize role (remove spaces, match case-insensitively to exact ENUM)
    const normalizedInput = form.role.value.replace(/[\s_]+/g, '').toLowerCase();
    const matchedRole = validRoles.find(r => r.toLowerCase() === normalizedInput);
    
    if(!matchedRole) {
        alert("Invalid role entered! Please select or type one of: \n" + validRoles.join(", "));
        return;
    }

    const data = {
        name: form.name.value,
        username: form.username.value,
        password: form.password.value,
        role: matchedRole,
        department: form.department.value,
        gender: "Male" // default dummy
    };
    
    try {
        const res = await fetch(`${API_BASE_URL}/admin/faculty`, {
            method: "POST",
            headers: { 
                "Authorization": `Bearer ${currentToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });
        const resData = await res.json();
        if(res.ok) {
            alert("Faculty Added");
            hideAddFacultyModal();
            fetchFaculty();
            fetchOverview(); // Sync counts
            form.reset();
        } else {
            alert(resData.detail);
        }
    } catch(err) {
        console.error(err);
    }
}

function createFacultyModal() {
    const modalHtml = `
    <div id="add-faculty-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999; justify-content:center; align-items:center;">
        <div style="background:#fff; padding:2rem; border-radius:12px; width:400px; max-width:90%;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                <h3 style="margin:0; color:var(--primary-color);">Add Faculty</h3>
                <span style="cursor:pointer; font-size:1.5rem;" onclick="hideAddFacultyModal()">&times;</span>
            </div>
            <form id="add-faculty-form" onsubmit="submitAddFaculty(event)" style="display:flex; flex-direction:column; gap:1rem;">
                <div>
                    <label style="display:block; margin-bottom:.5rem;">Full Name</label>
                    <input type="text" name="name" class="form-control" required>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.5rem;">Username</label>
                    <input type="text" name="username" class="form-control" required>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.5rem;">Password</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.5rem;">Role</label>
                    <input type="text" name="role" list="role-options" class="form-control" placeholder="Select or type role..." required>
                    <datalist id="role-options">
                        <option value="HOD">
                        <option value="Class Incharge">
                        <option value="PTI">
                        <option value="ANO">
                        <option value="Hostel Superintendent Boys">
                        <option value="Hostel Superintendent Girls">
                        <option value="Librarian">
                        <option value="Canteen Owner">
                        <option value="Admin">
                    </datalist>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.5rem;">Department</label>
                    <input type="text" name="department" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary" style="margin-top:1rem;">Save Faculty</button>
            </form>
        </div>
    </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function fetchAttendanceInsights() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/attendance-insights`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch insights");
        const data = await res.json();
        allInsightsData = data.insights || [];
        renderAttendanceInsights();
    } catch (err) {
        console.error(err);
    }
}

function renderAttendanceInsights() {
    activeCharts.forEach(c => c.destroy());
    activeCharts = [];
    const branchFilter = document.getElementById("attendance-filter-branch").value;
    const grid = document.getElementById("admin-attendance-grid");
    grid.innerHTML = "";
    if (allInsightsData.length === 0) {
        grid.innerHTML = `<div class="card" style="grid-column:1/-1;text-align:center;padding:3rem;"><p style="color:var(--text-light);">No attendance data yet.</p></div>`;
        return;
    }
    let dd = [];
    if (branchFilter === "all") {
        const bg = {};
        allInsightsData.forEach(i => {
            if (!bg[i.branch]) bg[i.branch] = { b: i.branch, ts: 0, ps: 0, c: 0, st: 0 };
            bg[i.branch].ts += i.theory_avg; bg[i.branch].ps += i.practical_avg;
            bg[i.branch].st += i.student_count; bg[i.branch].c++;
        });
        dd = Object.values(bg).map(g => ({ title: g.b+" (Overall)", ta: Math.round(g.ts/g.c), pa: Math.round(g.ps/g.c), sc: g.st }));
    } else {
        dd = allInsightsData.filter(i => i.branch === branchFilter).map(i => ({ title: i.branch+" - Sem "+i.semester, ta: Math.round(i.theory_avg), pa: Math.round(i.practical_avg), sc: i.student_count }));
    }
    if (dd.length === 0) { grid.innerHTML = `<div class="card" style="grid-column:1/-1;text-align:center;padding:3rem;"><p style="color:var(--text-light);">No data for selected branch.</p></div>`; return; }
    dd.forEach((ins, idx) => {
        const card = document.createElement("div"); card.className = "semester-card";
        const tI = "ct"+idx, pI = "cp"+idx;
        card.innerHTML = `<h3>${ins.title}</h3><div style="display:flex;justify-content:space-around;align-items:center;margin:20px 0 15px;"><div style="width:130px;text-align:center;"><canvas id="${tI}" width="130" height="130"></canvas><small style="font-weight:600;color:var(--text-light);margin-top:8px;display:block;">Theory</small></div><div style="width:130px;text-align:center;"><canvas id="${pI}" width="130" height="130"></canvas><small style="font-weight:600;color:var(--text-light);margin-top:8px;display:block;">Practical</small></div></div><div style="padding-top:15px;border-top:1px solid #f1f5f9;color:var(--text-light);font-weight:500;font-size:0.9rem;"><i class="fa-solid fa-users" style="margin-right:5px;"></i> ${ins.sc} Students</div>`;
        grid.appendChild(card);
        setTimeout(() => {
            const mk = (id, v, cl) => { const e = document.getElementById(id); if(!e) return; activeCharts.push(new Chart(e, { type:'doughnut', data:{labels:['Attended','Missed'],datasets:[{data:[v,100-v],backgroundColor:[cl,'#f1f5f9'],borderWidth:0}]}, options:{cutout:'70%',responsive:false,plugins:{legend:{display:false},tooltip:{enabled:true}}}, plugins:[{id:'ctr',afterDraw(ch){const{ctx,chartArea:{width:w,height:h,top:t,left:l}}=ch;ctx.save();ctx.font='bold 16px Outfit';ctx.fillStyle='#1e293b';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(v+'%',l+w/2,t+h/2);ctx.restore();}}] })); };
            mk(tI, ins.ta, ins.ta<75?'#ef4444':'#10b981');
            mk(pI, ins.pa, ins.pa<75?'#ef4444':'#10b981');
        }, 50);
    });
}

async function fetchDBInsights() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/db-insights`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch DB insights");
        const data = await res.json();
        
        const grid = document.getElementById("admin-db-insights");
        grid.innerHTML = "";
        
        if (data.insights.length === 0) {
            grid.innerHTML = `<p class="no-data" style="grid-column: 1/-1;">No class incharge data available.</p>`;
            return;
        }

        data.insights.forEach((insight, index) => {
            const card = document.createElement("div");
            card.className = "insight-item";
            
            // Alternate colors for variety
            const colors = [
                { bg: '#eff6ff', color: '#1e40af' }, // Blue
                { bg: '#f0fdf4', color: '#166534' }, // Green
                { bg: '#fefce8', color: '#854d0e' }, // Yellow
                { bg: '#fef2f2', color: '#991b1b' }  // Red
            ];
            const theme = colors[index % colors.length];

            card.innerHTML = `
                <div class="insight-icon" style="background: ${theme.bg}; color: ${theme.color};">
                    <i class="fa-solid fa-chalkboard-user"></i>
                </div>
                <div class="insight-value">${insight.total_students}</div>
                <div class="insight-label">
                    ${insight.branch} - ${insight.semester}th Sem <br>
                    <span style="font-size:0.75rem; font-weight: 500;">${insight.incharge_name}</span>
                </div>
            `;
            grid.appendChild(card);
        });
        
        // Render Demographics
        if(data.overall_stats) {
            const demoGrid = document.getElementById("admin-student-demographics");
            if(demoGrid) {
                demoGrid.innerHTML = `
                    <div class="insight-item">
                        <div class="insight-icon" style="background: #eff6ff; color: #1e40af;">
                            <i class="fa-solid fa-building"></i>
                        </div>
                        <div class="insight-value">${data.overall_stats.total_hosteller}</div>
                        <div class="insight-label">Hostellers</div>
                    </div>
                    <div class="insight-item">
                        <div class="insight-icon" style="background: #fefce8; color: #854d0e;">
                            <i class="fa-solid fa-flag"></i>
                        </div>
                        <div class="insight-value">${data.overall_stats.total_ncc}</div>
                        <div class="insight-label">NCC Cadets</div>
                    </div>
                    <div class="insight-item">
                        <div class="insight-icon" style="background: #f0fdf4; color: #166534;">
                            <i class="fa-solid fa-circle-check"></i>
                        </div>
                        <div class="insight-value">${data.overall_stats.total_accepted}</div>
                        <div class="insight-label">Paid</div>
                    </div>
                    <div class="insight-item">
                        <div class="insight-icon" style="background: #fef2f2; color: #991b1b;">
                            <i class="fa-solid fa-circle-xmark"></i>
                        </div>
                        <div class="insight-value">${data.overall_stats.total_pending}</div>
                        <div class="insight-label">Unpaid</div>
                    </div>
                `;
            }
        }
    } catch (err) {
        console.error(err);
    }
}

async function fetchBranches() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/branches`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch branches");
        const data = await res.json();
        allSystemBranches = data.branches || [];
        
        const tbody = document.getElementById("admin-branches-tbody");
        tbody.innerHTML = "";
        
        if (allSystemBranches.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center">No branches found.</td></tr>`;
            return;
        }

        allSystemBranches.forEach(b => {
            const tr = document.createElement("tr");
            const escapedBranch = b.name.replace(/'/g, "\\'");
            tr.innerHTML = `
                <td><strong>${b.name}</strong></td>
                <td>${b.hod_name || '<span class="text-red">Missing</span>'}</td>
                <td>${b.hod_username || 'N/A'}</td>
                <td>
                    <button class="btn btn-outline btn-sm" onclick="showManageBranchModal('${escapedBranch}', '${b.hod_name || ''}', '${b.hod_username || ''}')"><i class="fa-solid fa-gear"></i> Manage</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

function showAddBranchModal() {
    document.getElementById("add-branch-modal").style.display = "flex";
}

function hideAddBranchModal() {
    document.getElementById("add-branch-modal").style.display = "none";
}

async function submitAddBranch(e) {
    e.preventDefault();
    const form = e.target;
    
    const data = {
        name: form.name.value,
        hod_name: form.hod_name.value,
        hod_username: form.hod_username.value,
        hod_password: form.hod_password.value,
        hod_gender: form.hod_gender.value
    };
    
    try {
        const res = await fetch(`${API_BASE_URL}/admin/branches`, {
            method: "POST",
            headers: { 
                "Authorization": `Bearer ${currentToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });
        const resData = await res.json();
        if(res.ok) {
            alert(resData.message);
            hideAddBranchModal();
            fetchBranches().then(() => populateAllBranchDropdowns());
            fetchOverview();
            form.reset();
        } else {
            alert(resData.detail || "Failed to add branch");
        }
    } catch(err) {
        console.error(err);
        alert("Error adding branch");
    }
}

function createBranchModal() {
    const modalHtml = `
    <div id="add-branch-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999; justify-content:center; align-items:center;">
        <div style="background:#fff; padding:2rem; border-radius:12px; width:450px; max-width:90%;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                <h3 style="margin:0; color:var(--primary-color);">Add New Branch & HOD</h3>
                <span style="cursor:pointer; font-size:1.5rem;" onclick="hideAddBranchModal()">&times;</span>
            </div>
            <form id="add-branch-form" onsubmit="submitAddBranch(event)" style="display:flex; flex-direction:column; gap:1rem;">
                <div>
                    <label style="display:block; margin-bottom:.3rem; font-weight:600;">Branch Name</label>
                    <input type="text" name="name" class="form-control" placeholder="e.g. Mechanical Engineering" required>
                </div>
                <hr style="margin: 0.5rem 0; border: 0; border-top: 1px solid #eee;">
                <p style="margin:0; font-size:0.85rem; color:#666;">Set up the Head of Department (HOD) account:</p>
                <div>
                    <label style="display:block; margin-bottom:.3rem;">HOD Full Name</label>
                    <input type="text" name="hod_name" class="form-control" required>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.3rem;">HOD Username</label>
                    <input type="text" name="hod_username" class="form-control" required>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.3rem;">HOD Password</label>
                    <input type="password" name="hod_password" class="form-control" required>
                </div>
                <div>
                    <label style="display:block; margin-bottom:.3rem;">HOD Gender</label>
                    <select name="hod_gender" class="form-control">
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="margin-top:1rem;">Create Branch & HOD</button>
            </form>
        </div>
    </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");
    window.location.href = "/";
}

function showManageBranchModal(branchName, hodName, hodUsername) {
    document.getElementById("manage-branch-name").value = branchName;
    document.getElementById("manage-branch-display").value = branchName;
    document.getElementById("manage-branch-hod-name").value = hodName;
    document.getElementById("manage-branch-hod-username").value = hodUsername;
    document.getElementById("manage-branch-hod-password").value = ''; // Leave blank by default
    document.getElementById("manage-branch-modal").style.display = "flex";
}

function hideManageBranchModal() {
    document.getElementById("manage-branch-modal").style.display = "none";
}

async function submitManageBranch(e) {
    e.preventDefault();
    const branchName = document.getElementById("manage-branch-name").value;
    const data = {
        hod_name: document.getElementById("manage-branch-hod-name").value,
        hod_username: document.getElementById("manage-branch-hod-username").value,
        hod_password: document.getElementById("manage-branch-hod-password").value
    };
    
    try {
        const res = await fetch(`${API_BASE_URL}/admin/branches/${encodeURIComponent(branchName)}/hod`, {
            method: "PUT",
            headers: { 
                "Authorization": `Bearer ${currentToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        });
        const resData = await res.json();
        if(res.ok) {
            alert(resData.message);
            hideManageBranchModal();
            fetchBranches();
        } else {
            alert(resData.detail || "Update failed");
        }
    } catch (err) {
        console.error(err);
        alert("Error updating branch.");
    }
}
