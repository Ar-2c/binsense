# mailer.py
import os, smtplib, ssl
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')

def _smtp_settings():
    host = os.getenv('SMTP_HOST')
    port = int(os.getenv('SMTP_PORT', '587'))
    user = os.getenv('SMTP_USER')
    pwd = os.getenv('SMTP_PASS')
    if not all([host, port, user, pwd]):
        raise RuntimeError('Saknar SMTP_* i miljön')
    return host, port, user, pwd

def send_email(
        subject: str,
        body: str,
        to: Iterable[str],
        attachments: Optional[Iterable[Tuple[str, bytes, str]]] = None,  # (filename, bytes, mime)
        sender: Optional[str] = None,
):
    host, port, user, pwd = _smtp_settings()
    sender = sender or user

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    msg.set_content(body)

    for att in (attachments or []):
        fname, blob, mime = att
        maintype, subtype = mime.split('/', 1)
        msg.add_attachment(blob, maintype=maintype, subtype=subtype, filename=fname)

    context = ssl.create_default_context()
    
    
    if port == 465:
    # Ren SSL från start (ingen starttls)
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as s:
            s.login(user, pwd)
            s.send_message(msg)
    else:
    # STARTTLS (t.ex. 587)
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo()
            s.starttls(context=context)
            s.ehlo()
            s.login(user, pwd)
            s.send_message(msg)