"""HTTP representations for manual metadata and page evidence."""

from pydantic import BaseModel, ConfigDict, Field

from domain.models.evidence import PageEvidence


class _ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegionResponse(_ResponseModel):
    """One verified region normalized against the visible PDF page."""

    x0: float = Field(ge=0.0, le=1.0)
    y0: float = Field(ge=0.0, le=1.0)
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)


class ManualResponse(_ResponseModel):
    """Metadata for the explicitly active registered manual."""

    document_id: str
    version: str
    filename: str
    page_count: int
    pdf_url: str


class EvidenceResponse(_ResponseModel):
    """Navigable source evidence without internal filesystem paths."""

    evidence_id: str
    document_hash: str
    pdf_page: int
    printed_label: str | None
    text: str
    regions: tuple[RegionResponse, ...]
    pdf_url: str

    @classmethod
    def from_domain(cls, page: PageEvidence) -> EvidenceResponse:
        """Normalize verified point coordinates for the browser PDF viewport."""

        regions: tuple[RegionResponse, ...] = ()
        if page.regions:
            if page.width is None or page.height is None or page.width <= 0 or page.height <= 0:
                raise ValueError("Evidence regions require positive page dimensions")
            regions = tuple(
                _normalize_region(region, width=page.width, height=page.height)
                for region in page.regions
            )
        return cls(
            evidence_id=page.evidence_id,
            document_hash=page.document_hash,
            pdf_page=page.pdf_page,
            printed_label=page.printed_label,
            text=page.text,
            regions=regions,
            pdf_url=f"/api/v1/manual/pdf?version={page.document_hash}",
        )


def _normalize_region(
    region: tuple[float, float, float, float], *, width: float, height: float
) -> RegionResponse:
    x0, y0, x1, y1 = region
    if not (0.0 <= x0 <= x1 <= width and 0.0 <= y0 <= y1 <= height):
        raise ValueError("Evidence region lies outside the visible page")
    return RegionResponse(x0=x0 / width, y0=y0 / height, x1=x1 / width, y1=y1 / height)
