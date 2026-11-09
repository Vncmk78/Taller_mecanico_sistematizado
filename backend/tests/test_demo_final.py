"""El perfil final nunca reutiliza puertos, volúmenes, bucket ni configuración."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import demo_final as demo
from scripts import ambiente_pruebas as amb


def test_perfil_final_aislado_y_marca_sql(tmp_path, monkeypatch):
    falso = SimpleNamespace(BACKEND_DIR=amb.BACKEND_DIR, PLANTILLA=amb.PLANTILLA,
        COMPOSE=amb.COMPOSE, PUERTOS_EXISTENTES=set(amb.PUERTOS_EXISTENTES),
        URLS_ESPERADAS=dict(amb.URLS_ESPERADAS), ErrorAmbiente=amb.ErrorAmbiente)
    carpeta = tmp_path / '.demo-final'
    monkeypatch.setattr(demo, 'CARPETA', carpeta)
    monkeypatch.setattr(demo, 'amb', falso)
    demo.preparar_perfil()
    compose = (carpeta / 'compose.yml').read_text()
    assert 'name: sgtm_demo_final' in compose
    assert 'sgtm_pruebas_' not in compose
    assert 'evidencias-pruebas' not in compose
    assert '127.0.0.1:5453:5432' in compose
    assert '127.0.0.1:9020:9000' in compose
    assert falso.PUERTOS_PERMITIDOS.isdisjoint({5443,5444,5445,5446,8100,8101,8102,8103,8104,9010,9011,5183})
    assert falso.ARCHIVO == carpeta / '.env'
    assert falso.URLS_ESPERADAS['MS2_MS1_URL'] == 8301
    assert falso.URLS_ESPERADAS['MS4_S3_ENDPOINT'] == 9020
    assert 'sgtm-ambiente-demo-final' in (carpeta / 'initdb/01-marcar-ambiente.sql').read_text()
    assert not (carpeta / 'initdb/01-marcar-ambiente.sh').exists()
    assert not falso.ARCHIVO.exists()  # configurar es una operación separada


def test_no_reutiliza_carpeta_ajena(tmp_path, monkeypatch):
    carpeta = tmp_path / 'existente'
    carpeta.mkdir()
    archivo = carpeta / 'guardar.txt'
    archivo.write_text('Trabajo anterior')
    monkeypatch.setattr(demo, 'CARPETA', carpeta)
    with pytest.raises(amb.ErrorAmbiente, match='no se modifica'):
        demo.preparar_perfil()
    assert archivo.read_text() == 'Trabajo anterior'
    assert list(carpeta.iterdir()) == [archivo]
