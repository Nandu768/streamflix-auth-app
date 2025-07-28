from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_number = os.getenv('TWILIO_PHONE_NUMBER')

print(f"Twilio Config: {'Set' if all([account_sid, auth_token, twilio_number]) else 'Not set'}")

try:
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body="Test SMS from StreamFlix",
        from_=twilio_number,
        to="+919876543210"  # Replace with your phone number
    )
    print(f"✅ SMS sent successfully with SID: {message.sid}")
except Exception as e:
    print(f"❌ Error: {e}")