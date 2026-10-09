import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

load_dotenv()

# Se lee de backend/.env (ver .env.example): nunca escribir credenciales en el código.
# Estructura: postgresql://usuario:password@host:5432/nombre_base_de_datos
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta DATABASE_URL en backend/.env (ver backend/.env.example).")

# pool_pre_ping: Neon suspende la base de datos tras unos minutos sin uso y cierra las conexiones;
# así se detecta y se reabre la conexión en vez de fallar en la primera petición tras la pausa.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- MODELO DE USUARIO ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)  # Número de celular opcional
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación 1 a N con la tabla tasks
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")


# --- MODELO TRADICIONAL DE LA TABLA EN BASE DE DATOS ---
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)    # Título normalizado por la IA
    due_date = Column(String(50), nullable=True)   # Almacenará la fecha inferida en formato AAAA-MM-DD
    category = Column(String(100), nullable=True)  # Categoría (Estudio, Trabajo, etc.)
    priority = Column(String(50), nullable=True)   # Prioridad (Alta, Media, Baja)
    completed = Column(Boolean, default=False)
    ai_analysis = Column(String, nullable=True)

    # Recordatorios por correo (los envía el flujo de n8n en automation/). Guardan cuándo se
    # envió cada aviso para no repetirlo; se reinician si cambia la fecha de la tarea.
    reminder_day_before_sent_at = Column(DateTime, nullable=True)
    reminder_same_day_sent_at = Column(DateTime, nullable=True)

    # Clave foránea para asociar la tarea al usuario creador
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="tasks")


def create_db():
    """Genera físicamente las tablas en el servidor PostgreSQL si no existen."""
    Base.metadata.create_all(bind=engine)

# Función para inyectar la sesión de base de datos en los endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()