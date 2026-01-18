# notifications.py - wysyłanie powiadomień email

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECEIVER
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP("smtp.mailgun.org", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)

        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:
        print(f"Błąd wysyłania email: {e}")
        return False

def notify_new_kpo(kpo_list):
    """Wysyła powiadomienie o nowych KPO"""
    
    if not kpo_list:
        return
    
    subject = f"BDO: {len(kpo_list)} nowych KPO do zatwierdzenia"
    
    body = "Nowe karty przekazania odpadów:\n\n"
    for kpo in kpo_list:
        body += f"- {kpo['cardNumber']}\n"
        body += f"  Odpad: {kpo['wasteCode']} - {kpo['wasteCodeDescription']}\n"
        body += f"  Od: {kpo['senderName']}\n"
        body += f"  Data: {kpo['realTransportTime']}\n\n"
    
    body += "Zaloguj się do aplikacji aby zatwierdzić."
    
    send_email(subject, body)