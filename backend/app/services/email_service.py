"""
Email service for sending transactional emails.

Supports multiple email providers:
- SMTP (Gmail, custom SMTP)
- SendGrid
- AWS SES (via boto3)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via various providers."""
    
    def __init__(self):
        """Initialize email service based on configuration."""
        self.provider = settings.EMAIL_PROVIDER.lower() if hasattr(settings, 'EMAIL_PROVIDER') else 'smtp'
        self.from_email = getattr(settings, 'EMAIL_FROM', 'noreply@grantpool.org')
        self.from_name = getattr(settings, 'EMAIL_FROM_NAME', 'GrantPool')
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if self.provider == 'sendgrid':
                return self._send_via_sendgrid(to_email, subject, html_content, text_content)
            elif self.provider == 'ses':
                return self._send_via_ses(to_email, subject, html_content, text_content)
            else:  # Default to SMTP
                return self._send_via_smtp(to_email, subject, html_content, text_content)
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email via SMTP."""
        smtp_host = getattr(settings, 'SMTP_HOST', 'smtp.gmail.com')
        smtp_port = getattr(settings, 'SMTP_PORT', 587)
        smtp_user = getattr(settings, 'SMTP_USER', '')
        smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        smtp_use_tls = getattr(settings, 'SMTP_USE_TLS', True)
        
        if not smtp_user or not smtp_password:
            logger.error("SMTP credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"SMTP email send failed: {str(e)}")
            return False
    
    def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email via SendGrid."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            
            sendgrid_api_key = getattr(settings, 'SENDGRID_API_KEY', '')
            if not sendgrid_api_key:
                logger.error("SendGrid API key not configured - SENDGRID_API_KEY environment variable is empty or missing")
                return False
            
            # Log configuration check (without exposing key)
            logger.info(f"SendGrid: Sending email to {to_email} from {self.from_email} (provider: {self.provider})")
            
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            if text_content:
                message.plain_text_content = text_content
            
            sg = SendGridAPIClient(sendgrid_api_key)
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"SendGrid email sent successfully to {to_email} (status: {response.status_code})")
                return True
            else:
                # Log detailed error information
                error_body = ""
                try:
                    error_body = response.body.decode('utf-8') if response.body else "No error body"
                except:
                    error_body = str(response.body) if response.body else "No error body"
                
                logger.error(
                    f"SendGrid email send failed to {to_email}: "
                    f"status_code={response.status_code}, "
                    f"headers={dict(response.headers) if hasattr(response, 'headers') else 'N/A'}, "
                    f"body={error_body}"
                )
                return False
                
        except ImportError:
            logger.error("SendGrid library not installed. Install with: pip install sendgrid")
            return False
        except Exception as e:
            import traceback
            logger.error(
                f"SendGrid email send failed to {to_email}: {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            return False
    
    def _send_via_ses(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email via AWS SES."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            aws_region = getattr(settings, 'AWS_REGION', 'us-east-1')
            aws_access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', '')
            aws_secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', '')
            
            if not aws_access_key or not aws_secret_key:
                logger.error("AWS credentials not configured")
                return False
            
            ses_client = boto3.client(
                'ses',
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            
            message = {
                'Subject': {'Data': subject},
                'Body': {
                    'Html': {'Data': html_content}
                }
            }
            
            if text_content:
                message['Body']['Text'] = {'Data': text_content}
            
            response = ses_client.send_email(
                Source=f"{self.from_name} <{self.from_email}>",
                Destination={'ToAddresses': [to_email]},
                Message=message
            )
            
            logger.info(f"AWS SES email sent successfully to {to_email}")
            return True
            
        except ImportError:
            logger.error("boto3 library not installed. Install with: pip install boto3")
            return False
        except ClientError as e:
            logger.error(f"AWS SES email send failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"AWS SES email send failed: {str(e)}")
            return False


def send_password_reset_email(email: str, reset_token: str, reset_url: Optional[str] = None) -> bool:
    """
    Send password reset email.
    
    Args:
        email: User's email address
        reset_token: Password reset token
        reset_url: Optional full reset URL (if not provided, will use APP_URL)
        
    Returns:
        True if email sent successfully, False otherwise
    """
    app_url = getattr(settings, 'APP_URL', 'http://localhost:3000')
    if not reset_url:
        reset_url = f"{app_url}/forgot-password?token={reset_token}&email={email}"
    
    subject = "Reset Your GrantPool Password"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{ display: inline-block; padding: 12px 24px; background-color: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Reset Your Password</h2>
            <p>You requested to reset your password for your GrantPool account.</p>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_url}" class="button">Reset Password</a>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #667eea;">{reset_url}</p>
            <p><strong>This link will expire in 1 hour.</strong></p>
            <p>If you didn't request this password reset, please ignore this email.</p>
            <div class="footer">
                <p>GrantPool - Decisive grant triage system</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Reset Your GrantPool Password
    
    You requested to reset your password for your GrantPool account.
    
    Click the link below to reset your password:
    {reset_url}
    
    This link will expire in 1 hour.
    
    If you didn't request this password reset, please ignore this email.
    
    GrantPool - Decisive grant triage system
    """
    
    email_service = EmailService()
    return email_service.send_email(email, subject, html_content, text_content)













