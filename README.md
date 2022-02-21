# KaulleN's Wildermyth relationship chart renderer v0.0.1

Renders relationships charts for Wildermyth characters in a player's legacy.

Available as an online tool at https://wildermyth-renderer.herokuapp.com/ (there's also a couple of clarifications on various parameters and such)

## Dependencies

Requires [graphviz](https://graphviz.org/) to be installed in your system to work properly.
If it's not present you can still run this program in *norender* mode and render the charts manually afterwards 
(I used [this online editor](https://dreampuf.github.io/GraphvizOnline/) for testing purposes, it seems to work just right).

Python requirements are listed in `requirements.txt` file, all of them are available on PyPI.

## Base usage

```
run.py [-h] [-o OUTPUT_PATH] [-r RENDER_DIR] [-c] [--norender] [-R] [--hide-phantoms] [-P]
              [--pack-by-subgraphs] [-L]
              [--include-relationships REL [REL ...]]
              [--exclude-relationships REL [REL ...]]
              [--include-heroes HERO [HERO ...]]
              [--exclude-heroes HERO [HERO ...]]
              legacy_path

positional arguments:
  legacy_path           Path to legacy.json or legacy.json.zip file

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_PATH, --output-path OUTPUT_PATH
                        Path to save rendered chart (.png)
  -r RENDER_DIR, --render-dir RENDER_DIR
                        Directory for temporary render files
  -c, --clean-tmp-files
                        Flag to clean temporary files after rendering
  --norender            Flag to not render any images and instead create raw .gv files 
                        (if --clean-tmp-files is specified, nothing will be left at all; 
                        output path must still be specified in order to produce graph filenames)

Rendering params:
  --no-gender-shapes    Flag to not choose node shapes according to character gender
  --no-class-colors, --no-class-colours
                        Flag to not choose node colors according to character class
  -R, --prioritize-relationships, --prioritise-relationships
                        Flag to prioritise relationships while rendering 
                        (sometimes provides cleaner results)
  --hide-phantoms       Flag to hide unknown parents from chart
  -P, --pack            Flag to pack the chart neatly instead of spreading it horizontally
  --pack-by-subgraphs   Flag to spread out different components when packing the chart
  -L, --include-legend  Flag to include legend to the chart

Chart filtering params:
  --include-relationships REL [REL ...] 
                        List of relationships to include; 
                        entry format is status[_type]
  --exclude-relationships REL [REL ...]
                        List of relationships to exclude; 
                        entry format is status[_type]
  --include-heroes INCLUDE_HEROES [INCLUDE_HEROES ...]
                        List of heroes to include; 
                        accepts either name or id (short/long form)
  --exclude-heroes EXCLUDE_HEROES [EXCLUDE_HEROES ...]
                        List of heroes to exclude; 
                        accepts either name or id (short/long form)
```


## Example

![example image](https://github.com/KaulleN/wildermyth-renderer/blob/10e4ad9cc9823fce7491ff4034e343fc1eb76d95/example.png?raw=true)

This example was created using command `python run.py /home/<my_username>/.steam/debian-installation/steamapps/common/Wildermyth/players/<player_name>_<player_uid>/legacy.json.zip -o example.png -cPL --include-relationships locked --include-heroes "Gomez" "Lurch" --no-class-colors`


## Known issues

* Sometimes the result will have intersecting edges and weird node placement for no apparent reason; it's a caveat of creating graphs programmatically and as of now I have no idea how to solve it.
* CharacterData instances inside the code are currently kinda messy as I implemented them in the very beginning when I didn't fully realise how everything would work. I intend to rewrite them if I ever decide to develop this project further.

## Contribution

Feel free to fork this repository and do whatever you want with it, though I will definitely appreciate if you mention it in the credits.

I will appreciate any insight into possible avenues for improvement of this code, such as:

* In-depth understanding of graphviz rendering logic that could help improve algorithms present in this code
* Any knowledge whatsoever on how faces are rendered in Wildermyth that could help me add portraits to this chart
* Skills in web development (namely front-end) to make the web version more user-friendly
