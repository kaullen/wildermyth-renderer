#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import logging
import sys
import zipfile
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Tuple

from wildermyth_renderer import CharacterData
from wildermyth_renderer import FilterParams
from wildermyth_renderer import GraphRenderer
from wildermyth_renderer import RelationshipChart
from wildermyth_renderer import RelationshipStatus
from wildermyth_renderer import RendererParams
from wildermyth_renderer import extract_individual_entities

if TYPE_CHECKING:
    from wildermyth_renderer import schemas

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='KaulleN\'s Wildermyth relationship chart renderer')

parser.add_argument('legacy_path', type=Path, help='Path to legacy.json or legacy.json.zip file')

parser.add_argument('-o', '--output-path', type=Path, default=Path('chart.png'),
                    help='Path to save rendered chart (.png)')
parser.add_argument('-r', '--render-dir', type=Path, default=None, help='Directory for temporary render files')
parser.add_argument('-c', '--clean-tmp-files', action='store_true',
                    help='Flag to clean temporary files after rendering')
parser.add_argument('--norender', action='store_true',
                    help='Flag to not render any images and instead create raw .gv files '
                         '(if --clean-tmp-files is specified, nothing will be left at all; '
                         'output path must still be specified in order to produce graph filenames)')

rgroup = parser.add_argument_group(title='Rendering params')
rgroup.add_argument('-R', '--prioritize-relationships', '--prioritise-relationships', action='store_true',
                    help='Flag to prioritise relationships while rendering (sometimes provides cleaner results)')
rgroup.add_argument('--hide-phantoms', action='store_true', help='Flag to hide unknown parents from chart')

rgroup.add_argument('-P', '--pack', action='store_true',
                    help='Flag to pack the chart neatly instead of spreading it horizontally')
rgroup.add_argument('--pack-by-subgraphs', action='store_true',
                    help='Flag to spread out different components when packing the chart')
rgroup.add_argument('-L', '--include-legend', action='store_true', help='Flag to include legend to the chart')

fgroup = parser.add_argument_group(title='Chart filtering params')
fgroup.add_argument('--include-relationships', nargs='+', default=None,
                    help='List of relationships to include; entry format is status[_type]')
fgroup.add_argument('--exclude-relationships', nargs='+', default=None,
                    help='List of relationships to exclude; entry format is status[_type]')

fgroup.add_argument('--include-heroes', nargs='+', default=None,
                    help='List of heroes to include; accepts either name or id')
fgroup.add_argument('--exclude-heroes', nargs='+', default=None,
                    help='List of heroes to exclude; accepts either name or id')


def load_legacy_json(legacy_path: Path) -> schemas.LegacyDict:
    if legacy_path.suffix.lower() == '.zip':
        with zipfile.ZipFile(legacy_path) as legacy_zip:
            legacy_json_filenames = [f for f in legacy_zip.namelist() if f.lower().endswith('.json')]
            if not legacy_json_filenames:
                raise FileNotFoundError('No JSON files found in provided archive')

            if 'legacy.json' in legacy_json_filenames:
                legacy_json_filename = 'legacy.json'
            else:
                log.warning('No `legacy.json` file found in provided archive, trying to render from %s instead',
                            legacy_json_filenames[0])
                legacy_json_filename = legacy_json_filenames[0]

            with legacy_zip.open(legacy_json_filename) as legacy_file:
                return json.load(legacy_file)
    elif legacy_path.suffix.lower() == '.json':
        with legacy_path.open() as legacy_file:
            return json.load(legacy_file)
    else:
        raise ValueError(f"Path to legacy file must be either .zip or .json")


def prepare_relationship_list(rel_args: Optional[Iterable[str]]) -> Optional[List[Tuple[RelationshipStatus, str]]]:
    if rel_args is None:
        return None
    res = []
    for rel_str in rel_args:
        rel_status, has_type, rel_type = rel_str.partition('_')
        if rel_status == 'legacy':
            # common mistake
            rel_status = 'locked'
        rel_status = RelationshipStatus[rel_status.upper()]
        if has_type:
            if rel_type in ('soulmate', 'soulmates'):
                # locked lovers are called soulmates in game, it may cause confusion
                rel_type = 'lover'
            elif rel_type in ('lovers', 'rivals', 'friends'):
                # in game files all the relationships are in singular form
                rel_type = rel_type[:-1]
        else:
            rel_type = '*'
        res.append((rel_status, rel_type))
    return res


def prepare_hero_list(hero_args: Optional[Iterable[str]], chart: RelationshipChart) -> Optional[List[str]]:
    if hero_args is None:
        return None
    res = []
    label_lookup = chart.make_label_lookup()
    short_id_lookup = chart.make_short_id_lookup()
    for hero_str in hero_args:
        if hero_str in chart.nodes:
            res.append(hero_str)
        elif hero_str in short_id_lookup:
            res.append(short_id_lookup[hero_str].id)
        elif hero_str in label_lookup:
            res.extend([n.id for n in label_lookup[hero_str]])
        else:
            raise ValueError(f"Hero identifier {hero_str} not found")
    return res


def main(args_dict: Dict[str, Any]) -> None:
    log.info('Starting program')

    legacy_data = load_legacy_json(args_dict['legacy_path'])
    individual_entities = extract_individual_entities(legacy_data)
    characters = [CharacterData.from_entity_dicts(*entity) for entity in individual_entities]
    chart = RelationshipChart.from_character_data(characters)

    filter_params = FilterParams(
        include_relationships=prepare_relationship_list(args_dict['include_relationships']),
        exclude_relationships=prepare_relationship_list(args_dict['exclude_relationships']),

        include_heroes=prepare_hero_list(args_dict['include_heroes'], chart),
        exclude_heroes=prepare_hero_list(args_dict['exclude_heroes'], chart),
    )
    chart.apply_filter_params(filter_params, inplace=True)
    chart.clean_relationships(inplace=True)

    renderer_params = RendererParams(
        output_path=args_dict['output_path'].absolute(),
        norender=args_dict['norender'],
        render_dir=args_dict['render_dir'].absolute() if args_dict['render_dir'] is not None else None,
        clean_tmp_files=args_dict['clean_tmp_files'],
        include_legend=args_dict['include_legend'],
        prioritize_relationships=args_dict['prioritize_relationships'],
        hide_phantoms=args_dict['hide_phantoms'],
        pack_graph=args_dict['pack'],
        pack_by_subgraphs=args_dict['pack_by_subgraphs'],
    )
    renderer = GraphRenderer(renderer_params, chart)
    renderer.render()
    log.info('Successfully rendered the chart at %s', renderer_params.output_path)


if __name__ == '__main__':
    args = parser.parse_args()
    main(vars(args))
