# Diseño: registro de auditoría global

## Intención

Dar a administración global un historial de accesos y cambios sensibles del sitio durante 180 días, con actor, persona afectada cuando corresponda, asignatura, fecha y una huella de IP no reversible sin la sal. El equipo docente de una asignatura seguirá viendo solo los ingresos de sus propios códigos.

## Enfoque

Ampliar la tabla aditiva `audit_events` que ya registra los ingresos con códigos. Añadir eventos para ingreso SOS, creación y desactivación efectiva de códigos, alta y retiro de roles docentes, retiro de acceso y anonimización de una persona o cohorte. Guardar únicamente `HMAC-SHA-256(IP, sal)`; generar una sal aleatoria por instalación y persistirla en `settings`, fuera de Git. Exponer una API nueva protegida por `role='admin'` y una tabla paginada dentro del panel de administración, para recorrer todos los eventos que sigan dentro del plazo.

Los mensajes HTTP de consola dejarán de incluir IP remota en claro, incluido el ingreso SOS. No se registran eventos de acciones rechazadas ni operaciones que no modifican datos.

## Alternativas consideradas

- Guardar IP en claro: descartado porque contradice el encargo y facilita identificar dispositivos.
- Hash sin sal o con sal fija en código: descartado por permitir correlación o ataques de diccionario entre instalaciones.
- Reutilizar `audit_events` y su retención: elegido porque ya contiene los accesos por código y tiene plazo de 180 días; evita una segunda fuente de datos.

## Límites

- SQLite y servidor estándar actuales; esquema aditivo.
- Solo administración global puede consultar el historial consolidado.
- Docentes siguen limitados por asignatura en la vista de ingresos por código.
- No registrar IP en claro, ni modificar cookies, CSP, validación de origen o tablas anónimas.
- Sin dependencias, sin publicación de borradores de privacidad, desafíos, encuestas o rúbricas.

## Validación

La prueba HTTP se escribirá primero. Debe comprobar los seis grupos de eventos, permisos globales, retención de 180 días, ausencia de IP en claro y una huella HMAC verificable con la sal persistida. Ejecutar la suite completa y revisar `.gitignore` antes del commit.
