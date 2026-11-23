import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hook_ruff_se_ejecuta_en_entorno_aislado():
    ruff_directo = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ruff_directo.returncode == 0, (
        "Ruff debe pasar al ejecutarse directamente antes de comprobar el hook:\n"
        f"{ruff_directo.stdout}\n{ruff_directo.stderr}"
    )

    pre_commit = shutil.which("pre-commit")
    assert pre_commit is not None, "Pre-commit debe estar instalado para probar el hook."

    resultado = subprocess.run(
        [pre_commit, "run", "ruff", "--all-files"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    salida = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, (
        "El hook de Ruff debe ejecutarse correctamente en su entorno aislado.\n"
        f"código de salida: {resultado.returncode}\n{salida}"
    )
    assert re.search(r"(?m)^Ruff.*Passed$", salida), (
        "Pre-commit debe informar que el hook Ruff pasó.\n" + salida
    )


def test_hook_pytest_se_ejecuta_en_entorno_aislado():
    if os.environ.get("RETO0_TESTING_PYTEST_HOOK"):
        return

    pre_commit = shutil.which("pre-commit")
    assert pre_commit is not None, "Pre-commit debe estar instalado para probar el hook."

    entorno = os.environ.copy()
    entorno["RETO0_TESTING_PYTEST_HOOK"] = "1"
    resultado = subprocess.run(
        [pre_commit, "run", "pytest", "--all-files"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=entorno,
    )
    salida = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, (
        "El hook de pytest debe ejecutarse correctamente en su entorno aislado.\n"
        f"código de salida: {resultado.returncode}\n{salida}"
    )
    assert re.search(r"(?m)^Pruebas.*Passed$", salida), (
        "Pre-commit debe informar que el hook pytest pasó.\n" + salida
    )


def test_hooks_no_dependen_de_herramientas_externas_a_pre_commit():
    configuracion = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    bloques = {
        coincidencia.group("id"): coincidencia.group("contenido")
        for coincidencia in re.finditer(
            r"(?ms)^      - id: (?P<id>ruff|pytest)\r?\n"
            r"(?P<contenido>.*?)(?=^      - id: |\Z)",
            configuracion,
        )
    }
    assert set(bloques) == {"ruff", "pytest"}, (
        "Se esperaban los hooks existentes de Ruff y pytest para verificar su "
        "dependencia común."
    )

    entradas_esperadas = {"ruff": "ruff check .", "pytest": "python -m pytest -q"}
    hooks_externos = []
    for hook_id, entrada_esperada in entradas_esperadas.items():
        bloque = bloques[hook_id]
        entrada = re.search(r"(?m)^        entry: (.+)$", bloque)
        lenguaje = re.search(r"(?m)^        language: (.+)$", bloque)
        assert entrada and entrada.group(1) == entrada_esperada, (
            f"La entrada del hook {hook_id} cambió; no se puede atribuir este "
            "hallazgo a la dependencia identificada."
        )
        assert lenguaje, f"El hook {hook_id} no declara un lenguaje."
        if lenguaje.group(1) == "system":
            hooks_externos.append(hook_id)

    assert not hooks_externos, (
        f"Los hooks {', '.join(hooks_externos)} usan language: system y dependen de "
        "herramientas externas al entorno de Pre-commit. Este hallazgo se solapa "
        "con los fallos 1 y 2 de AUDITORIA.md; no es una causa independiente."
    )
