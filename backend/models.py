from __future__ import annotations
import typing
from database import db
from flask_login import UserMixin
from datetime import datetime, timedelta
from typing import Optional, Any
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import secrets


def _now() -> datetime:
    """Retorna datetime UTC naive (compatible con SQLite y sin DeprecationWarning)."""
    return datetime.utcnow()  # noqa: DTZ003


# ── Modelo: SensorNode (Sensores físicos registrados en el panel) ──
class SensorNode(db.Model):
    __tablename__ = 'sensor_node'

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:       Mapped[str]           = mapped_column(String(100), nullable=False)
    type:       Mapped[str]           = mapped_column(String(50),  nullable=False)
    rf_code:    Mapped[str]           = mapped_column(String(20),  unique=True, nullable=False)
    location:   Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active:  Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, default=_now)

    alerts: Mapped[list[Alert]] = relationship(
        'Alert', backref='sensor', lazy=True, cascade='all, delete-orphan'
    )


# ── Modelo: Alert (Registro histórico de alertas disparadas por sensores) ──
class Alert(db.Model):
    __tablename__ = 'alert'

    id:             Mapped[int]           = mapped_column(Integer, primary_key=True)
    sensor_node_id: Mapped[int]           = mapped_column(Integer, ForeignKey('sensor_node.id'), nullable=False)
    triggered_at:   Mapped[datetime]      = mapped_column(DateTime, default=_now)
    delivery_rf:    Mapped[str]           = mapped_column(String(20), default='pending')
    delivery_push:  Mapped[str]           = mapped_column(String(20), default='pending')
    notes:          Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


# ── Modelo: Device (Receptores ESP32 físicos vinculados a un usuario) ──
class Device(db.Model):
    __tablename__ = 'device'

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:          Mapped[str]           = mapped_column(String(100), nullable=False)
    push_token:    Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active:     Mapped[bool]          = mapped_column(Boolean, default=True)
    registered_at: Mapped[datetime]      = mapped_column(DateTime, default=_now)

    # Vinculación física ESP32
    code:          Mapped[Optional[str]] = mapped_column(String(10), unique=True, nullable=True)
    is_registered: Mapped[bool]          = mapped_column(Boolean, default=False)
    user_id:       Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('user.id'), nullable=True)

    deliveries: Mapped[list[AlertDelivery]] = relationship(
        'AlertDelivery', backref='device', lazy=True, cascade='all, delete-orphan'
    )


# ── Modelo: AlertDelivery (Estado de entrega de alertas hacia los dispositivos) ──
class AlertDelivery(db.Model):
    __tablename__ = 'alert_delivery'

    id:        Mapped[int]      = mapped_column(Integer, primary_key=True)
    alert_id:  Mapped[int]      = mapped_column(Integer, ForeignKey('alert.id'),  nullable=False)
    device_id: Mapped[int]      = mapped_column(Integer, ForeignKey('device.id'), nullable=False)
    status:    Mapped[str]      = mapped_column(String(20), default='pending')
    sent_at:   Mapped[datetime] = mapped_column(DateTime, default=_now)


# ── Modelo: User (Cuentas de usuario para login, dashboard y panel admin) ──
class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id:                    Mapped[int]               = mapped_column(Integer, primary_key=True)
    username:              Mapped[str]               = mapped_column(String(80),  unique=True, nullable=False)
    email:                 Mapped[str]               = mapped_column(String(120), unique=True, nullable=False)
    password_hash:         Mapped[str]               = mapped_column(String(200), nullable=False)
    role:                  Mapped[str]               = mapped_column(String(20),  default='user')
    is_active:             Mapped[bool]               = mapped_column(Boolean, default=True)  # type: ignore
    created_at:            Mapped[datetime]          = mapped_column(DateTime, default=_now)
    last_login:            Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_login_attempts: Mapped[int]               = mapped_column(Integer, default=0)
    locked_until:          Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_changed_at:   Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Vinculación de dispositivo físico
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('device.id'), nullable=True)

    # Verificación de correo
    is_verified:                Mapped[bool]               = mapped_column(Boolean, default=False)
    verification_token:         Mapped[Optional[str]]      = mapped_column(String(64), nullable=True)
    verification_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Recuperación de contraseña
    reset_token:         Mapped[Optional[str]]      = mapped_column(String(64), nullable=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Métodos de token ─────────────────────────────────

    def generate_verification_token(self) -> str:
        """Genera un token seguro de 32 bytes y lo guarda en el modelo."""
        token = secrets.token_urlsafe(32)
        self.verification_token = token
        self.verification_token_expires = _now() + timedelta(hours=24)
        return token

    def generate_reset_token(self) -> str:
        """Genera un token de reseteo de contraseña con expiración de 1 hora."""
        token = secrets.token_urlsafe(32)
        self.reset_token = token
        self.reset_token_expires = _now() + timedelta(hours=1)
        return token

    # ── Seguridad / lockout ──────────────────────────────

    MAX_FAILED_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int     = 15

    def is_locked(self) -> bool:
        """Return True if the account is currently locked out."""
        return bool(self.locked_until and self.locked_until > _now())

    def register_failed_attempt(self) -> None:
        """Increment the failed counter and lock the account if the threshold is reached."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = _now() + timedelta(minutes=self.LOCKOUT_MINUTES)

    def reset_failed_attempts(self) -> None:
        """Clear counters on successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None