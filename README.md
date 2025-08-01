# RemindMyRent

**RemindMyRent** is a lightweight rent reminder app built with Flask. It automates monthly rent reminders using email and SMS notifications. The app leverages Celery for background task scheduling and integrates with Twilio and Gmail SMTP.

---

## 🚀 Features

- 🔔 Automatic rent reminders on the 1st of every month
- 📧 Email notifications via Gmail SMTP
- 📱 SMS notifications via Twilio
- 🕒 Task scheduling using Celery with Redis
- 📊 Admin panel to manage tenant data (basic)
- 🌐 RESTful API endpoints (Flask-based)
- 🔐 Environment variable support for secure config

---

## 🛠️ Technologies Used

- **Flask** – Lightweight Python web framework
- **Flask-Mail** – Email notifications
- **Twilio API** – SMS notifications
- **Celery** – Asynchronous task scheduler
- **Redis** – Message broker for Celery
- **Flask-Migrate + SQLAlchemy** – Database ORM and migrations

---

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/RemindMyRent.git
   cd RemindMyRent

2. **Create and activate a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

3. **Install dependencies**
    ```bash
    pip install -r requirements.txt

4. **Configure environment variables**
    Create a .env file and add the following:
    ```bash
    SQLALCHEMY_DATABASE_URI=postgresql://postgres:yourpassword@localhost:5432/remindmyrent
    MAIL_USERNAME=your_email@gmail.com
    MAIL_PASSWORD=your_gmail_app_password

    TWILIO_ACCOUNT_SID=your_twilio_sid
    TWILIO_AUTH_TOKEN=your_twilio_token
    TWILIO_PHONE_NUMBER=+911234567890

    JWT_SECRET_KEY=your_super_secret_key

5. **Run database migrations**
    ```bash
    flask db init
    flask db migrate -m "Initial DB"
    flask db upgrade

6. **Run Redis server**
    ```bash
    redis-server

7. **Start Celery worker**
    ```bash
    celery -A celery_worker.celery worker --loglevel=info

8. **Start Celery beat**
    ```bash
    celery -A celery_beat.celery beat --loglevel=info

9. **Run Flask server**
    ```bash
    flask run

---

## 🔌 API Endpoints

### ✅ Authentication

| Endpoint           | Method | Description              |
|--------------------|--------|--------------------------|
| `/register`        | POST   | Register a new user      |
| `/login`           | POST   | Login and receive tokens |
| `/refresh`         | POST   | Refresh access token     |
| `/logout`          | POST   | Revoke access token      |
| `/logout-refresh`  | POST   | Revoke refresh token     |


## 📋 Rent Reminder

### ➕ Add Reminder

**POST** `/add_reminder`

#### Request Body
```json
{
  "tenant_name": "John Doe",
  "email": "john@example.com",
  "rent_date": "2025-07-01",
  "rent_amount": 15000,
  "due_day": 1,
  "frequency": "monthly"
}
```

#### ✅ Success Response
```json
{ "message": "Reminder added" }
```

### 💵 Record Rent Payment
**POST** `/record_payment`

#### Request Body
```json
{
  "tenant_id": 1,
  "payment_date": "2025-07-05",
  "for_month": "2025-07-01",
  "amount_paid": 15000
}
```

#### ✅ Success Response
```json
{ "message": "Payment recorded" }
```

#### ❌ Error
```json
{ "error": "Tenant not found or unauthorized" }
```
 
---

## Contact

- *Author:* Gunjan Agarwal
- *Email:* gunagarwal999@gmail.com  
- *GitHub:* Gunjan2222












