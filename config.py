import os

class Config:
    """Configuración profesional con variables de entorno."""
    # 1. Credenciales de Meta
    WA_TOKEN = os.environ.get('WHATSAPP_TOKEN', 'EAAKzjv2Ge8YBQ8agFuZAc1fnJESl49Pxsku320zAGx6XJxYAk6IZA8ommyxvtawfR7JZAhbhEgYNvJfP3kL1rCm55ZAJZBMpGRfBxLb7pv0CLWiWXELfTgINNaXV42HpCPsRT6pL7HbWOQMn6PEUZBjEM0oTFaMKSEUQDAtyQsjOfUQ2ZBDtqcpBf82clgMTarHV0NFrKNuEO6ak2tZCefUIF7T3ZBJA3ZBTZCuZBJSpUFV91ZB8gp2TqcUqGAuz5sadLMyvN45y2As10LwO2KsyQrdrLpgZDZD')
    WA_PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '1077626325424911')
    
    # 2. Base de Datos (SQLite local / PostgreSQL en Render)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///metapython.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 3. Webhook
    WEBHOOK_VERIFY_TOKEN = 'ANDERCODE'