# RoadSense: Smart Road Infrastructure Monitoring & Reward System

RoadSense is a unified civic-tech platform designed to report, validate, and manage road infrastructure issues (such as potholes and road damage) through citizen participation, automated AI verification, and government collaboration.

---

## 🚀 Key Features

### 1. Citizen Portal & Reporting
- **Interactive Reporting:** Citizens can report issues with descriptions, GPS coordinates (latitude and longitude), and image uploads.
- **Rewarding System:** Citizens earn points (coins) for valid, unique reports. 
- **Fastag Redemption:** Earned coins can be redeemed for real-world Fastag balance top-ups.
- **Geo-Lock Anti-Fraud:** Prevents spam and double-reporting by checking for duplicate reports within a 10-meter radius in the last 24 hours.

### 2. AI & Image Processing
- **YOLOv8 Object Detection:** Uses a custom YOLO model (`best.pt`) to automatically verify the existence of road damage in submitted images.
- **Adaptive Detection Thresholds:** Performs automated validation checks and falls back to dynamic thresholds to reduce false rejections for low-light or angled photos.
- **CCTV Stream Simulation:** Simulates public/government CCTV monitoring, scanning video frames periodically to flag road issues autonomously.

### 3. AI Support Chatbot
- **Gemini-Powered Chatbot:** Integrates Google's Gemini API (`gemini-1.5-pro-latest`) to answer citizen questions about the platform, issue status, and fastag rewards.
- **Robust Exception Handling:** Ensures continuous chatbot operation with automated fallback messages for API limits or connection errors.

### 4. Admin & Worker Workflow
- **Admin Dashboard:** Central console for administrators to view system statistics, monitor CCTV alerts, approve Fastag redemption requests, and assign issues to workers.
- **Worker Portal:** Allows ground teams to view assigned issues, update work progress, upload verification photos of the completed work, and mark issues as resolved.

---

## 🛠️ Technology Stack

- **Backend:** Flask, Flask-SQLAlchemy, Flask-Bcrypt, Flask-Login
- **Frontend:** Vanilla HTML5, Modern CSS3 (Variables, CSS-Grid, Flexbox), JavaScript
- **AI/ML:** Ultralytics YOLOv8, OpenCV, Google Generative AI (Gemini)
- **Database:** SQLite (Default)

---

## 📁 Repository Structure

```text
├── frontend/                     # Frontend Assets and Views
│   ├── index.html                # Main System Dashboard
│   ├── login.html                # User login page
│   ├── report.html               # Issue Reporting Page (Citizen View)
│   ├── user.html                 # Citizen Dashboard & Wallet View
│   ├── worker.html               # Worker Task Board
│   ├── admin.html                # Administrative View & User management
│   ├── app.js                    # Core frontend logic & API requests
│   ├── app.css                   # Global styles
│   └── style.css                 # Layout and portal specific styles
├── static/                       # Static folder (Flask)
├── templates/                    # Jinja2 template folder
├── uploads/                      # Uploaded issue images folder
├── app.py                        # Flask Application Factory & Server entry point
├── auth.py                       # User Authentication Blueprints & Logic
├── issues.py                     # Issue Reporting & Management Blueprints
├── rewards.py                    # Coin Rewards & Fastag Redemption system
├── chatbot.py                    # Google Gemini API integration
├── yoloModel.py                  # PotholeSystem YOLO Detector class
├── yolo_validator.py             # Image validation and threshold configuration
├── models.py                     # SQLAlchemy database models
├── db.py                         # SQLAlchemy database initialization
├── seed.py                       # Script to seed default database users
├── requirements.txt              # Project Python Dependencies
└── .env                          # Local Environment Configuration (Ignored by Git)
```

---

## ⚙️ Setup and Installation

### 1. Clone & Navigate to Workspace
```bash
cd issue_reporting_app
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/Scripts/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a file named `.env` in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
FLASK_APP=app.py
FLASK_ENV=development
```

### 5. Seed the Database
Initialize and seed the SQLite database with default roles:
```bash
python seed.py
```

### 6. Run the Application
Start the Flask development server:
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000/` or `http://127.0.0.1:5000/frontend`.

---

## 🔑 Default Credentials

The database seeding script registers three test accounts corresponding to the standard roles in the system:

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| **`admin`** | `admin123` | Admin | Administrative monitoring, CCTV, user management, and payouts. |
| **`user`** | `user123` | Citizen | Report issues, chat with Gemini AI, and redeem Fastag coins. |
| **`worker`** | `worker123` | Worker | View assigned tasks and submit repair resolution reports. |

---

## 🔒 Fraud Prevention & Reward Rules

1. **AI Image Validation:** The uploaded image must show detections of potholes/road damage with a YOLO confidence score above the threshold (`0.25` default, fallback to `0.10`).
2. **Geo-Locking:** The reporting location coordinates (latitude and longitude) must not be within a **10-meter radius** of another reported issue submitted in the last **24 hours**.
3. **Daily Cap:** A citizen can earn rewards for a maximum of **5 reports** per calendar day.
4. **Duplicate File Hash:** Submitting the exact same image file is flagged and does not award coins.
