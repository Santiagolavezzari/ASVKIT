import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


from typing import Any

class Base(DeclarativeBase):
    """Base declarativa tipada — habilita soporte completo de Mapped[T] en Pylance."""
    pass


# ── Instancia global de la Base de Datos SQLAlchemy ──
db = SQLAlchemy(model_class=Base)


# ── Inicializa la Base de Datos con la App de Flask (Se corre al arrancar el servidor) ──
def init_db(app):
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'asvkit.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)


def create_tables(app):
    with app.app_context():
        db.create_all()


# ── Funciones de soporte para el manejo de los Dispositivos Físicos (ESP32) ──

def insert_device(code: str):
    from models import Device
    d = db.session.execute(
        db.select(Device).filter_by(code=code)
    ).scalar_one_or_none()
    if not d:
        d = Device(name=f"ESP32-{code}", code=code)
        db.session.add(d)
        db.session.commit()
    return d


def get_device_by_code(code: str):
    from models import Device
    return db.session.execute(
        db.select(Device).filter_by(code=code)
    ).scalar_one_or_none()


# ── Vincula un usuario del sistema (login) con su receptor (ESP32) físico ──
def link_user_to_device(user, device) -> None:
    device.is_registered = True
    device.user_id = user.id
    user.device_id = device.id
    db.session.commit()