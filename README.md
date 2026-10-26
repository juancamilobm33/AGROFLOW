# Sistema de Inventario Agroflow

Sistema de inventario para una granja institucional con gestión de:

- Gallinas
- Vacas
- Cerdas

## Tecnologías

- Python
- Flask
- MySQL

## Estructura del proyecto

- `app.py`: aplicación principal de Flask
- `templates/`: vistas HTML
- `static/`: archivos CSS
- `db/schema.sql`: script de base de datos
- `requirements.txt`: dependencias del proyecto

## Requisitos

- Python 3.10+
- MySQL Server instalado y en ejecución

## Instalación

1. Crear entorno virtual:

```bash
python -m venv venv
source venv/bin/activate
```

En Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Crear base de datos en MySQL:

```sql
CREATE DATABASE agroflow_inventory;
```

4. Ajusta la conexión en `app.py` si tu usuario/contraseña son otros:

```python
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "agroflow_inventory",
}
```

5. Ejecuta la aplicación:

```bash
python app.py
```

Abrir en el navegador:

```text
http://localhost:5000
```

## Funcionalidades

- Inicio de sesión con roles de administrador y estudiante
- El estudiante puede consultar y agregar registros, pero no editarlos ni eliminarlos
- El administrador puede editar/eliminar registros y restablecer contraseñas desde Cuentas
- Control de alimento en kg por especie; compras exclusivas del administrador y alertas al quedar 15 kg o menos
- Registrar inventario por categoría
- Registrar diariamente el alimento suministrado y la leche recogida de las vacas
- Agregar plantas al inventario; los administradores pueden eliminarlas
- Consultar historiales cronológicos de gallinas, cerdas, vacas, plantas y compras de alimento
- Ver cantidades por especie
- Eliminar registros
- Visualizar total general

## Acceso y sesiones

Las cuentas iniciales se crean automáticamente al iniciar Flask. Las contraseñas se guardan como hashes en la tabla `usuarios`; no se muestran en el formulario de inicio de sesión. El SQL de `db/schema.sql` también crea esta tabla y prepara las cuentas iniciales.

El administrador puede restablecer la contraseña de cualquiera de las cuentas desde **Cuentas** después de iniciar sesión. El cambio requiere ingresar la contraseña nueva dos veces y debe tener al menos 10 caracteres.

El saldo de alimento se calcula como compras menos consumo: gallinas usa los kg del registro diario, cerdas estima 0.5 kg por lechón más 2 kg diarios de mantenimiento durante un máximo de 60 días desde el parto, y vacas usa su registro diario. El control de cerdas usa una sola tabla, `porcino_partos`; al ejecutar `db/schema.sql` se eliminan las tablas porcinas auxiliares anteriores. Las compras solo las puede ingresar el administrador; con 15 kg o menos se muestra alerta y con 10 kg o menos la alerta es urgente.

Para conservar las sesiones entre reinicios, configura una clave secreta antes de ejecutar Flask. En PowerShell:

```powershell
$env:AGROFLOW_SECRET_KEY = "una-clave-aleatoria-larga"
python app.py
```

Si no se configura, la aplicación genera una clave temporal y los usuarios tendrán que iniciar sesión otra vez al reiniciar el servidor.
