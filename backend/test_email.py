"""
Script de diagnostico SMTP para ASV Kit.
Ejecutar: python test_email.py
      o:  python test_email.py destino@correo.com
"""
import sys, os, smtplib
from email.mime.text import MIMEText

# Leer .env manualmente (evita problemas de encoding con dotenv en consola)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
env = {}
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()

MAIL_SERVER   = env.get('MAIL_SERVER', os.environ.get('MAIL_SERVER', ''))
MAIL_PORT     = int(env.get('MAIL_PORT', os.environ.get('MAIL_PORT', '587')))
MAIL_USE_TLS  = env.get('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USERNAME = env.get('MAIL_USERNAME', os.environ.get('MAIL_USERNAME', ''))
MAIL_PASSWORD = env.get('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD', ''))
MAIL_SENDER   = env.get('MAIL_SENDER', MAIL_USERNAME)

pw_status = '[OK] configurado' if (MAIL_PASSWORD and MAIL_PASSWORD not in ('tu_app_password_sin_espacios', '')) else '[!!] NO configurado'

print("=" * 58)
print("  ASV Kit - Diagnostico de email SMTP")
print("=" * 58)
print(f"  MAIL_SERVER   : {MAIL_SERVER}")
print(f"  MAIL_PORT     : {MAIL_PORT}")
print(f"  MAIL_USE_TLS  : {MAIL_USE_TLS}")
print(f"  MAIL_USERNAME : {MAIL_USERNAME}")
print(f"  MAIL_PASSWORD : {pw_status}")
print(f"  MAIL_SENDER   : {MAIL_SENDER}")
print("-" * 58)

# Validaciones
issues = []
if not MAIL_SERVER:
    issues.append("MAIL_SERVER esta vacio")
if MAIL_USERNAME in ('', 'tu_correo@gmail.com'):
    issues.append("MAIL_USERNAME no fue configurado (sigue siendo placeholder)")
if MAIL_PASSWORD in ('', 'tu_app_password_sin_espacios'):
    issues.append("MAIL_PASSWORD no fue configurado (sigue siendo placeholder)")

if issues:
    print("\n[ERROR] Problemas encontrados en .env:")
    for issue in issues:
        print(f"   - {issue}")
    print("\n[ACCION] Edita backend/.env con tus credenciales reales y reinicia el servidor.")
    print("\n  Para Gmail:")
    print("  1. Activa 2FA: https://myaccount.google.com/security")
    print("  2. Crea App Password: https://myaccount.google.com/apppasswords")
    print("  3. Pega los 16 caracteres en MAIL_PASSWORD del .env")
    sys.exit(1)

# Intentar conexion real
dest = sys.argv[1] if len(sys.argv) > 1 else MAIL_USERNAME
print(f"\n[ENVIANDO] Email de prueba a: {dest}")

try:
    body = "<h2>ASV Kit SMTP OK</h2><p>Correo de prueba del sistema de diagnostico.</p>"
    msg = MIMEText(body, 'html', 'utf-8')
    msg['Subject'] = 'ASV Kit - Prueba de email SMTP'
    msg['From']    = MAIL_SENDER
    msg['To']      = dest

    print(f"  Conectando a {MAIL_SERVER}:{MAIL_PORT} (TLS={MAIL_USE_TLS})...")

    if MAIL_USE_TLS:
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=15)

    print("  Autenticando...")
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    print("  Enviando mensaje...")
    server.sendmail(MAIL_SENDER, [dest], msg.as_string())
    server.quit()

    print("\n[OK] Email enviado exitosamente!")
    print(f"     Revisa la bandeja de {dest} (incluyendo spam).")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n[ERROR] Fallo de autenticacion: {e}")
    print("\n  Para Gmail con App Password:")
    print("  1. Ve a: https://myaccount.google.com/apppasswords")
    print("  2. Genera una App Password (16 caracteres SIN espacios)")
    print("  3. Coloca esos 16 caracteres exactos en MAIL_PASSWORD del .env")
    print("  NOTA: La contrasena normal de Gmail NO funciona, necesitas App Password")

except smtplib.SMTPConnectError as e:
    print(f"\n[ERROR] No se pudo conectar al servidor SMTP: {e}")
    print("  Verifica MAIL_SERVER y MAIL_PORT en el .env")

except smtplib.SMTPException as e:
    print(f"\n[ERROR] Error SMTP: {e}")

except Exception as e:
    print(f"\n[ERROR] Error inesperado: {type(e).__name__}: {e}")
