import os

class Config:
    """Configuración base de la aplicación."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'una_clave_secreta_por_defecto_muy_larga')
    
    # URL de la base de datos. En Render para persistencia, usar PostgreSQL.
    # Ejemplo de Render PostgreSQL URI: postgres://usuario:password@host:port/database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///pizzeriabot.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Credenciales de WhatsApp Cloud API - Extraídas de tus imágenes
    # Usamos variables de entorno para no exponer tokens en GitHub.
    WA_TOKEN = os.environ.get('WHATSAPP_TOKEN', 'TU_TOKEN_TEMPORAL_DE_24H_O_PERMANENTE')
    
    # Identificador de número de teléfono: Extraído de image_1.png
    WA_PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '1077626325424911') 
    
    # Identificador de la cuenta de WhatsApp Business: Extraído de image_1.png
    WA_BUSINESS_ACCOUNT_ID = os.environ.get('BUSINESS_ACCOUNT_ID', '1979098879624769')
    
    # Token de verificación para el webhook, configurado en el panel de Meta
    WEBHOOK_VERIFY_TOKEN = 'ANDERCODE'