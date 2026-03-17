import os

class Config:
    """Configuración profesional de variables de entorno."""
    # Base de Datos
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///metapython.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Meta API
    # Importante: Asegúrate de que en Render la variable se llame exactamente WHATSAPP_TOKEN
    WA_TOKEN = os.environ.get('WHATSAPP_TOKEN')
    WA_PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '1077626325424911')
    WEBHOOK_VERIFY_TOKEN = 'ANDERCODE'