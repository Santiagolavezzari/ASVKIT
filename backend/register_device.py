import argparse
import sys
import os

# Ajustar path para asegurar que importa backend correctamente
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from models import Device

def main():
    parser = argparse.ArgumentParser(description="Pre-cargar un nuevo dispositivo ESP32 en la base de datos.")
    parser.add_argument("--code", required=True, help="Código único de 4 caracteres del ESP32")
    args = parser.parse_args()

    code = args.code.upper()

    with app.app_context():
        existing = Device.query.filter_by(code=code).first()
        if existing:
            print(f"Error: El dispositivo con código '{code}' ya existe.")
            return

        new_device = Device(
            name=f"ESP32-{code}",
            code=code,
            is_registered=False,
            user_id=None
        )
        db.session.add(new_device)
        db.session.commit()
        print(f"Éxito: Dispositivo '{code}' pre-cargado correctamente en la base de datos (is_registered=0, user_id=NULL).")

if __name__ == "__main__":
    main()
