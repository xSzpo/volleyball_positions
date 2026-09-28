"""Write SVG as PDF with fixed metadata, so regenerating an unchanged SVG gives identical bytes."""

from pathlib import Path

import cairocffi
from cairosvg.parser import Tree
from cairosvg.surface import PDFSurface

CREATE_DATE = "2026-01-01T00:00:00Z"


def svg_to_pdf(svg: str, path: Path) -> None:
    with path.open("wb") as output:
        surface = PDFSurface(Tree(bytestring=svg.encode()), output, 96)
        surface.cairo.set_metadata(cairocffi.PDF_METADATA_CREATE_DATE, CREATE_DATE)
        surface.finish()
