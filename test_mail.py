# test_mail.py
import os
from mailer import send_email

# Läs in miljövariabler (om du använder python-dotenv)
from dotenv import load_dotenv
load_dotenv()

# Testdata
subject = "📬 Test från Binsense mailer"
body = (
    "Hej!\n\n"
    "Detta är ett testmail från ditt Python-script.\n"
    "Om du ser detta så fungerar SMTP-inställningarna som de ska!\n\n"
    "— Binsense"
)

recipient = os.getenv("SMTP_USER")  # skicka till dig själv
send_email(subject, body, [recipient])

print("✅ Testmejl skickat till", recipient)