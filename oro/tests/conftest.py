"""Fixtures compartidas de las pruebas."""

from __future__ import annotations

import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico


@pytest.fixture(scope="session")
def cfg():
    return cargar_configuracion()


@pytest.fixture(scope="session")
def df_pequeno():
    """Histórico sintético pequeño para pruebas rápidas."""
    return ProveedorSintetico(velas=1500, semilla=123).historico(1500)


@pytest.fixture(scope="session")
def df_medio():
    return ProveedorSintetico(velas=4000, semilla=123).historico(4000)


@pytest.fixture(autouse=True)
def _aislar_ficheros(tmp_path, monkeypatch):
    """Aísla cada prueba de los ficheros REALES del sistema.

    Sin esto, cualquier prueba que cierre una operación escribía en el
    ``operaciones_oro.jsonl`` del repositorio —el registro real que alimenta el
    aprendizaje— y lo contaminaba con datos sintéticos. Al ejecutar cada prueba
    en un directorio temporal, los ficheros de ruta relativa (registro, estado,
    modelo) se crean y se descartan allí.
    """
    monkeypatch.chdir(tmp_path)



@pytest.fixture(autouse=True)
def _sin_lbma_en_red(monkeypatch):
    """Las pruebas no salen a gold.org.

    El árbitro del LBMA se llama al construir el plan, así que sin esto cada
    prueba de punta a punta haría una petición de red: lenta, y dependiente de
    que la web responda. Las pruebas del árbitro ponen su propia serie.
    """
    monkeypatch.setattr("oro.referencia.serie_fix", lambda **kw: {})
