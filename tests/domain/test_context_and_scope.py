from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime, timezone

import pytest

from app.domain.value_objects import ContextChunk, RetrievedContext
from app.domain.value_objects.export_scope import ExportArtifact, ExportScope
from app.domain.exceptions.erasure_exceptions import InvalidErasureManifestError
from app.domain.value_objects.erasure_manifest import ErasedRecordCount, ErasureManifest
from app.domain.types import EmbeddingSourceType, ErasedResource, ExportFormat, ExportSection
from app.domain.exceptions.export_exceptions import EmptyExportScopeError, InvalidExportPeriodError


def build_chunk(text: str = "Almoço em 12/08", similarity: Decimal = Decimal("0.82")) -> ContextChunk:
    return ContextChunk(
        source_id=uuid4(),
        context_text=text,
        similarity=similarity,
        source_type=EmbeddingSourceType.TRANSACTION
    )


class TestContextChunk:

    def test_similarity_at_the_threshold_is_relevant(self) -> None:
        assert build_chunk(similarity=Decimal("0.70")).is_relevant(minimum_similarity=Decimal("0.70")) is True

    def test_nearest_neighbour_below_the_threshold_is_not_relevant(self) -> None:
        assert build_chunk(similarity=Decimal("0.31")).is_relevant(minimum_similarity=Decimal("0.70")) is False


class TestRetrievedContext:

    def test_empty_context_blocks_the_inference(self) -> None:
        context = RetrievedContext(chunks=[])

        assert context.is_empty is True
        assert context.source_ids == []
        assert context.to_prompt_text(max_characters=1000) == ""

    def test_prompt_enumerates_the_chunks_in_order(self) -> None:
        first = build_chunk(text="primeiro")
        second = build_chunk(text="segundo")

        prompt = RetrievedContext(chunks=[first, second]).to_prompt_text(max_characters=1000)

        assert prompt.splitlines()[0].startswith("[1] (transaction) primeiro")
        assert prompt.splitlines()[1].startswith("[2] (transaction) segundo")

    def test_prompt_is_truncated_at_the_configured_ceiling(self) -> None:
        chunks = [build_chunk(text="x" * 40) for _ in range(5)]

        prompt = RetrievedContext(chunks=chunks).to_prompt_text(max_characters=120)

        assert len(prompt.splitlines()) == 2

    def test_source_ids_preserve_the_relevance_order(self) -> None:
        first = build_chunk()
        second = build_chunk()

        assert RetrievedContext(chunks=[first, second]).source_ids == [first.source_id, second.source_id]


class TestExportScope:

    def test_absent_sections_mean_the_full_dossier(self) -> None:
        scope = ExportScope.build()

        assert scope.is_full_dossier is True
        assert scope.has_period is False

    def test_empty_sections_are_refused(self) -> None:
        with pytest.raises(EmptyExportScopeError):
            ExportScope.build(sections=[])

    def test_inverted_period_is_refused(self) -> None:
        with pytest.raises(InvalidExportPeriodError):
            ExportScope.build(start_date=date(2026, 5, 1), end_date=date(2026, 4, 1))

    def test_sections_are_returned_in_canonical_order(self) -> None:
        scope = ExportScope.build(sections=[ExportSection.GOALS, ExportSection.PROFILE])

        assert scope.ordered_sections == [ExportSection.PROFILE, ExportSection.GOALS]

    def test_label_describes_sections_and_window(self) -> None:
        scope = ExportScope.build(sections=[ExportSection.PROFILE], start_date=date(2026, 1, 1))

        assert scope.label == "PROFILE@2026-01-01..*"

    def test_covers_answers_by_section(self) -> None:
        scope = ExportScope.build(sections=[ExportSection.ASSETS])

        assert scope.covers(section=ExportSection.ASSETS) is True
        assert scope.covers(section=ExportSection.GOALS) is False


class TestExportArtifact:

    def test_checksum_and_size_derive_from_the_content(self) -> None:
        artifact = ExportArtifact.build(
            content=b"conteudo",
            file_path="/tmp/a.json",
            file_name="a.json",
            media_type="application/json",
            total_records=3
        )

        assert artifact.byte_size == 8
        assert len(artifact.checksum) == 64
        assert artifact.entity_tag == f'"sha256:{artifact.checksum}"'

    def test_identical_content_yields_an_identical_validator(self) -> None:
        first = ExportArtifact.build(
            content=b"igual",
            file_path="/tmp/a.csv",
            file_name="a.csv",
            media_type="text/csv",
            total_records=1
        )
        second = ExportArtifact.build(
            content=b"igual",
            file_path="/tmp/b.csv",
            file_name="b.csv",
            media_type="text/csv",
            total_records=1
        )

        assert first.entity_tag == second.entity_tag

    def test_file_name_is_deterministic_for_the_same_instant(self) -> None:
        user_id = uuid4()
        generated_at = datetime(2026, 8, 14, 10, 30, 0, tzinfo=timezone.utc)

        name = ExportArtifact.compose_file_name(
            user_id=user_id,
            generated_at=generated_at,
            export_format=ExportFormat.PDF
        )

        assert name == f"controla-ai-export-{user_id}-20260814103000.pdf"

    def test_extension_follows_the_requested_format(self) -> None:
        name = ExportArtifact.compose_file_name(
            user_id=uuid4(),
            generated_at=datetime(2026, 8, 14, 10, 30, 0, tzinfo=timezone.utc),
            export_format=ExportFormat.CSV
        )

        assert name.endswith(".csv")


class TestErasureManifest:

    def test_rejects_negative_count(self) -> None:
        with pytest.raises(InvalidErasureManifestError):
            ErasedRecordCount(resource=ErasedResource.TRANSACTIONS, total=-1)

    def test_manifest_covers_every_resource_in_canonical_order(self) -> None:
        manifest = ErasureManifest.build(totals={ErasedResource.TRANSACTIONS: 12})

        assert [count.resource for count in manifest.counts] == ErasedResource.canonical_order()
        assert manifest.total_of(resource=ErasedResource.TRANSACTIONS) == 12
        assert manifest.total_of(resource=ErasedResource.GOALS) == 0
        assert manifest.total_records == 12

    def test_label_omits_resources_without_records(self) -> None:
        manifest = ErasureManifest.build(
            totals={ErasedResource.TRANSACTIONS: 2, ErasedResource.RECEIPTS: 1}
        )

        assert manifest.label == "TRANSACTIONS=2,RECEIPTS=1"

    def test_purge_is_complete_when_no_byte_survives(self) -> None:
        manifest = ErasureManifest.build(totals={}, purged_files=["a.png", "b.pdf"])

        assert manifest.total_purged_files == 2
        assert manifest.is_complete is True
        assert manifest.outcome == "COMPLETE"

    def test_retained_file_degrades_the_outcome_to_partial(self) -> None:
        manifest = ErasureManifest.build(totals={}, purged_files=["a.png"], retained_files=["b.pdf"])

        assert manifest.is_complete is False
        assert manifest.outcome == "PARTIAL"

    def test_resource_totals_are_ready_for_serialization(self) -> None:
        totals = ErasureManifest.build(totals={ErasedResource.ASSETS: 3}).as_resource_totals()

        assert ("ASSETS", 3) in totals
