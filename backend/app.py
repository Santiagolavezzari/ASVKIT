from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from database import db, init_db, insert_device, get_device_by_code, link_user_to_device
from models import SensorNode, Alert, Device, User
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import func
from dotenv import load_dotenv
import logging
import os
import re

# Cargar variables de entorno desde backend/.env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# ── App Setup ─────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('ASVKIT_SECRET', 'asvkit-secret-2024')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# Timeout de 30s para evitar "database is locked" con SQLite
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'timeout': 30}}

# ── Flask-Mail config (Mailtrap por defecto; cambiá por tus datos SMTP) ──
app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER',   'sandbox.smtp.mailtrap.io')
app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', '2525'))
app.config['MAIL_USE_TLS']  = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')   # pon tu user Mailtrap
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')   # pon tu pass Mailtrap
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_SENDER', 'no-reply@asvkit.com')
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')

mail = Mail(app)

CORS(app, supports_credentials=True, origins=[
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "http://localhost",
    "http://localhost:80",
    "http://127.0.0.1",
    "http://127.0.0.1:80",
    "null",  # file:// protocol origin
])
init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')

# ── Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('asvkit')


def _now() -> datetime:
    """Retorna datetime UTC naive (compatible con SQLite y sin DeprecationWarning)."""
    return datetime.utcnow()  # noqa: DTZ003

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'No autenticado'}), 401

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Acceso denegado'}), 403
        return f(*args, **kwargs)
    return decorated

# ── Rutas de Autenticación (Login, Registro, Recuperación de contraseña, Verificación de mail) ──

@app.route('/register', methods=['GET'])
def register_page():
    return send_from_directory(BASE_DIR, 'register.html')

@app.route('/register', methods=['POST'])
def register_api():
    try:
        data = request.get_json()
        if not data or not data.get('username') or not data.get('email') or not data.get('password') or not data.get('code'):
            return jsonify({'error': 'Faltan campos obligatorios'}), 400
            
        if len(data['password']) < 8:
            return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
        if not re.search(r'[A-Z]', data['password']):
            return jsonify({'error': 'La contraseña debe contener al menos una letra mayúscula'}), 400
        if not re.search(r'[0-9]', data['password']):
            return jsonify({'error': 'La contraseña debe contener al menos un número'}), 400
            
        if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
            return jsonify({'error': 'El correo electrónico no tiene un formato válido'}), 400
        
        if db.session.execute(db.select(User).filter_by(username=data['username'])).scalar_one_or_none():
            return jsonify({'error': 'El usuario ya existe'}), 400
            
        if db.session.execute(db.select(User).filter_by(email=data['email'])).scalar_one_or_none():
            return jsonify({'error': 'El correo ya está registrado'}), 400
            
        code_upper = data['code'].upper()
        device = get_device_by_code(code_upper)
        
        if not device:
            return jsonify({'error': 'Código de dispositivo no encontrado'}), 404
            
        if device.is_registered:
            return jsonify({'error': 'Este dispositivo ya está vinculado a una cuenta'}), 400
            
        email = data['email']
        
        user = User(
            username=data['username'],
            email=email,
            password_hash=generate_password_hash(data['password']),
            role='user',
            is_verified=False
        )
        db.session.add(user)
        db.session.flush()
        
        link_user_to_device(user, device)

        # Generar token y enviar email de verificación
        token = user.generate_verification_token()
        db.session.commit()
        _send_verification_email(user.email, user.username, token)
        
        log.info(f"Registro: {user.username} vinculado a dispositivo {device.code} — verificación pendiente")
        return jsonify({
            'success': True,
            'message': 'Cuenta creada. Revisá tu correo y hacé click en el link de verificación para activar tu cuenta.'
        })
        
    except Exception as e:
        db.session.rollback()
        log.error(f'Error en registro: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/auth/register', methods=['POST'])
@login_required
@admin_required
def register():
    try:
        data = request.get_json()
        if not data or not data.get('username') or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Faltan campos obligatorios'}), 400
        if db.session.execute(db.select(User).filter_by(username=data['username'])).scalar_one_or_none():
            return jsonify({'error': 'Usuario ya existe'}), 400
        if db.session.execute(db.select(User).filter_by(email=data['email'])).scalar_one_or_none():
            return jsonify({'error': 'Email ya registrado'}), 400
        user = User(
            username=data['username'],
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            role=data.get('role', 'user')
        )
        db.session.add(user)
        db.session.commit()
        log.info(f'Usuario creado: {user.username} (por {current_user.username})')
        return jsonify({'message': 'Usuario creado', 'id': user.id}), 201
    except Exception as e:
        db.session.rollback()
        log.error(f'Error al registrar usuario: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': 'Faltan credenciales'}), 400

        user = db.session.execute(db.select(User).filter_by(username=data['username'])).scalar_one_or_none()

        # Unknown user – don't reveal existence
        if not user:
            log.warning(f'Login fallido (usuario desconocido): {data.get("username", "?")}')
            return jsonify({'error': 'Credenciales incorrectas'}), 401

        # Lockout check
        if user.is_locked():
            remaining = int((user.locked_until - _now()).total_seconds() / 60) + 1
            log.warning(f'Login bloqueado: {user.username}')
            return jsonify({
                'error': f'Cuenta bloqueada por demasiados intentos fallidos. '
                         f'Intentá de nuevo en {remaining} minuto(s).'
            }), 429

        # Password check
        if not check_password_hash(user.password_hash, data['password']):
            user.register_failed_attempt()
            db.session.commit()
            attempts_left = max(0, User.MAX_FAILED_ATTEMPTS - user.failed_login_attempts)
            log.warning(f'Login fallido: {user.username} '
                        f'(intento {user.failed_login_attempts}/{User.MAX_FAILED_ATTEMPTS})')
            if attempts_left == 0:
                return jsonify({
                    'error': f'Cuenta bloqueada por {User.LOCKOUT_MINUTES} minutos '
                             f'debido a demasiados intentos fallidos.'
                }), 429
            return jsonify({
                'error': f'Credenciales incorrectas. '
                         f'Te quedan {attempts_left} intento(s) antes del bloqueo.'
            }), 401

        # Active check
        if not user.is_active:
            return jsonify({'error': 'Cuenta desactivada. Contactá al administrador.'}), 403

        # Email verification check
        if not user.is_verified:
            return jsonify({
                'error': 'Correo no verificado. Revisá tu bandeja de entrada o solicitá un nuevo link.',
                'code': 'email_not_verified',
                'email': user.email
            }), 403

        # Success
        user.reset_failed_attempts()
        from flask import session as flask_session
        flask_session.permanent = True   # Cookie persiste 30 días
        login_user(user, remember=True)
        user.last_login = _now()
        db.session.commit()
        log.info(f'Login exitoso: {user.username}')
        return jsonify({'message': 'Login exitoso', 'role': user.role, 'username': user.username, 'id': user.id})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error en login: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    log.info(f'Logout: {current_user.username}')
    logout_user()
    return jsonify({'message': 'Logout exitoso'})

@app.route('/api/auth/me', methods=['GET'])
@login_required
def me():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'role': current_user.role,
        'email': current_user.email,
        'last_login': current_user.last_login.isoformat() if current_user.last_login else None
    })

@app.route('/api/auth/session', methods=['GET'])
def check_session():
    """Verifica si hay sesión activa. Retorna 200 con datos o 401 sin redirigir."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'id': current_user.id,
            'username': current_user.username,
            'role': current_user.role
        })
    return jsonify({'authenticated': False}), 401

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """Allow the current user to change their own password."""
    try:
        data = request.get_json()
        current_pw = data.get('current_password', '')
        new_pw     = data.get('new_password', '')
        if not current_pw or not new_pw:
            return jsonify({'error': 'Faltan campos obligatorios'}), 400
        if len(new_pw) < 8:
            return jsonify({'error': 'La nueva contraseña debe tener al menos 8 caracteres'}), 400
        if not check_password_hash(current_user.password_hash, current_pw):
            return jsonify({'error': 'Contraseña actual incorrecta'}), 401
        current_user.password_hash = generate_password_hash(new_pw)
        current_user.password_changed_at = _now()
        db.session.commit()
        log.info(f'Contraseña cambiada: {current_user.username}')
        return jsonify({'message': 'Contraseña actualizada correctamente'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error cambiando contraseña: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

# ── Email Verification ────────────────────────────────

def _send_verification_email(to_email, username, token):
    """Envía el email de verificación. Falla silenciosamente si no hay SMTP configurado."""
    try:
        verify_url = f"{APP_BASE_URL}/verify-email.html?token={token}"
        msg = Message(
            subject="ASV Kit · Verificá tu correo",
            recipients=[to_email]
        )
        msg.html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;background:#0a0a0f;color:#f5f5f7;padding:40px 32px;border-radius:16px">
          <h2 style="margin-bottom:8px;font-size:22px;">Bienvenido a ASV Kit, {username} 👋</h2>
          <p style="color:rgba(245,245,247,.7);line-height:1.6;margin-bottom:28px">
            Para activar tu cuenta hacé click en el botón de abajo.<br>
            El link expira en <strong>24 horas</strong>.
          </p>
          <a href="{verify_url}" style="display:inline-block;background:#0071e3;color:#fff;font-weight:600;padding:14px 28px;border-radius:10px;text-decoration:none;font-size:15px">
            Verificar mi correo
          </a>
          <p style="color:rgba(245,245,247,.4);font-size:12px;margin-top:28px">
            Si no creaste esta cuenta, ignorá este mensaje.
          </p>
        </div>
        """
        mail.send(msg)
        log.info(f'Email de verificación enviado a {to_email}')
    except Exception as e:
        log.warning(f'No se pudo enviar email de verificación: {e}')

@app.route('/api/auth/verify-email', methods=['GET'])
def verify_email():
    token = request.args.get('token', '')
    if not token:
        return jsonify({'error': 'Token faltante'}), 400

    user = db.session.execute(db.select(User).filter_by(verification_token=token)).scalar_one_or_none()
    if not user:
        return jsonify({'error': 'Token inválido o ya utilizado'}), 404

    if user.verification_token_expires and user.verification_token_expires < _now():
        return jsonify({'error': 'Token expirado', 'code': 'token_expired', 'email': user.email}), 410

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()
    log.info(f'Email verificado: {user.username}')
    return jsonify({'success': True, 'message': 'Correo verificado correctamente. Ya podés iniciar sesión.'})

@app.route('/api/auth/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({'error': 'Falta el correo electrónico'}), 400

        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        if not user:
            # No revelar si el usuario existe
            return jsonify({'message': 'Si ese correo está registrado, recibirás un nuevo link.'})

        if user.is_verified:
            return jsonify({'message': 'Tu correo ya está verificado. Podés iniciar sesión.'})

        token = user.generate_verification_token()
        db.session.commit()
        _send_verification_email(user.email, user.username, token)
        log.info(f'Reenvío de verificación para: {user.email}')
        return jsonify({'message': 'Te enviamos un nuevo link de verificación. Revisá tu correo.'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error en resend-verification: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

# ── Password Reset (Forgot / Reset) ──────────────────────────────────

def _send_reset_email(to_email, username, token):
    """Envía el email de recuperación de contraseña."""
    try:
        reset_url = f"{APP_BASE_URL}/reset-password.html?token={token}"
        msg = Message(
            subject="ASV Kit · Recuperación de contraseña",
            recipients=[to_email]
        )
        msg.html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:0 auto;background:#0a0a0f;color:#f5f5f7;padding:40px 32px;border-radius:16px">
          <h2 style="margin-bottom:8px;font-size:22px;">Recuperación de contraseña 🔑</h2>
          <p style="color:rgba(245,245,247,.7);line-height:1.6;margin-bottom:8px">
            Hola <strong>{username}</strong>, recibimos una solicitud para restablecer la contraseña de tu cuenta en ASV Kit.
          </p>
          <p style="color:rgba(245,245,247,.7);line-height:1.6;margin-bottom:28px">
            Hacé click en el botón de abajo para crear una nueva contraseña.
            El link expira en <strong>1 hora</strong>.
          </p>
          <a href="{reset_url}" style="display:inline-block;background:#0071e3;color:#fff;font-weight:600;padding:14px 28px;border-radius:10px;text-decoration:none;font-size:15px">
            Restablecer contraseña
          </a>
          <p style="color:rgba(245,245,247,.5);font-size:12px;margin-top:28px;line-height:1.6">
            Si no solicitaste este cambio, ignorá este mensaje. Tu contraseña actual seguirá siendo la misma.<br/>
            Por seguridad, este link es de un solo uso.
          </p>
          <p style="color:rgba(245,245,247,.3);font-size:11px;margin-top:16px">
            ASV Kit &mdash; Sistema de Monitoreo de Seguridad
          </p>
        </div>
        """
        mail.send(msg)
        log.info(f'Email de recuperación enviado a {to_email}')
    except Exception as e:
        log.warning(f'No se pudo enviar email de recuperación: {e}')
        raise  # Re-lanzar para que el endpoint pueda informar el error


@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Solicita reseteo de contraseña. Envía email con link único."""
    try:
        data = request.get_json()
        email = (data.get('email', '') if data else '').strip().lower()
        if not email:
            return jsonify({'error': 'Ingresá tu correo electrónico'}), 400

        user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

        # Siempre responder igual (no revelar si el email existe)
        generic_msg = 'Si ese correo está registrado, recibirás un link para restablecer tu contraseña. Revisá tu bandeja de entrada.'

        if not user:
            log.info(f'Forgot-password: email no encontrado ({email})')
            return jsonify({'message': generic_msg})

        if not user.is_active:
            return jsonify({'message': generic_msg})

        token = user.generate_reset_token()
        db.session.commit()

        try:
            _send_reset_email(user.email, user.username, token)
        except Exception as e:
            log.error(f'Error enviando reset email: {e}')
            return jsonify({'error': 'No se pudo enviar el email. Verificá la configuración SMTP del servidor.'}), 500

        return jsonify({'message': generic_msg})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error en forgot-password: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Resetea la contraseña usando el token del email."""
    try:
        data = request.get_json()
        token    = (data.get('token', '') if data else '').strip()
        new_pw   = (data.get('new_password', '') if data else '').strip()

        if not token:
            return jsonify({'error': 'Token faltante'}), 400
        if not new_pw:
            return jsonify({'error': 'La nueva contraseña es requerida'}), 400
        if len(new_pw) < 8:
            return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400

        user = db.session.execute(db.select(User).filter_by(reset_token=token)).scalar_one_or_none()
        if not user:
            return jsonify({'error': 'El link es inválido o ya fue utilizado'}), 404

        if user.reset_token_expires and user.reset_token_expires < _now():
            return jsonify({'error': 'El link expiró. Solicitá uno nuevo.', 'code': 'token_expired'}), 410

        user.password_hash = generate_password_hash(new_pw)
        user.password_changed_at = _now()
        user.reset_token = None
        user.reset_token_expires = None
        # Desbloquear cuenta si estaba bloqueada
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()

        # Cerrar cualquier sesión activa de este usuario en el servidor
        # para que deba autenticarse nuevamente con la nueva contraseña.
        logout_user()

        log.info(f'Contraseña restablecida para: {user.username}')
        return jsonify({'success': True, 'message': 'Contraseña restablecida correctamente. Ya podés iniciar sesión.'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error en reset-password: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500


# ── Rutas del Dashboard / Panel Principal (Estadísticas y gráficos iniciales) ──

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    try:
        today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        total_alerts = db.session.execute(db.select(func.count()).select_from(Alert)).scalar_one()
        alerts_today = db.session.execute(
            db.select(func.count()).select_from(Alert).where(Alert.triggered_at >= today)
        ).scalar_one()
        active_sensors = db.session.execute(
            db.select(func.count()).select_from(SensorNode).where(SensorNode.is_active.is_(True))
        ).scalar_one()
        total_sensors = db.session.execute(db.select(func.count()).select_from(SensorNode)).scalar_one()
        if current_user.role == 'admin':
            total_devices = db.session.execute(
                db.select(func.count()).select_from(Device).where(Device.is_active.is_(True))
            ).scalar_one()
        else:
            total_devices = db.session.execute(
                db.select(func.count()).select_from(Device).where(
                    Device.user_id == current_user.id, Device.is_active.is_(True)
                )
            ).scalar_one()
        last_alert = db.session.execute(
            db.select(Alert).order_by(Alert.triggered_at.desc())
        ).scalars().first()

        return jsonify({
            'total_alerts': total_alerts,
            'alerts_today': alerts_today,
            'active_sensors': active_sensors,
            'total_sensors': total_sensors,
            'total_devices': total_devices,
            'last_alert': last_alert.triggered_at.isoformat() if last_alert else None,
            'last_alert_sensor': last_alert.sensor.name if last_alert else None
        })
    except Exception as e:
        log.error(f'Error en stats: {e}')
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

@app.route('/api/stats/chart', methods=['GET'])
@login_required
def get_chart_data():
    """Devuelve alertas agrupadas por día para los últimos 7 días"""
    try:
        days = int(request.args.get('days', 7))
        days = min(days, 30)
        start = _now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        results = db.session.query(
            func.date(Alert.triggered_at).label('day'),
            func.count(Alert.id).label('count')
        ).filter(
            Alert.triggered_at >= start
        ).group_by(
            func.date(Alert.triggered_at)
        ).all()

        data_map = {str(r.day): r.count for r in results}
        chart = []
        for i in range(days):
            day = start + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            chart.append({'date': day_str, 'count': data_map.get(day_str, 0)})

        return jsonify(chart)
    except Exception as e:
        log.error(f'Error en chart data: {e}')
        return jsonify({'error': 'Error obteniendo datos del gráfico'}), 500

# ── Rutas de Alertas (Panel de Alertas: lista, paginación, filtros y creación desde el ESP32) ──

@app.route('/api/alerts', methods=['GET'])
@login_required
def get_alerts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 200)

        type_filter = request.args.get('type')
        rf_filter = request.args.get('rf')
        push_filter = request.args.get('push')

        stmt = db.select(Alert).order_by(Alert.triggered_at.desc())

        if type_filter:
            stmt = stmt.join(SensorNode).where(SensorNode.type == type_filter)
        if rf_filter:
            stmt = stmt.where(Alert.delivery_rf == rf_filter)
        if push_filter:
            stmt = stmt.where(Alert.delivery_push == push_filter)

        paginated = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

        return jsonify({
            'items': [{
                'id': a.id,
                'sensor': a.sensor.name,
                'type': a.sensor.type,
                'location': a.sensor.location,
                'triggered_at': a.triggered_at.isoformat(),
                'delivery_rf': a.delivery_rf,
                'delivery_push': a.delivery_push,
                'notes': a.notes
            } for a in paginated.items],
            'total': paginated.total,
            'page': paginated.page,
            'pages': paginated.pages,
            'has_next': paginated.has_next,
            'has_prev': paginated.has_prev
        })
    except Exception as e:
        log.error(f'Error obteniendo alertas: {e}')
        return jsonify({'error': 'Error obteniendo alertas'}), 500

@app.route('/api/alerts', methods=['POST'])
def create_alert():
    try:
        data = request.get_json()
        if not data or not data.get('rf_code'):
            return jsonify({'error': 'Falta rf_code'}), 400
        sensor = db.session.execute(db.select(SensorNode).filter_by(rf_code=data['rf_code'])).scalar_one_or_none()
        if not sensor:
            return jsonify({'error': 'Sensor no encontrado'}), 404
        if not sensor.is_active:
            return jsonify({'error': 'Sensor desactivado'}), 400
        alert = Alert(
            sensor_node_id=sensor.id,
            delivery_rf=data.get('delivery_rf', 'pending'),
            delivery_push=data.get('delivery_push', 'pending'),
            notes=data.get('notes')
        )
        db.session.add(alert)
        db.session.commit()
        log.info(f'Alerta creada: sensor={sensor.name}, rf_code={data["rf_code"]}')
        return jsonify({'message': 'Alerta registrada', 'id': alert.id}), 201
    except Exception as e:
        db.session.rollback()
        log.error(f'Error creando alerta: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

# ── Rutas de Sensores (Panel de Sensores: ver, agregar, editar y eliminar) ──

@app.route('/api/sensors', methods=['GET'])
@login_required
def get_sensors():
    sensors = db.session.execute(db.select(SensorNode).order_by(SensorNode.created_at.desc())).scalars().all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'type': s.type,
        'rf_code': s.rf_code,
        'location': s.location,
        'is_active': s.is_active,
        'alert_count': len(s.alerts)
    } for s in sensors])

@app.route('/api/sensors', methods=['POST'])
@login_required
@admin_required
def create_sensor():
    try:
        data = request.get_json()
        if not data or not data.get('name') or not data.get('type') or not data.get('rf_code'):
            return jsonify({'error': 'Faltan campos obligatorios'}), 400
        if db.session.execute(db.select(SensorNode).filter_by(rf_code=data['rf_code'])).scalar_one_or_none():
            return jsonify({'error': 'Código RF ya registrado'}), 400
        sensor = SensorNode(
            name=data['name'],
            type=data['type'],
            rf_code=data['rf_code'],
            location=data.get('location')
        )
        db.session.add(sensor)
        db.session.commit()
        log.info(f'Sensor creado: {sensor.name} (RF: {sensor.rf_code})')
        return jsonify({'message': 'Sensor registrado', 'id': sensor.id}), 201
    except Exception as e:
        db.session.rollback()
        log.error(f'Error creando sensor: {e}')
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/sensors/<int:record_id>', methods=['PUT'])
@login_required
@admin_required
def update_sensor(record_id: int):
    try:
        sensor = db.get_or_404(SensorNode, record_id)

        data = request.get_json()
        sensor.name = data.get('name', sensor.name)
        sensor.location = data.get('location', sensor.location)
        sensor.is_active = data.get('is_active', sensor.is_active)
        db.session.commit()
        log.info(f'Sensor actualizado: {sensor.name}')
        return jsonify({'message': 'Sensor actualizado'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error actualizando sensor: {e}')
        return jsonify({'error': 'Error interno'}), 500

@app.route('/api/sensors/<int:record_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_sensor(record_id: int):
    try:
        sensor = db.get_or_404(SensorNode, record_id)
        name = sensor.name
        db.session.delete(sensor)
        db.session.commit()
        log.info(f'Sensor eliminado: {name}')
        return jsonify({'message': 'Sensor eliminado'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error eliminando sensor: {e}')
        return jsonify({'error': 'Error interno'}), 500

# ── Rutas de Dispositivos Receptores (Panel de Dispositivos: los ESP32 vinculados a los usuarios) ──

@app.route('/api/devices', methods=['GET'])
@login_required
def get_devices():
    if current_user.role == 'admin':
        devices = db.session.execute(db.select(Device).order_by(Device.registered_at.desc())).scalars().all()
    else:
        devices = db.session.execute(
            db.select(Device).filter_by(user_id=current_user.id).order_by(Device.registered_at.desc())
        ).scalars().all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'push_token': d.push_token,
        'is_active': d.is_active,
        'code': d.code if current_user.role == 'admin' else None,
        'user_name': u.username if d.user_id and (u := db.session.get(User, d.user_id)) else None,
        'registered_at': d.registered_at.isoformat()
    } for d in devices])

@app.route('/api/devices', methods=['POST'])
@login_required
@admin_required
def create_device():
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': 'Falta nombre del dispositivo'}), 400
        device = Device(name=data['name'], push_token=data.get('push_token'))
        db.session.add(device)
        db.session.commit()
        log.info(f'Dispositivo registrado: {device.name}')
        return jsonify({'message': 'Dispositivo registrado', 'id': device.id}), 201
    except Exception as e:
        db.session.rollback()
        log.error(f'Error registrando dispositivo: {e}')
        return jsonify({'error': 'Error interno'}), 500

@app.route('/api/devices/<int:record_id>', methods=['PUT'])
@login_required
@admin_required
def update_device(record_id: int):
    try:
        device = db.get_or_404(Device, record_id)
        data = request.get_json()
        device.name = data.get('name', device.name)
        device.is_active = data.get('is_active', device.is_active)
        device.push_token = data.get('push_token', device.push_token)
        db.session.commit()
        return jsonify({'message': 'Dispositivo actualizado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno'}), 500

@app.route('/api/devices/<int:record_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_device(record_id: int):
    try:
        device = db.get_or_404(Device, record_id)
        name = device.name
        
        if device.user_id:
            user = db.session.get(User, device.user_id)
            if user:
                user.device_id = None
                
        db.session.delete(device)
        db.session.commit()
        log.info(f'Dispositivo eliminado: {name}')
        return jsonify({'message': 'Dispositivo eliminado'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error eliminando dispositivo: {e}')
        return jsonify({'error': 'Error interno'}), 500

# ── Rutas de Administración de Usuarios (Panel "Usuarios": sólo accesible para administradores) ──

@app.route('/api/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    users = db.session.execute(db.select(User).order_by(User.created_at.desc())).scalars().all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role': u.role,
        'is_active': u.is_active,
        'created_at': u.created_at.isoformat(),
        'last_login': u.last_login.isoformat() if u.last_login else None,
        'failed_login_attempts': u.failed_login_attempts or 0,
        'locked_until': u.locked_until.isoformat() if u.locked_until else None,
        'is_locked': u.is_locked(),
        'device_code': device.code if u.device_id and (device := db.session.get(Device, u.device_id)) else None
    } for u in users])

@app.route('/api/users/<int:record_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(record_id: int):
    try:
        user = db.get_or_404(User, record_id)
        data = request.get_json()
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'role' in data and data['role'] in ('admin', 'user'):
            user.role = data['role']
        if data.get('unlock'):
            user.failed_login_attempts = 0
            user.locked_until = None
        db.session.commit()
        log.info(f'Usuario actualizado: {user.username} (por {current_user.username})')
        return jsonify({'message': 'Usuario actualizado'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error actualizando usuario: {e}')
        return jsonify({'error': 'Error interno'}), 500

@app.route('/api/users/<int:record_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(record_id: int):
    try:
        if record_id == current_user.id:
            return jsonify({'error': 'No podés eliminarte a vos mismo'}), 400
        user = db.get_or_404(User, record_id)
        name = user.username
        
        devices = db.session.execute(db.select(Device).filter_by(user_id=user.id)).scalars().all()
        for d in devices:
            d.is_registered = False
            d.user_id = None
            
        db.session.delete(user)
        db.session.commit()
        log.info(f'Usuario eliminado: {name} (por {current_user.username})')
        return jsonify({'message': 'Usuario eliminado'})
    except Exception as e:
        db.session.rollback()
        log.error(f'Error eliminando usuario: {e}')
        return jsonify({'error': 'Error interno'}), 500

# ── Rutas de Archivos Estáticos (Sirven el Frontend: HTML, CSS, JS) ──

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BASE_DIR, filename)

# ── Inicialización de la Aplicación y Migraciones de Base de Datos ──
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # ── Schema migrations for existing databases ───────
        new_columns_user = [
            ('last_login',                   'DATETIME'),
            ('failed_login_attempts',        'INTEGER DEFAULT 0'),
            ('locked_until',                 'DATETIME'),
            ('password_changed_at',          'DATETIME'),
            ('device_id',                    'INTEGER'),
            ('is_verified',                  'BOOLEAN DEFAULT 0'),
            ('verification_token',           'VARCHAR(64)'),
            ('verification_token_expires',   'DATETIME'),
            ('reset_token',                  'VARCHAR(64)'),
            ('reset_token_expires',          'DATETIME'),
        ]
        for col_name, col_def in new_columns_user:
            try:
                db.session.execute(
                    db.text(f'ALTER TABLE user ADD COLUMN {col_name} {col_def}')
                )
                db.session.commit()
                log.info(f'Migración: columna "{col_name}" agregada a user')
            except Exception:
                db.session.rollback()  # Column already exists – ignore

        new_columns_device = [
            ('code',          'VARCHAR(10)'),
            ('is_registered', 'BOOLEAN DEFAULT 0'),
            ('user_id',       'INTEGER'),
        ]
        for col_name, col_def in new_columns_device:
            try:
                db.session.execute(
                    db.text(f'ALTER TABLE device ADD COLUMN {col_name} {col_def}')
                )
                db.session.commit()
                log.info(f'Migración: columna "{col_name}" agregada a device')
            except Exception:
                db.session.rollback()

        # Asegurar que los dispositivos de prueba existen
        try:
            for code in ["B9C2", "A1B2", "C3D4", "E5F6", "G7H8", "I9J0"]:
                insert_device(code)
        except Exception as e:
            log.warning(f"No se pudieron insertar dispositivos de prueba (posible bloqueo): {e}")

        # Marcar como verificados los usuarios que existían antes del sistema de verificación
        try:
            unverified_legacy = db.session.execute(
                db.select(User).where(
                    (User.is_verified.is_(None)) | (User.is_verified.is_(False)),
                    User.verification_token.is_(None)
                )
            ).scalars().all()
            for u in unverified_legacy:
                u.is_verified = True
            if unverified_legacy:
                db.session.commit()
                log.info(f'Verificados {len(unverified_legacy)} usuario(s) legado(s) (pre-verificación)')
        except Exception as e:
            log.warning(f"No se pudo verificar usuarios legados: {e}")

        try:
            if not db.session.execute(db.select(User).filter_by(username='admin')).scalar_one_or_none():
                admin = User(
                    username='admin',
                    email='admin@asvkit.com',
                    password_hash=generate_password_hash('admin123'),
                    role='admin',
                    is_verified=True
                )
                db.session.add(admin)
                db.session.commit()
                log.info('Usuario admin creado: admin / admin123')
        except Exception as e:
            log.warning(f"No se pudo verificar/crear usuario admin: {e}")

    app.run(debug=True, port=5000)

    @app.route("/frontend/historial")
    def serve_historial():
        return send_from_directory(BASE_DIR, 'historial.html')