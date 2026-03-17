from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Cliente(db.Model):
    """Modelo para guardar la información del cliente y personalizar la atención."""
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True)
    telefono = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(100))
    ultima_direccion = db.Column(db.Text)
    pedidos = db.relationship('Pedido', backref='cliente', lazy=True)

class Pedido(db.Model):
    """Modelo principal del pedido."""
    __tablename__ = 'pedidos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 'domicilio' o 'recogida'
    tipo_entrega = db.Column(db.String(20), nullable=False) 
    
    # Estado del pedido: 'solicitado', 'confirmado', 'en_cocina', 'en_camino', 'entregado', 'cancelado'
    estado = db.Column(db.String(50), default='solicitado')
    
    direccion_entrega = db.Column(db.Text)
    costo_total = db.Column(db.Float, nullable=False)
    
    # Tiempo estimado en minutos: 40 por defecto
    tiempo_estimado = db.Column(db.Integer, default=40)
    
    # Guardamos los items del pedido como JSON para flexibilidad inicial
    items_json = db.Column(db.Text, nullable=False) 

    @property
    def items(self):
        """Deserializa los items del pedido para facilitar su uso."""
        return json.loads(self.items_json) if self.items_json else []