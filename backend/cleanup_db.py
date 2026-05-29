import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from models import Device, User

def cleanup_orphans():
    with app.app_context():
        # Encontrar dispositivos registrados que apuntan a usuarios que ya no existen
        devices = Device.query.all()
        fixed = 0
        
        for d in devices:
            if d.is_registered:
                if d.user_id:
                    user = User.query.get(d.user_id)
                    if not user:
                        print(f"Dispositivo {d.code} asignado a usuario borrado (ID {d.user_id}). Liberando...")
                        d.is_registered = False
                        d.user_id = None
                        fixed += 1
                else:
                    print(f"Dispositivo {d.code} marcado como registrado pero sin user_id. Liberando...")
                    d.is_registered = False
                    fixed += 1
            else:
                # Si no está registrado, asegurarse que no tenga user_id colgado
                if d.user_id is not None:
                    d.user_id = None
                    fixed += 1

        db.session.commit()
        print(f"Finalizado. Se arreglaron {fixed} dispositivos huérfanos.")

if __name__ == '__main__':
    cleanup_orphans()
