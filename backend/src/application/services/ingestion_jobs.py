"""Application service facade for persisted ingestion jobs."""

from __future__ import annotations

from dataclasses import dataclass

from application.models.ingestion import IngestionJob, IngestionJobStore, IngestionSnapshot


@dataclass(frozen=True, slots=True)
class IngestionJobService:
    store: IngestionJobStore

    def snapshot(self) -> IngestionSnapshot:
        return self.store.load()

    def start(self) -> IngestionJob:
        return self.store.start()
