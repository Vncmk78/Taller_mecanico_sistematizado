"""Suite backend completa con PostgreSQL y MinIO aislados.

Uso, desde backend, después de ambiente_pruebas.py configurar e infra:
    python scripts/verificar_backend.py

Crea bases verificar_suite_* y elimina solo las creadas por esta ejecución.
Las pruebas S3 crean sus propios buckets. No usa datos de la demostración.
"""
import os, subprocess, sys
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

raiz = Path(__file__).resolve().parents[1]
os.chdir(raiz)
config = dotenv_values(raiz / '.env.pruebas')
nombres = {2: 'verificar_suite_ms2', 3: 'verificar_suite_ms3'}
urls = {}
creadas = []
try:
    for n, nombre in nombres.items():
        origen = make_url(config[f'MS{n}_DATABASE_URL'])
        assert origen.host in ('127.0.0.1', 'localhost') and origen.port == 5442+n
        admin_url = origen.set(database='postgres')
        admin = create_engine(admin_url, isolation_level='AUTOCOMMIT')
        with admin.connect() as c:
            assert not c.scalar(text('SELECT 1 FROM pg_database WHERE datname=:nombre'), {'nombre': nombre}), 'Base ya existente; no se toca'
            c.execute(text(f'CREATE DATABASE "{nombre}"'))
        creadas.append((admin, nombre))
        urls[n] = origen.set(database=nombre).render_as_string(hide_password=False)
    prefijos = ('MS1_', 'MS2_', 'MS3_', 'MS4_', 'GATEWAY_', 'SGTM_', 'APP_TEST_', 'SCRUM397438_', 'REGISTRO_ORDEN_', 'PERFIL_CLIENTE_', 'INTEGRIDAD_PG_')
    entorno = {k:v for k,v in os.environ.items() if not k.startswith(prefijos)}
    entorno.update(SGTM_ENV_FILE='/dev/null', MS2_EVENT_WORKER_ENABLED='false')
    entorno.update({
        'MS2_MIGRATION_TEST_DATABASE_URL': urls[2],
        'MS3_ORM_TEST_DATABASE_URL': urls[3],
        'PERFIL_CLIENTE_MS2_TEST_URL': urls[2],
        'REGISTRO_ORDEN_MS2_TEST_URL': urls[2],
        'SCRUM397438_MS2_TEST_URL': urls[2],
        'SCRUM397438_MS3_TEST_URL': urls[3],
        'INTEGRIDAD_PG_ADMIN_URL': make_url(config['MS2_DATABASE_URL']).set(database='postgres').render_as_string(hide_password=False),
        'MS4_TEST_S3_ENDPOINT': config['MS4_S3_ENDPOINT'],
        'MS4_TEST_S3_ADMIN_ACCESS_KEY': config['PRUEBAS_MINIO_ROOT_USUARIO'],
        'MS4_TEST_S3_ADMIN_SECRET_KEY': config['PRUEBAS_MINIO_ROOT_CLAVE'],
        'MS4_TEST_S3_REGION': 'us-east-1',
        'MS4_TEST_S3_MS4_ACCESS_KEY': config['MS4_S3_ACCESS_KEY'],
        'MS4_TEST_S3_MS4_SECRET_KEY': config['MS4_S3_SECRET_KEY'],
    })
    # Los modelos ORM reales necesitan su esquema público, además de los esquemas
    # que cada fixture de integración crea y elimina por su cuenta.
    codigo = '''
import os
from sqlalchemy import create_engine
from alembic import command
from alembic.config import Config
for n, ruta in [(2, 'ms2_taller'), (3, 'ms3_presupuestos')]:
    engine=create_engine(os.environ[f'SCRUM397438_MS{n}_TEST_URL'])
    with engine.begin() as conexion:
        cfg=Config(); cfg.set_main_option('script_location', f'services/{ruta}/alembic')
        cfg.attributes['connection']=conexion
        command.upgrade(cfg, 'head')
    engine.dispose()
'''
    for n in range(1,5):
        entorno[f'MS{n}_JWT_SECRET_KEY'] = f'clave-secreta-exclusiva-para-pruebas-de-ms{n}-123456'
    migracion_env = dict(entorno)
    for n in range(1,5):
        migracion_env[f'MS{n}_JWT_SECRET_KEY'] = f'clave-secreta-exclusiva-para-pruebas-de-ms{n}-123456'
    subprocess.run([sys.executable,'-c',codigo],env=migracion_env,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    objetivos = sys.argv[1:] or ['tests','services']
    log = raiz / '.pruebas/logs/suite-backend.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as salida:
        resultado=subprocess.run([sys.executable,'-m','pytest',*objetivos,'-q','-rs','--tb=short','--junitxml=.pruebas/logs/suite-backend.xml'],env=entorno,stdout=salida,stderr=subprocess.STDOUT)
    print('\n'.join(log.read_text().splitlines()[-65:]))
    estado=resultado.returncode
finally:
    for admin, nombre in reversed(creadas):
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE "{nombre}"'))
        admin.dispose()
    print('Bases privadas de esta ejecución eliminadas; demostración intacta.')
sys.exit(estado)
