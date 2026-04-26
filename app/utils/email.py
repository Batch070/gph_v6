import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings

def _send_email_sync(to_email: str, subject: str, html_content: str):
    """Synchronous function to send email via SMTP."""
    if not settings.SMTP_PASSWORD:
        print(f"[Email Notification Blocked] Password missing. Would have sent to {to_email}: {subject}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USERNAME
        msg["To"] = to_email

        # Attach HTML content
        part = MIMEText(html_content, "html")
        msg.attach(part)

        # Connect to server and send
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USERNAME, to_email, msg.as_string())
        server.quit()
        print(f"[Email Notification Sent] Successfully sent to {to_email}: {subject}")
    except Exception as e:
        print(f"[Email Notification Error] Failed to send email to {to_email}: {str(e)}")

def send_student_notification(to_email: str, subject: str, html_content: str):
    """
    Asynchronously sends an email notification to a student.
    Runs the actual SMTP logic in a separate thread to prevent blocking
    FastAPI routes.
    """
    if not to_email:
        print("[Email Notification Blocked] No recipient email provided.")
        return
        
    thread = threading.Thread(
        target=_send_email_sync, 
        args=(to_email, subject, html_content)
    )
    thread.start()

def get_html_template(title: str, message: str) -> str:
    """Returns a professionally styled HTML template for notifications."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f4f7f6;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background-color: #2c3e50;
                color: #ffffff;
                padding: 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 30px;
                color: #333333;
                line-height: 1.6;
            }}
            .footer {{
                background-color: #f1f1f1;
                color: #777777;
                text-align: center;
                padding: 15px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{title}</h1>
            </div>
            <div class="content">
                {message}
            </div>
            <div class="footer">
                <p>This is an automated notification from the GPH Automated Fine Payment System.</p>
                <p>Please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
