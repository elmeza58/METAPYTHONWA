from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Cliente(db.Model):
    """Almacena datos del cliente y su estado de conversación."""
    id = db.Column(db.Integer, primary_key=True)
    telefono = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100))
    ultima_direccion = db.Column(db.Text)
    
    # --- NUEVOS CAMPOS PARA PERSISTENCIA ---
    paso_actual = db.Column(db.String(50), default="INICIO")
    pedido_temporal = db.Column(db.Text, default='{"ingredientes": [], "extras": [], "total": 0}')

class Pedido(db.Model):
    """Registro histórico de ventas finalizadas."""
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    detalles_json = db.Column(db.Text)
    total = db.Column(db.Float)
    tipo_entrega = db.Column(db.String(20))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    cliente = db.relationship('Cliente', backref='pedidos_historial')