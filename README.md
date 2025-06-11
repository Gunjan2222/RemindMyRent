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
    MAIL_USERNAME=your_email@gmail.com
    MAIL_PASSWORD=your_email_password_or_app_password

    TWILIO_ACCOUNT_SID=your_twilio_sid
    TWILIO_AUTH_TOKEN=your_twilio_token
    TWILIO_PHONE_NUMBER=your_twilio_number

5. **Run database migrations**
    ```bash
    flask db init
    flask db migrate
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

1. ✅ **Health Check**
   *GET /*
   
   Description: Basic endpoint to confirm the server is running.
   
   Response:
   
   ```text
   Server is running!
   ```

2. ➕ **Add Rent Reminder**
   *POST /add_reminder*
   
   Description: Add a new rent reminder for a tenant.
   
   Request Body (application/json):
   
   ```json
   {
     "tenant_name": "John Doe",
     "email": "john@example.com",
     "rent_date": "2025-07-01",
     "rent_amount": 15000,
     "due_day": 1,  // optional, defaults to 1
     "frequency": "monthly"  // optional, defaults to "monthly"
   }
   ```
   Success Response (201 Created):
   
   ```json
   {
     "message": "Reminder added"
   }
   ```
   
3. 💰 **Record Rent Payment**
   *POST /record_payment*
   
   Description: Record a rent payment made by a tenant.
   
   Request Body (application/json):
   
   ```json
   {
     "tenant_id": 1,
     "payment_date": "2025-07-05",
     "for_month": "2025-07-01",
     "amount_paid": 15000
   }
   ```
   Success Response (201 Created):
   
   ```json
   {
     "message": "Payment recorded"
   }
   ```
   Error Response (404 Not Found):
   
   ```json
   {
     "error": "Tenant not found"
   }
   ```
   
---

## Contact

- *Author:* Gunjan Agarwal
- *Email:* gunagarwal999@gmail.com  
- *GitHub:* Gunjan2222












