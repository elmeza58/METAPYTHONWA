import os

class Config:
    """Configuración con respaldo directo para evitar errores de carga."""
    
    # 1. Intenta leer de Render, si no existe, usa el string que pegamos abajo
    WA_TOKEN = os.environ.get('WHATSAPP_TOKEN', 'EAAKzjv2Ge8YBQ8agFuZAc1fnJESl49Pxsku320zAGx6XJxYAk6IZA8ommyxvtawfR7JZAhbhEgYNvJfP3kL1rCm55ZAJZBMpGRfBxLb7pv0CLWiWXELfTgINNaXV42HpCPsRT6pL7HbWOQMn6PEUZBjEM0oTFaMKSEUQDAtyQsjOfUQ2ZBDtqcpBf82clgMTarHV0NFrKNuEO6ak2tZCefUIF7T3ZBJA3ZBTZCuZBJSpUFV91ZB8gp2TqcUqGAuz5sadLMyvN45y2As10LwO2KsyQrdrLpgZDZD')
    
    # 2. Tu ID de teléfono (asegúrate que sea el correcto 1077626325424911)
    WA_PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '1077626325424911')
    
    # 3. Base de datos y Webhook
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///metapython.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WEBHOOK_VERIFY_TOKEN = 'ANDERCODE'