# GPH Automated Fine System (Mark1)

A professional Attendance Management and Fine System built with FastAPI, MySQL, and a modern frontend.

## Features
- **AI-Powered Attendance Extraction**: Automatically extract attendance data from register images.
- **Role-Based Dashboards**: Separate interfaces for Admin, HOD, Faculty, Incharge, and Students.
- **Fine Management**: Automated fine calculation and tracking.
- **Payment Integration**: Secure payment processing (Razorpay).
- **Responsive UI**: Modern, dynamic design with Font Awesome icons.

## Tech Stack
- **Backend**: Python 3.9+, FastAPI
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript
- **Database**: MySQL
- **OCR/AI**: OpenRouter (Gemini models)
- **Containerization**: Docker & Docker Compose

## Setup Instructions

### Prerequisites
- Docker & Docker Compose
- Python 3.9+ (for local development)

### Environment Configuration
1. Create a `.env` file in the root directory.
2. Add the following variables:
   ```env
   DATABASE_URL=mysql+aiomysql://user:password@db:3306/attendance_db
   OPENROUTER_API_KEY=your_key_here
   RAZORPAY_KEY_ID=your_key_here
   RAZORPAY_KEY_SECRET=your_key_here
   ```

### Running with Docker
```bash
docker-compose up --build
```

### Local Development
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Mac/Linux
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Project Structure
- `app/`: Backend logic (routes, services, models).
- `frontend/`: UI components and assets.
- `docker-compose.yml`: Container orchestration.
- `requirements.txt`: Python dependencies.

## License
[MIT](LICENSE)
