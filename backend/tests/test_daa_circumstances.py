"""The D.A.A. code catalogue is a reviewed external input to CIDE lookup."""

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CATALOGUE = _REPO / "data" / "rules" / "daa-circumstances.v1.json"


def test_shipped_daa_catalogue_keeps_the_human_validated_mapping() -> None:
    """A0 is no selection; A1-A17 are the standard D.A.A. checklist."""
    payload = json.loads(_CATALOGUE.read_text(encoding="utf-8"))

    assert payload["provenance"] == "external-daa-form"
    assert payload["in_manual_scope"] is False
    assert [(item["code"], item["label"]) for item in payload["circumstances"]] == [
        ("A0", "Sin circunstancia declarada"),
        ("A1", "Estaba estacionado o parado"),
        ("A2", "Salía de un estacionamiento o abría una puerta"),
        ("A3", "Iba a estacionar"),
        ("A4", "Salía de un aparcamiento, lugar privado o camino de tierra"),
        ("A5", "Entraba a un aparcamiento, lugar privado o camino de tierra"),
        ("A6", "Entraba en una rotonda"),
        ("A7", "Circulaba por una rotonda"),
        ("A8", "Golpeó por detrás a otro vehículo en el mismo sentido y carril"),
        ("A9", "Circulaba en el mismo sentido, pero en carril distinto"),
        ("A10", "Cambiaba de carril"),
        ("A11", "Adelantaba"),
        ("A12", "Giraba a la derecha"),
        ("A13", "Giraba a la izquierda"),
        ("A14", "Daba marcha atrás"),
        ("A15", "Invadía el carril del sentido contrario"),
        ("A16", "Venía de la derecha en un cruce"),
        ("A17", "No respetó una señal de preferencia o un semáforo en rojo"),
    ]


def test_daa_catalogue_marks_a0_as_a_non_manoeuvre() -> None:
    """The zero index must never be presented as a manoeuvre from the form."""
    payload = json.loads(_CATALOGUE.read_text(encoding="utf-8"))

    zero = payload["circumstances"][0]
    assert zero["code"] == "A0"
    assert zero["is_daa_checkbox"] is False
    assert "no existe" in zero["note"].lower()
