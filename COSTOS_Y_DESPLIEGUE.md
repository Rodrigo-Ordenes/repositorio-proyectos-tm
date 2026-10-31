# Alternativa inicial de dominio y publicación

Valores consultados el **30 de octubre de 2026**; pueden cambiar y el precio final depende del nombre disponible, impuestos y facturación en dólares.

## Recomendación de bajo costo

Un sitio y un dominio `.cl`, con dos rutas separadas (`/incentiva` y `/innova`). La aplicación ya incluye configuración inicial de despliegue en `render.yaml`.

| Ítem | Estimación | Por qué |
|---|---:|---|
| Dominio `.cl` en NIC Chile | **$9.990 CLP/año**, exento de IVA | NIC permite registrarlo directamente y administrar DNS desde su panel. |
| Web app Render, plan Starter | **US$7/mes** | Mantiene la aplicación activa. El plan gratuito se duerme después de 15 minutos y su sistema de archivos temporal pierde cambios, por eso no lo propongo para guardar sesiones y datos del curso. |
| Disco persistente Render, 1 GB | **aprox. US$0,25/mes** | Necesario para conservar SQLite tras reinicios y despliegues. El disco es de una instancia; es compatible con la arquitectura SQLite de un único servidor. |
| HTTPS/TLS en Render | **US$0** | Render administra y renueva el certificado TLS para el dominio conectado. |
| Correo transaccional Brevo Free | **US$0**, hasta 300 envíos diarios | Puede enviar los enlaces de acceso por SMTP/API. La cuenta gratuita añade marca Brevo y tiene cuota diaria; confirmar sender/domain antes de depender de ella. |

El gasto base estimado queda en **US$7,25 al mes + $9.990 CLP al año**, antes de impuestos/cargos de pago aplicables, aumento de almacenamiento o consumo extraordinario de red. No incluye compra de un nombre `.com` ni el precio de un remitente de correo propio. La tarifa de NIC se mantiene en pesos chilenos, exenta de IVA. No reservar ni pagar un dominio hasta comprobar disponibilidad y definir quién será titular.

## Por qué este despliegue

- Mantiene un solo enlace y dominio, pero separa las asignaturas por ruta y por permisos en el servidor.
- No depende de TI PUCV: Google OAuth se configura desde una cuenta del equipo y el correo institucional se limita a dominios PUCV. Si la organización bloquea la app, quedan códigos personales y enlaces de correo; cada responsable docente se configura en su proyecto.
- El disco persistente evita perder SQLite cuando el servicio se reinicia. Las copias de seguridad deben conservarse además en una ubicación controlada por el equipo docente.
- No usar el plan gratis para información que debe permanecer disponible: además de dormir, Render elimina archivos locales al reiniciar/re-desplegar si no hay un disco persistente.
- El alojamiento entrega una URL pública; **el portal no queda abierto**: las páginas de curso y sus APIs requieren sesión, y el acceso al curso necesita aprobación docente. Mantener HTTPS, SMTP y la revisión docente habilitados.

## Pasos cuando se decida publicar

1. Elegir un nombre de dominio neutral y comprobar que esté disponible en [NIC Chile](https://www.nic.cl/dominios/). Evitar usar la marca PUCV en el nombre si no se cuenta con autorización para representarla.
2. Crear una cuenta Render y desplegar este repositorio mediante Blueprint (`render.yaml`). Elegir el plan Starter y mantener un único servicio/instancia.
3. Enlazar el dominio al servicio Render y actualizar DNS según las instrucciones de Render. Esperar la emisión de TLS y comprobar que `APP_BASE_URL` use `https://`.
4. Crear cuenta de envío transaccional (por ejemplo, Brevo), validar un remitente/dominio y copiar SMTP host, user, password y from a los secretos de Render. No guardarlos en el código.
5. Configurar correo de administración global, responsables de Incentiva e Innova, y probar la solicitud, aprobación, rechazo y revocación de accesos con cuentas institucionales de prueba.
6. Crear la copia inicial de SQLite y programar una copia periódica externa. La salida diaria de correos, el archivo SQLite y los videos deben tener responsable operativo.
7. Confirmar quién será titular/pagador del dominio y hosting, quién recibe solicitudes de acceso de cada asignatura y cuánto tiempo se conservarán entregas y cuentas.

## Limitación de identidad PUCV

El enlace mágico comprueba que la persona controla un buzón `@mail.pucv.cl` o `@pucv.cl`; no demuestra matrícula o relación vigente. La aprobación manual por asignatura reduce accesos indebidos. Si se exige que solo estudiantes actuales entren, la docente tendría que contrastar las solicitudes con las listas del curso y aprobarlas; esta versión no se conecta a sistemas PUCV.

## Fuentes oficiales de precio y condiciones

- [NIC Chile: tarifas .CL](https://nic.cl/dominios/tarifas.html)
- [Render: planes y precios](https://render.com/pricing)
- [Render: discos persistentes](https://render.com/docs/disks)
- [Render: dominios personalizados y TLS](https://render.com/docs/custom-domains)
- [Render: límites del plan gratuito](https://render.com/docs/free)
- [Brevo: planes, correo transaccional y cuota](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans)
