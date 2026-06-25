# Bot Antinuke

Bot de Discord enfocado 100% en antinuke (18 módulos de protección) + comandos
de moderación básicos. Reacciona en milisegundos porque la configuración vive
en memoria (no consulta la base de datos en cada evento).

## 1. Crear la aplicación en Discord

1. Ve a https://discord.com/developers/applications y crea una aplicación.
2. En la pestaña **Bot**, activa estos 3 "Privileged Gateway Intents":
   - Server Members Intent
   - Message Content Intent
   - (Presence Intent no es necesaria)
3. Copia el **Token** del bot (lo vas a usar como `DISCORD_TOKEN`).
4. En **OAuth2 > URL Generator**, marca `bot`, y en permisos marca
   **Administrator** (el antinuke necesita poder expulsar, banear, gestionar
   roles/canales, etc. — sin permisos de administrador no puede proteger nada).
5. Usa la URL generada para invitar el bot a tu servidor.

## 2. Obtener tu ID de Discord (dueño del bot)

Activa el "Modo Desarrollador" en Discord (Ajustes > Avanzado), luego
clic derecho sobre tu perfil > "Copiar ID de usuario". Eso es tu `OWNER_ID`.

## 3. Subir el código a GitHub

```
git init
git add .
git commit -m "Bot antinuke inicial"
git branch -M main
git remote add origin https://github.com/tu-usuario/tu-repo.git
git push -u origin main
```

## 4. Desplegar en Railway

1. En https://railway.app crea un nuevo proyecto > "Deploy from GitHub repo"
   y selecciona tu repositorio.
2. Dentro del proyecto, clic en "+ New" > "Database" > "PostgreSQL".
   Railway crea la base y te da automáticamente la variable `DATABASE_URL`.
3. En el servicio del bot, ve a "Variables" y añade:
   - `DISCORD_TOKEN` = el token del paso 1
   - `OWNER_ID` = tu ID del paso 2
   - `PREFIX` = `.` (o el que prefieras)
   - `DATABASE_URL` se la puedes referenciar desde la base de Postgres
     (Railway te deja enlazar variables entre servicios) o copiarla manualmente.
4. Railway detecta el `Procfile` y ejecuta `python bot.py` solo.

## Notas importantes

- El antinuke detecta la acción y al **executor** vía el audit log de Discord;
  por eso el bot necesita el permiso de **Ver registro de auditoría**
  (incluido en Administrator).
- El `lockdown` bloquea el envío de mensajes en todos los canales de texto;
  al desactivarlo, vuelve los permisos a "por defecto" — si algún canal tenía
  un permiso personalizado distinto antes del lockdown, no se restaura exacto
  (limitación conocida, dímelo si necesitas que guarde el estado exacto).
- `backup restore` solo recrea los **roles** (nombre, color, permisos). Los
  canales no se recrean automáticamente porque el orden y las categorías son
  difíciles de reproducir fielmente sin riesgo de errores — si lo necesitas,
  lo añadimos como siguiente paso.
- Solo el dueño del servidor y el `OWNER_ID` (tú) pueden usar los comandos de
  `antinuke`, `whitelist`, `logs`, `lockdown` y `backup`. Los comandos de
  moderación usan los permisos normales de Discord (kick_members, etc.).    
