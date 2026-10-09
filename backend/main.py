import os
import json
import time
import traceback
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.orm import Session
from google import genai
from google.genai import errors, types
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()

import database
import date_resolver
from database import get_db
import schemas
import auth

app = FastAPI(
    title="TaskAI Core - Motor Principal",
    description="Backend funcional aislado con persistencia tradicional y extracción mediante Gemini AI"
)

# Orígenes permitidos (la URL local de tu futuro proyecto en Angular)
origins = [
    "http://localhost:4200",
]

# Habilitamos CORS de forma abierta para no tener bloqueos futuros con Angular
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Inicializar tablas al arrancar el servidor
@app.on_event("startup")
def startup_event():
    database.create_db()




# --- MODELOS DE CONTROL DE DATOS (PYDANTIC) ---

# Esquema para recibir los datos de actualización manual
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None  # Formato YYYY-MM-DD
    category: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class TaskRequest(BaseModel):
    text: str = Field(description="Texto libre enviado por el usuario.")


class GeminiTaskStructure(BaseModel):
    title: str = Field(description="Un título resumido, claro y limpio de la tarea.")
    category: str = Field(description="Categoría de la tarea (Ej: Estudio, Trabajo, Descanso, Salud).")
    priority: str = Field(description="Prioridad estimada basada en la urgencia: Alta, Media o Baja.")
    detected_date: Optional[str] = Field(
        description="Fecha de la tarea en formato AAAA-MM-DD. Si las instrucciones indican una fecha ya calculada, "
                    "copia exactamente esa. Si no, búscala en el calendario de referencia sin hacer cálculos. "
                    "Si el texto no menciona ninguna fecha, null.")
    ai_analysis: str = Field(
        description="Un consejo de productividad o recordatorio de una sola frase sobre el impacto de la actividad.")


class CompleteTaskResponse(BaseModel):
    id: int
    title: str
    due_date: Optional[str]
    category: str
    priority: str
    ai_analysis: str
    completed: Optional[bool]


# Modelos en orden de preferencia. En el plan gratuito cada modelo tiene su propia cuota, así que si
# uno está saturado (503) o agotado (429) se prueba el siguiente en vez de fallar.
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-lite-latest"]
# Códigos que justifican pasar al siguiente modelo; cualquier otro error (p. ej. 400) se propaga.
GEMINI_FALLBACK_CODES = {429, 500, 503, 504}

# Cliente oficial de Gemini (lee GEMINI_API_KEY). Por defecto la librería reintenta 5 veces con
# esperas de hasta 60 s; con 2 intentos por modelo el salto al modelo de respaldo es rápido.
client = genai.Client(http_options=types.HttpOptions(
    retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1.0, max_delay=4.0)))


def generate_with_fallback(contents: str, config: types.GenerateContentConfig):
    """Llama a Gemini probando los modelos de GEMINI_MODELS en orden hasta que uno responda."""
    last_error = None
    for model in GEMINI_MODELS:
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            print(f"=== Modelo usado: {model} ===")
            return response
        except errors.APIError as e:
            if e.code not in GEMINI_FALLBACK_CODES:
                raise
            print(f"=== {model} no disponible ({e.code} {e.status}) -> probando el siguiente modelo ===")
            last_error = e
    raise last_error


# --- ENDPOINTS SISTEMA Y AUTENTICACIÓN ---

@app.get("/", tags=["Sistema"])
def health_check():
    return {"status": "online", "backend": "PostgreSQL + Gemini 2.5 unificados"}


@app.post("/api/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED,
          tags=["Autenticación"])
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(database.User).filter(database.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado."
        )

    new_user = database.User(
        email=user_data.email,
        hashed_password=auth.hash_password(user_data.password),
        full_name=user_data.full_name,
        phone_number=user_data.phone_number
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/api/auth/login", response_model=schemas.Token, tags=["Autenticación"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(database.User).filter(database.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --- ENDPOINTS CORE ---

# ENDPOINT PARA LISTAR TODAS LAS TAREAS
@app.get("/api/tasks", response_model=List[CompleteTaskResponse], tags=["Tareas"])
def list_tasks(
        db: Session = Depends(get_db),
        current_user: database.User = Depends(auth.get_current_user)
):
    """Consulta la base de datos y retorna el historial con su análisis guardado."""
    tasks = db.query(database.Task).filter(
        database.Task.owner_id == current_user.id
    ).order_by(database.Task.id.desc()).all()

    return [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date if t.due_date else None,
            "category": t.category if t.category else "General",
            "priority": t.priority if t.priority else "Media",
            "ai_analysis": t.ai_analysis if hasattr(t, "ai_analysis") and t.ai_analysis else "Sin análisis registrado.",
            # <-- RETORNA LO DE LA BD
            "completed": t.completed if t.completed is not None else False
        }
        for t in tasks
    ]


# 2. ENDPOINT PARA MARCAR COMO COMPLETADA (TOGGLE)
@app.patch("/api/tasks/{task_id}/toggle", response_model=CompleteTaskResponse, tags=["Tareas"])
async def toggle_task_status(
        task_id: int,
        db: Session = Depends(get_db),
        current_user: database.User = Depends(auth.get_current_user)
):
    task = db.query(database.Task).filter(
        database.Task.id == task_id,
        database.Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La tarea con ID {task_id} no existe."
        )

    try:
        # Forzamos la actualización usando tipos nativos de Python
        current_status = bool(task.completed) if task.completed is not None else False
        task.completed = not current_status

        db.commit()
        db.refresh(task)

        return {
            "id": task.id,
            "title": task.title,
            "due_date": task.due_date if task.due_date else None,
            "category": task.category,
            "priority": task.priority,
            "completed": task.completed,
            "ai_analysis": task.ai_analysis if hasattr(task, "ai_analysis") and task.ai_analysis else "Sin análisis."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al modificar la columna booleana: {str(e)}"
        )


# 3. ENDPOINT PARA ACTUALIZACIÓN MANUAL COMPLETA (PUT)
@app.put("/api/tasks/{task_id}", response_model=CompleteTaskResponse, tags=["Tareas"])
async def update_task_manual(
        task_id: int,
        payload: TaskUpdate,
        db: Session = Depends(get_db),
        current_user: database.User = Depends(auth.get_current_user)
):
    task = db.query(database.Task).filter(
        database.Task.id == task_id,
        database.Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La tarea con ID {task_id} no existe."
        )

    try:
        # Extraemos los datos enviados en el JSON omitiendo los que no se enviaron
        update_data = payload.dict(exclude_unset=True)

        # Actualizamos campo por campo de forma segura
        if "title" in update_data:
            task.title = update_data["title"]
        if "due_date" in update_data:
            if update_data["due_date"] != task.due_date:
                # Nueva fecha: los recordatorios ya enviados eran para la anterior.
                task.reminder_day_before_sent_at = None
                task.reminder_same_day_sent_at = None
            task.due_date = update_data["due_date"]
        if "category" in update_data:
            task.category = update_data["category"]
        if "priority" in update_data:
            task.priority = update_data["priority"]
        if "completed" in update_data:
            task.completed = bool(update_data["completed"]) if update_data["completed"] is not None else False

        db.commit()
        db.refresh(task)

        # Retornamos la estructura exacta que espera Pydantic
        return {
            "id": task.id,
            "title": task.title,
            "due_date": task.due_date if task.due_date else None,
            "category": task.category,
            "priority": task.priority,
            "completed": task.completed if task.completed is not None else False,
            "ai_analysis": task.ai_analysis if hasattr(task, "ai_analysis") and task.ai_analysis else "Sin análisis."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error en la actualización manual: {str(e)}"
        )


# 4. ENDPOINT PARA ELIMINAR TAREAS (DELETE)
@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tareas"])
async def delete_task(
        task_id: int,
        db: Session = Depends(get_db),
        current_user: database.User = Depends(auth.get_current_user)
):
    task = db.query(database.Task).filter(
        database.Task.id == task_id,
        database.Task.owner_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La tarea con ID {task_id} no existe."
        )

    db.delete(task)
    db.commit()
    return None  # El estatus 204 exige no retornar contenido


@app.post("/api/process-task", response_model=CompleteTaskResponse, tags=["Tareas"])
async def process_and_save(
        payload: TaskRequest,
        db: Session = Depends(get_db),
        current_user: database.User = Depends(auth.get_current_user)
):
    """Procesa el texto con IA, lo estructura y lo guarda de forma real en PostgreSQL."""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="El texto está vacío.")

    try:
        # --- MEDICIÓN DE TIEMPO ---
        inicio_ia = time.time()
        print("\n=== [1] Enviando petición a Gemini AI... ===")

        # La fecha se calcula en Python ANTES de llamar a Gemini: la IA no es fiable con la
        # aritmética de calendario (convertía "el próximo lunes" en el lunes ya pasado).
        today = datetime.now().date()
        resolved = date_resolver.resolve_date(payload.text, today)

        if resolved:
            iso = resolved.value.isoformat()
            date_instruction = (
                f"FECHA DE LA TAREA, YA CALCULADA (no la recalcules): {date_resolver.describe(resolved.value)} = {iso}.\n"
                f"Pon exactamente '{iso}' en 'detected_date'. Si mencionas la fecha en el consejo, "
                f"escríbela en lenguaje natural ('{date_resolver.describe(resolved.value)}'), nunca como AAAA-MM-DD."
            )
        else:
            # Expresiones que las reglas no cubren: la IA busca en un calendario en vez de calcular.
            date_instruction = (
                "Si el texto menciona una fecha, NO hagas cálculos: búscala en este calendario de referencia "
                "y copia su valor AAAA-MM-DD en 'detected_date'. 'El próximo <día>' es la primera vez que ese "
                "día aparece DESPUÉS de hoy; nunca uses una fecha anterior a hoy.\n"
                f"{date_resolver.calendar_for_prompt(today)}"
            )

        # A. Envío estructurado a Gemini AI
        response = generate_with_fallback(
            contents=f"Extrae y organiza la siguiente tarea: {payload.text}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiTaskStructure,
                system_instruction=(
                    "Eres un asistente de alta productividad encargado de parsear texto desorganizado "
                    "y normalizarlo al esquema JSON solicitado sin añadir saludos ni texto conversacional.\n\n"
                    f"HOY ES: {date_resolver.describe(today)} ({today.isoformat()}).\n"
                    f"{date_instruction}\n"
                    "Si el texto no incluye ninguna referencia de tiempo, deja 'detected_date' como null."
                )
            ),
        )

        fin_ia = time.time()
        print(f"=== [2] Gemini respondió en: {fin_ia - inicio_ia:.2f} segundos ===")

        # --- MEDICIÓN DE BASE DE DATOS ---
        inicio_db = time.time()

        # B. Convertimos el string devuelto por la IA en un diccionario de Python
        ai_data = json.loads(response.text)

        # La fecha calculada por reglas manda; la de la IA solo se usa si no la hubo, y validada.
        if resolved:
            due_date = resolved.value.isoformat()
            print(f"=== Fecha por reglas ({resolved.rule}): {due_date} ===")
        else:
            due_date = ai_data.get("detected_date")
            try:
                due_date = date.fromisoformat(due_date).isoformat() if due_date else None
            except ValueError:
                due_date = None  # La IA devolvió algo que no es una fecha AAAA-MM-DD
            print(f"=== Fecha por IA: {due_date} ===")

        # C. Creación del registro e inserción en PostgreSQL usando el ORM
        new_task = database.Task(
            title=ai_data["title"],
            due_date=due_date,
            category=ai_data["category"],
            priority=ai_data["priority"],
            completed=False,  # <-- Nace en falso
            ai_analysis=ai_data["ai_analysis"],
            owner_id=current_user.id  # Vinculación con el usuario logueado
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        fin_db = time.time()
        print(f"=== [3] Guardado en PostgreSQL en: {fin_db - inicio_db:.4f} segundos ===")
        print(f"=== [4] TIEMPO TOTAL: {fin_db - inicio_ia:.2f} segundos ===\n")

        # D. Retornamos la respuesta perfecta combinada para la futura UI
        return {
            "id": new_task.id,
            "title": new_task.title,
            "due_date": new_task.due_date if new_task.due_date else None,
            "category": new_task.category,
            "priority": new_task.priority,
            "completed": new_task.completed if new_task.completed is not None else False,
            "ai_analysis": ai_data["ai_analysis"]
        }

    except errors.APIError as e:
        # Todos los modelos fallaron: se avisa con un mensaje comprensible y el motivo real va a la terminal.
        db.rollback()
        print(f"=== [ERROR] Gemini: {e.code} {e.status} - {e.message} ===")
        if e.code == 429:
            raise HTTPException(status_code=429,
                                detail="Se agotó la cuota gratuita de la IA por ahora. Inténtalo más tarde.")
        if e.code in GEMINI_FALLBACK_CODES:
            raise HTTPException(status_code=503,
                                detail="La IA está saturada en este momento. Inténtalo de nuevo en unos minutos.")
        raise HTTPException(status_code=502, detail="La IA no pudo procesar la tarea.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()  # Sin esto el motivo del 500 solo viajaba en la respuesta, no en la terminal
        raise HTTPException(status_code=500, detail=f"Error en procesamiento del motor: {str(e)}")