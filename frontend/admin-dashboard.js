const API_BASE_URL = "/api";
let currentToken = localStorage.getItem("access_token");
let userRole = localStorage.getItem("token_role");

document.addEventListener("DOMContentLoaded", () => {
    if (!currentToken || userRole !== "Admin") {
        alert("Unauthorized access. Redirecting to login...");
        window.location.href = "/";
        return;
    }

    setupEventListeners();
    fetchOverview();
    fetchBranchData();
    fetchStudents();
    fetchFaculty();
    fetchAttendanceInsights();
    fetchDBInsights();
    
    // Add dummy modal for Add Faculty
    createFacultyModal();
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
            tr.innerHTML = `
                <td><strong>${row.department}</strong></td>
                <td>${row.semester}</td>
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
    const depts = new Set();
    const sems = new Set();
    data.forEach(r => {
        depts.add(r.department);
        sems.add(r.semester.replace("th Semester", ""));
    });
    
    const dFilter = document.getElementById("branch-filter-dept");
    depts.forEach(d => {
        if(d) dFilter.innerHTML += `<option value="${d}">${d}</option>`;
    });

    const sFilter = document.getElementById("branch-filter-sem");
    [2, 4, 6].forEach(s => {
        sFilter.innerHTML += `<option value="${s}">${s}th Semester</option>`;
    });
    filtersPopulated = true;
}

async function fetchStudents(search = "") {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/students?search=${search}`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch students");
        const data = await res.json();
        
        const tbody = document.getElementById("admin-students-tbody");
        tbody.innerHTML = "";
        
        if (data.students.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center">No students found.</td></tr>`;
            return;
        }

        data.students.forEach(s => {
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
    } catch (err) {
        console.error(err);
    }
}

async function fetchFaculty() {
    try {
        const res = await fetch(`${API_BASE_URL}/admin/faculty`, {
            headers: { "Authorization": `Bearer ${currentToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch faculty");
        const data = await res.json();
        
        const tbody = document.getElementById("admin-faculty-tbody");
        tbody.innerHTML = "";
        
        data.faculty.forEach(f => {
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
    } catch (err) {
        console.error(err);
    }
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
        
        const grid = document.getElementById("admin-attendance-grid");
        grid.innerHTML = "";
        
        if (data.insights.length === 0) {
            grid.innerHTML = `<p class="no-data">No attendance data available yet.</p>`;
            return;
        }

        data.insights.forEach(insight => {
            const card = document.createElement("div");
            card.className = "semester-card";
            card.innerHTML = `
                <div class="sem-icon"><i class="fa-solid fa-chart-line"></i></div>
                <h3>${insight.branch} - ${insight.semester}th Sem</h3>
                <div style="display:flex; justify-content:space-around; margin-top:10px;">
                    <div style="text-align:center;">
                        <small>Theory</small>
                        <div class="info-value ${insight.theory_avg < 75 ? 'text-red' : 'text-green'}" style="font-size:1.1rem;">${insight.theory_avg}%</div>
                    </div>
                    <div style="text-align:center;">
                        <small>Practical</small>
                        <div class="info-value ${insight.practical_avg < 75 ? 'text-red' : 'text-green'}" style="font-size:1.1rem;">${insight.practical_avg}%</div>
                    </div>
                </div>
                <p style="margin-top:10px; font-size:0.8rem;">Total Students: ${insight.student_count}</p>
            `;
            grid.appendChild(card);
        });
    } catch (err) {
        console.error(err);
    }
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

function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_role");
    window.location.href = "/";
}
