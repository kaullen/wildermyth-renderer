# -*- encoding: utf-8 -*-

import dataclasses
import enum
from pathlib import Path
from typing import List
from typing import Optional
from typing import Tuple


class RelationshipStatus(enum.IntEnum):
    PAST = 0
    LOCKED = 1


@dataclasses.dataclass(frozen=True)
class FilterParams:
    """
    Parameters used for filtering relationship charts
    """

    include_relationships: Optional[List[Tuple[RelationshipStatus, str]]] = None
    exclude_relationships: Optional[List[Tuple[RelationshipStatus, str]]] = None

    include_heroes: Optional[List[str]] = None
    exclude_heroes: Optional[List[str]] = None


@dataclasses.dataclass(frozen=True)
class RendererParams:
    """
    Parameters used for rendering graphs
    """

    output_path: Path

    norender: bool = False

    render_dir: Optional[Path] = None
    clean_tmp_files: bool = False

    gender_shapes: bool = True
    class_colors: bool = True

    include_legend: bool = False

    prioritize_relationships: bool = False
    hide_phantoms: bool = False

    pack_graph: bool = False
    pack_by_subgraphs: bool = False

    @property
    def graph_name(self) -> str:
        return f"{self.output_path.stem}_graph"

    def get_render_dir(self) -> Path:
        if self.render_dir is not None:
            return self.render_dir
        return self.output_path.parent
