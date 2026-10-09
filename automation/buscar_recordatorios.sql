-- Recordatorios pendientes de enviar: tareas sin completar que vencen mañana (aviso del día
-- anterior) u hoy (aviso del mismo día) y cuyo aviso aún no se ha enviado.
-- La ejecuta enviar_recordatorios.py, que fija antes la zona horaria a America/Bogota
-- (Neon funciona en UTC: sin eso, desde las 19:00 de Bogotá CURRENT_DATE sería "mañana").
-- due_date es texto AAAA-MM-DD: se compara como texto para no fallar con valores mal formados.
-- El escape HTML de los textos lo hace el script, no esta consulta.
WITH hoy AS (SELECT CURRENT_DATE AS d),
candidatas AS (
  SELECT
    t.id,
    t.title,
    COALESCE(t.category, 'General') AS category,
    COALESCE(t.priority, 'Media') AS priority,
    COALESCE(t.ai_analysis, '') AS ai_analysis,
    u.email,
    COALESCE(NULLIF(TRIM(u.full_name), ''), split_part(u.email, '@', 1)) AS nombre,
    CASE WHEN t.due_date = to_char(hoy.d, 'YYYY-MM-DD') THEN 'mismo_dia' ELSE 'dia_anterior' END AS tipo,
    CASE WHEN t.due_date = to_char(hoy.d, 'YYYY-MM-DD') THEN hoy.d ELSE hoy.d + 1 END AS fecha
  FROM tasks t
  JOIN users u ON u.id = t.owner_id
  CROSS JOIN hoy
  WHERE t.completed IS NOT TRUE
    AND (
      (t.due_date = to_char(hoy.d + 1, 'YYYY-MM-DD') AND t.reminder_day_before_sent_at IS NULL)
      OR (t.due_date = to_char(hoy.d, 'YYYY-MM-DD') AND t.reminder_same_day_sent_at IS NULL)
    )
)
SELECT
  c.*,
  (ARRAY['domingo','lunes','martes','miércoles','jueves','viernes','sábado'])[EXTRACT(DOW FROM c.fecha)::int + 1]
    || ', ' || EXTRACT(DAY FROM c.fecha)::int || ' de '
    || (ARRAY['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre',
              'octubre','noviembre','diciembre'])[EXTRACT(MONTH FROM c.fecha)::int] AS fecha_legible
FROM candidatas c
ORDER BY c.fecha, c.id;
