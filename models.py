# /Users/alejandromeza/WA_BOT_PROJECTN/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telefono = db.Column(db.String(20), unique=True, nullable=False)
    # Datos de Registro
    nombre = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    calle = db.Column(db.String(150))
    numero = db.Column(db.String(20))
    cruzamientos = db.Column(db.String(200))
    referencia = db.Column(db.Text)
    
    paso_actual = db.Column(db.String(50), default="INICIO")
    pedido_temporal = db.Column(db.Text, default='{"pizzas": [], "extras": [], "total": 0}')

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    detalles_json = db.Column(db.Text)
    total = db.Column(db.Float)
    tipo_entrega = db.Column(db.String(20))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    cliente = db.relationship('Cliente', backref='historial')