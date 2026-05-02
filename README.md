# GPH Automated Fine System (Mark1)

A professional, enterprise-grade Student Management, Attendance, and Clearance System built with FastAPI, PostgreSQL (Supabase), and a modern dynamic frontend. This platform fully digitizes academic operations, fee management, and departmental clearance workflows.

## 🌟 Key Features & Workflows

### 1. Role-Based Access & Dashboards
The system implements a rigid role-based access control (RBAC) mechanism using JWT tokens.
- **Admin**: Has overarching control. Can manage branches, oversee all fines, view global analytics, process overall clearances, and manage faculty accounts.
- **HOD (Head of Department)**: Manages branch-specific analytics, approves clearance requests for their department, and views branch-specific default students.
- **Class Incharge**: Manages student attendance, views analytics for their specific assigned class, and handles day-to-day class administration.
- **Faculty**: Can upload attendance, view student lists, and participate in the clearance approval chain.
- **Students**: Can log in to view their current fine status, check their attendance, pay fines via Razorpay, and apply for final clearance.

### 2. AI-Powered Attendance Extraction (Vision OCR)
Instead of manually typing attendance, faculty can upload a photo of the physical attendance register.
- **Provider**: Uses **OpenRouter API** to access state-of-the-art multimodal Vision Models (e.g., `nvidia/nemotron-nano-12b-v2-vl`).
- **Deterministic Extraction**: The AI is strictly prompted (`temperature: 0.1`) to act as a data extraction agent. It analyzes complex register tables, identifies the "Student Name", and scans the specific column for "Total Attended Classes".
- **Resilient Pipeline**: The backend handles the base64 image encoding and features an exponential backoff retry mechanism (to handle API rate limits).
- **Automated Formatting**: Uses robust Regex fallbacks to strip Markdown artifacts (````json`) from the AI's response, guaranteeing a pure JSON array is ingested into the PostgreSQL database.

### 3. Automated Academic Session Management
The application operates entirely dynamically based on the current calendar date, eliminating manual configuration between semesters:
- **Month-Aware Logic**: 
  - **Even Semesters** (2, 4, 6) automatically activate from January to June.
  - **Odd Semesters** (1, 3, 5) automatically activate from August to December.
- **Branch-Specific Role Segmentation**: 
  - The `First Year` branch HOD automatically only sees/manages data for semesters 1 and 2.
  - Core Department HODs automatically manage data for semesters 3, 4, 5, and 6.
- The Admin & HOD dashboards calculate the intersection of the current month and the assigned branch to dynamically render only the currently active, relevant student populations.

### 4. Automated Fine Management & Secure Payment Gateway
- Fines are automatically calculated based on attendance percentages and disciplinary records.
- Students with fines are marked as "Defaulters".
- **Zero-Fine Automatic Bypass**: If a student has perfect attendance/no disciplinary issues and their fine is uploaded as `0`, the system automatically bypasses the payment gateway entirely. It immediately marks their fine as `Paid` with an internal transaction ID of `ZERO_FINE`, allowing them to instantly qualify for clearance.
- **Razorpay Integration Engine**:
  - **Order Creation**: The backend generates a secure Razorpay Order ID when a student initiates payment, guaranteeing precise transaction amounts.
  - **Secure Checkout**: Students complete payments directly from their dashboard using the native Razorpay UI widget (Cards, UPI, Netbanking).
  - **Cryptographic Webhooks**: The system listens on `/api/webhooks/razorpay`. Upon a successful `payment.captured` event, the backend cryptographically verifies the `X-Razorpay-Signature` against the backend webhook secret to prevent spoofing.
  - **Automated Workflow**: Once verified, the system automatically:
    1. Updates the fine database status to `Paid` with the live transaction ID.
    2. Instantly updates the student's academic status to `Cleared` if there are no other dues.
    3. Triggers an automated HTML email receipt sent directly to the student's inbox.

### 5. Bulk Admit Card Distribution
Admit cards are fully digitized and tied directly to the clearance status.
- **Archive Parsing**: Admins upload a single massive `.zip` archive containing the admit card PDFs for thousands of students. The backend automatically extracts, validates, and routes the individual PDFs to secure static storage.
- **Conditional Access**: A student can only view and download their admit card from their dashboard **if and only if** their status is `Cleared` (meaning they have zero fines or have successfully paid their dues and passed the multi-tier clearance).

### 6. Multi-Tier Clearance System
A fully digitized "No Dues" process.
- Students initiate a clearance request from their dashboard.
- **Tier 1 (Faculty)**: Verifies no pending library/lab dues.
- **Tier 2 (HOD)**: Verifies departmental compliance.
- **Tier 3 (Admin)**: Verifies overall academic compliance and issues final clearance.

### 7. High-Performance Caching
To ensure the dashboard loads instantly even with thousands of students:
- Utilizes `cachetools` for in-memory Time-To-Live (TTL) caching on the server side.
- Complex database aggregations (like total branch fines, attendance averages) are cached for 5 minutes, significantly reducing PostgreSQL query load and latency.

### 8. Relational Database Architecture (PostgreSQL)
The backend is driven by a highly normalized, production-grade **Supabase PostgreSQL** database.
- **Data Integrity via ENUMs**: Utilizes native Postgres ENUMs for strict constraint checking on fields like `faculty_role`, `student_status`, `request_status`, and `group_type` to prevent invalid data entries.
- **Relational Mapping & Cascades**: Fully relational architecture mapping `students` to `branches`, `fines`, and `subject_attendance`. Enforces `ON DELETE CASCADE` rules so that removing a student automatically wipes their associated fines and clearance requests to prevent orphaned records.
- **Connection Pooling**: Uses SQLAlchemy's optimized connection pooling (`pool_size=10`, `max_overflow=20`, `pool_recycle=300`) to maintain robust, persistent connections to Supabase and handle high-traffic serverless bursts seamlessly without connection exhaustion.

#### Database Tables & Keys Overview
1. **`students`**
   - **Primary Key**: `roll_no` (String)
   - **Foreign Keys**: `class_incharge_id` → `faculty(id)`, `hod_id` → `faculty(id)`
   - *Key fields*: `branch`, `semester`, `academic_year`, `attendance metrics`, `status`
2. **`faculty`**
   - **Primary Key**: `id` (Integer)
   - *Key fields*: `role` (ENUM), `branch`, `username`, `password` (Hashed)
3. **`fines`**
   - **Primary Key**: `id` (Integer)
   - **Foreign Key**: `roll_no` → `students(roll_no)` *(ON DELETE CASCADE)*
   - *Key fields*: `amount`, `semester`, `status` (ENUM), `transaction_id`
4. **`requests`** (Clearance Applications)
   - **Primary Key**: `id` (Integer)
   - **Foreign Keys**: `roll_no` → `students(roll_no)` *(ON DELETE CASCADE)*, `faculty_id` → `faculty(id)`
   - *Key fields*: `status` (ENUM), `note`, `request_date`
5. **`subject_attendance`**
   - **Primary Key**: `id` (Integer)
   - **Foreign Key**: `uploaded_by` → `faculty(id)`
   - *Key fields*: `roll_no`, `subject_name`, `group_type` (ENUM), `attended_classes`, `upload_session_id`
6. **`subjects`**
   - **Primary Key**: `id` (Integer)
   - *Key fields*: `semester`, `name`, `group_type`, `branch`
7. **`branches`**
   - **Primary Key**: `id` (Integer)
   - *Key fields*: `name` (Unique)

### 9. Robust Internet Security
The application is fortified against common web vulnerabilities and internet threats through a layered security architecture:
- **Authentication & Encryption**: Uses stateless **JWT (JSON Web Tokens)** for session management and **Bcrypt** for mathematically irreversible password hashing. Passwords are never stored in plaintext.
- **Content Security Policy (CSP)**: A strict middleware whitelist that strictly controls which external scripts and assets (like Razorpay and FontAwesome) are allowed to load. This serves as the primary defense against advanced Cross-Site Scripting (XSS) and data injection attacks.
- **HTTP Security Headers**: Implements comprehensive security headers via custom FastAPI middleware:
  - `Strict-Transport-Security (HSTS)`: Forces all browser connections over secure HTTPS to prevent Man-In-The-Middle (MITM) downgrade attacks.
  - `X-Frame-Options: DENY`: Prevents the application from being embedded in hidden iframes, neutralizing Clickjacking attacks.
  - `X-Content-Type-Options: nosniff`: Prevents browsers from guessing file types, stopping MIME-sniffing vulnerabilities.
- **Cross-Origin Resource Sharing (CORS)**: Strictly limits API interaction to authorized frontends.
- **Rate Limiting**: Integrated dependency (`slowapi`) prepared to prevent DDoS and brute-force login attempts.

## 🛠️ Technology Stack

- **Backend:** Python 3.9+, FastAPI, SQLAlchemy ORM
- **Database:** PostgreSQL (Hosted on Supabase)
- **Frontend:** HTML5, Vanilla CSS3 (Custom Glassmorphism Design System), Vanilla JavaScript
- **Caching:** In-memory TTL Caching (`cachetools`)
- **Serverless Adapter:** Mangum (for Netlify/AWS Lambda deployment)
- **Authentication:** JWT (JSON Web Tokens) with Bcrypt password hashing
- **File Parsing:** `pdfplumber` and `pandas` for bulk data uploads (Excel/PDF)

## 📁 Detailed Project Structure

- `app/` - Core FastAPI backend.
  - `models/` - SQLAlchemy Database Schemas (`student.py`, `faculty.py`, `fine.py`, `branch.py`, `attendance.py`, `request.py`, `subject.py`).
  - `routes/` - REST API Endpoints segregated by entity (`admin.py`, `auth.py`, `faculty.py`, `student.py`, `ai_extraction.py`, `payment.py`).
  - `services/` - Core Business Logic, complex queries, and caching mechanisms.
  - `schemas/` - Pydantic validation models ensuring strict data integrity between frontend and backend.
  - `middleware/` - Custom middlewares handling CORS, Content Security Policies (CSP), and JWT validation.
  - `database.py` - SQLAlchemy Engine configuration tailored for Supabase connection pooling.
  - `config.py` - Environment variable mapping via `pydantic-settings`.
- `frontend/` - Static UI files. Features modular JavaScript files for each dashboard, custom CSS variables for theming, and responsive flexbox layouts.
- `netlify/functions/` - Contains `api.py`, the Mangum wrapper that translates AWS Lambda events into ASGI requests for FastAPI.
- `netlify.toml` - Netlify build configuration. Instructs Netlify to serve `frontend/` statically and proxy all `/api/*` requests to the Python serverless function.

## 🚀 Deployment Instructions (Netlify)

This application is fully configured for a Serverless deployment on Netlify. It avoids long-running server costs by spinning up instances only when requests are made.

1. **Version Control**: Push the entire repository to GitHub.
2. **Netlify Setup**: Log into Netlify and click "Add new site" -> "Import an existing project" -> Select your GitHub repository.
3. **Environment Variables**: Navigate to Site Settings -> Environment Variables and add:
   - `DATABASE_URL`: Your Supabase PostgreSQL Connection String (e.g., `postgresql://mark1_admin:...`)
   - `JWT_SECRET_KEY`: A strong, secure secret string
   - `OPENROUTER_API_KEY`: API Key for AI Attendance processing
   - `RAZORPAY_KEY_ID`: Your public Razorpay Key
   - `RAZORPAY_KEY_SECRET`: Your private Razorpay Secret
   - `SMTP_SERVER`, `SMTP_PORT`, `SMTP_PASSWORD`: For email functionality.
4. **Deploy**: Trigger a deployment. Netlify will build the frontend and deploy the FastAPI backend as an AWS Lambda function automatically based on `netlify.toml`.

## 💻 Local Development Setup

1. **Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Mac/Linux
   # or
   .\venv\Scripts\activate   # Windows
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration:**
   Create a `.env` file in the root directory based on the variables listed in the deployment section.

4. **Database Initialization:**
   Ensure your Supabase PostgreSQL instance is running. Run the following command to generate all required tables:
   ```bash
   python -c "from app.database import Base, engine; from app.models.student import Student; from app.models.faculty import Faculty; from app.models.fine import Fine; from app.models.branch import Branch; from app.models.attendance import SubjectAttendance; from app.models.request import Request; from app.models.subject import Subject; Base.metadata.create_all(bind=engine)"
   ```

5. **Run Locally:**
   ```bash
   uvicorn app.main:app --reload
   ```
   The backend will start at `http://localhost:8000`. Open `http://localhost:8000/frontend/login.html` to view the UI.

## 📜 License
[MIT](LICENSE)
