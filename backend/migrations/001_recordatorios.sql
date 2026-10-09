-- Columnas para los recordatorios por correo del flujo de n8n (automation/).
-- Base.metadata.create_all() no añade columnas a tablas existentes, así que se aplica a mano.
-- Es idempotente: se puede ejecutar varias veces sin error.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS reminder_day_before_sent_at TIMESTAMP NULL;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS reminder_same_day_sent_at TIMESTAMP NULL;
