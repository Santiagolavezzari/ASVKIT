import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from models import Device

codes = ["A1B2", "C3D4", "E5F6", "G7H8", "I9J0"]

with app.app_context():
    for code in codes:
        existing = Device.query.filter_by(code=code).first()
        if existing:
            print(f"El dispositivo '{code}' ya existe.")
        else:
            new_device = Device(
                name=f"ESP32-{code}",
                code=code,
                is_registered=False,
                user_id=None
            )
            db.session.add(new_device)
            print(f"Cargado: {code}")
    db.session.commit()
    print("Listo. Se cargaron los códigos.")
