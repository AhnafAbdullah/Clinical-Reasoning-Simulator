"""Searchable investigation catalog (Vol 5 §15).

A static, case-independent list of orderable investigations. Ordering one in a
session still resolves against the *case* (three outcomes — see use_cases): the
catalog is only what the student can browse/search, not what will be informative.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    category: str


CATALOG: tuple[CatalogEntry, ...] = (
    # Bedside
    CatalogEntry("ECG", "bedside"),
    CatalogEntry("Blood Glucose (capillary)", "bedside"),
    CatalogEntry("Urinalysis", "bedside"),
    CatalogEntry("Peak Flow", "bedside"),
    # Laboratory
    CatalogEntry("Complete Blood Count", "laboratory"),
    CatalogEntry("Urea & Electrolytes", "laboratory"),
    CatalogEntry("Liver Function Tests", "laboratory"),
    CatalogEntry("Troponin I", "laboratory"),
    CatalogEntry("C-Reactive Protein", "laboratory"),
    CatalogEntry("Thyroid Function Tests", "laboratory"),
    CatalogEntry("Random Blood Glucose", "laboratory"),
    CatalogEntry("HbA1c", "laboratory"),
    CatalogEntry("Coagulation Profile", "laboratory"),
    CatalogEntry("D-Dimer", "laboratory"),
    CatalogEntry("Arterial Blood Gas", "laboratory"),
    CatalogEntry("Lipid Profile", "laboratory"),
    # Imaging
    CatalogEntry("Chest X-Ray", "imaging"),
    CatalogEntry("Abdominal Ultrasound", "imaging"),
    CatalogEntry("CT Head", "imaging"),
    CatalogEntry("CT Pulmonary Angiogram", "imaging"),
    CatalogEntry("Echocardiogram", "imaging"),
)


def search_catalog(*, query: str | None = None, category: str | None = None) -> list[CatalogEntry]:
    q = (query or "").strip().lower()
    cat = (category or "").strip().lower()
    results = []
    for entry in CATALOG:
        if cat and entry.category != cat:
            continue
        if q and q not in entry.name.lower():
            continue
        results.append(entry)
    return results
