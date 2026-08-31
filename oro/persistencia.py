"""Guardado del estado en el repositorio, a prueba de conflictos.

Por qué existe este módulo (caso real del 24-ago-2026): el vigilante envió un
aviso de COMPRA y, al guardar, el `git rebase` chocó con el estado que otra
ejecución acababa de subir. El rebase se abortó, el push falló y **la operación
se perdió en silencio**: ninguna ejecución posterior supo que estaba abierta, así
que el aviso de SALIDA no llegó nunca. El paso del workflow, además, terminó en
"éxito" porque el fallo se tragaba con un `echo`.

La lección: el estado NO se puede fusionar como si fuera código. Aquí:

* Nunca se hace rebase del estado. Nos colocamos sobre lo último del remoto y
  **nuestro estado manda** (es el del proceso vivo, el más reciente).
* El registro de operaciones es un histórico que solo crece: se UNEN las líneas
  nuestras y las del remoto, sin perder ninguna.
* Si aun así no se puede guardar, se avisa ALTO Y CLARO (y el proceso lo
  comunica), porque un guardado perdido significa una operación sin vigilancia.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

RUTA_ESTADO = "oro_estado.json"
RUTA_OPERACIONES = "operaciones_oro.jsonl"


def _git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(("git",) + args, capture_output=True, text=True, timeout=timeout)


def _leer(ruta: str) -> str | None:
    p = Path(ruta)
    try:
        return p.read_text(encoding="utf-8") if p.exists() else None
    except OSError:
        return None


def _unir_jsonl(nuestro: str | None, remoto: str | None) -> str | None:
    """Une dos históricos append-only sin perder líneas ni duplicarlas."""
    if nuestro is None:
        return remoto
    if remoto is None:
        return nuestro
    vistas, salida = set(), []
    for bloque in (remoto, nuestro):          # remoto primero: preserva el orden histórico
        for linea in bloque.splitlines():
            linea = linea.strip()
            if linea and linea not in vistas:
                vistas.add(linea)
                salida.append(linea)
    return "\n".join(salida) + "\n"


def guardar_ficheros(ficheros: list[str], mensaje: str, intentos: int = 4) -> bool:
    """Sube ficheros CUALESQUIERA con la misma estrategia a prueba de conflictos.

    La usa el aprendizaje mensual (modelo + informe), que antes hacía su propio
    rebase y podía tirar el modelo recién aprendido sin avisar —y no reintentaba
    hasta el mes siguiente—.
    """
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return False
    nuestros = {f: Path(f).read_bytes() for f in ficheros if Path(f).exists()}
    if not nuestros:
        return False

    _git("config", "user.name", "oro-aprendizaje-bot")
    _git("config", "user.email", "actions@users.noreply.github.com")

    for _ in range(intentos):
        if _git("fetch", "origin", "main", timeout=90).returncode != 0:
            time.sleep(2)
            continue
        _git("reset", "--hard", "origin/main")
        for f, datos in nuestros.items():
            Path(f).write_bytes(datos)          # lo nuestro manda
            _git("add", "-f", f)
        if _git("diff", "--cached", "--quiet").returncode == 0:
            return False
        if _git("commit", "-m", mensaje).returncode != 0:
            time.sleep(2)
            continue
        if _git("push", timeout=90).returncode == 0:
            return True
        time.sleep(2)
    print("⚠️  NO se pudo guardar:", ", ".join(nuestros))
    return False


def guardar_en_repo(ruta_estado: str = RUTA_ESTADO, intentos: int = 4) -> bool:
    """Sube estado y registro al repositorio. True si se guardó algo.

    Fuera de un repositorio con remoto (uso local) devuelve False sin molestar.
    """
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return False

    estado_nuestro = _leer(ruta_estado)
    ops_nuestro = _leer(RUTA_OPERACIONES)
    if estado_nuestro is None and ops_nuestro is None:
        return False

    # No subir un estado ilegible: machacaría la copia BUENA del remoto con
    # basura y perdería las operaciones abiertas de todas las máquinas. El
    # runner siempre escribe JSON válido, así que llegar aquí con algo ilegible
    # significa disco corrupto o escritura a medias: mejor conservar el remoto.
    if estado_nuestro is not None:
        import json as _json
        try:
            _json.loads(estado_nuestro)
        except ValueError:
            print(f"⚠️  {ruta_estado} no es JSON válido: NO se sube "
                  f"(se conserva la versión del repositorio).")
            estado_nuestro = None
            if ops_nuestro is None:
                return False

    _git("config", "user.name", "oro-alertas-bot")
    _git("config", "user.email", "actions@users.noreply.github.com")

    for intento in range(1, intentos + 1):
        # 1) Colocarse sobre lo ÚLTIMO del remoto (sin rebase: nada que chocar).
        if _git("fetch", "origin", "main", timeout=90).returncode != 0:
            time.sleep(2)
            continue
        _git("reset", "--hard", "origin/main")

        # 2) Reescribir: el estado es del proceso vivo; el registro se une.
        if estado_nuestro is not None:
            Path(ruta_estado).write_text(estado_nuestro, encoding="utf-8")
        unido = _unir_jsonl(ops_nuestro, _leer(RUTA_OPERACIONES))
        if unido is not None:
            Path(RUTA_OPERACIONES).write_text(unido, encoding="utf-8")

        # 3) Preparar cada fichero por separado (uno ausente no aborta el otro).
        _git("add", "-f", ruta_estado)
        _git("add", "-f", RUTA_OPERACIONES)
        if _git("diff", "--cached", "--quiet").returncode == 0:
            return False  # nada que guardar

        if _git("commit", "-m", "Estado y registro de señales XAU/USD [skip ci]").returncode != 0:
            time.sleep(2)
            continue
        if _git("push", timeout=90).returncode == 0:
            return True
        time.sleep(2)  # alguien se adelantó: reintentar sobre el nuevo remoto

    print("⚠️  ATENCIÓN: NO se pudo guardar el estado tras varios intentos. "
          "Si hay una operación abierta puede quedarse SIN VIGILANCIA: revísala "
          "a mano en el bróker.")
    return False


def main() -> int:
    import sys
    if "--aprendizaje" in sys.argv[1:]:
        ok = guardar_ficheros(
            ["modelo_oro.pkl", "aprendizaje_estado.json"],
            "Aprendizaje XAU/USD: actualización del modelo/estado [skip ci]")
        print("Modelo/estado de aprendizaje guardado." if ok
              else "El aprendizaje no cambió el modelo (sin ventaja nueva demostrable).")
        return 0
    guardado = guardar_en_repo()
    print("Estado guardado en el repositorio." if guardado else "Sin cambios que guardar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
