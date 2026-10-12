# Sugar–water article: code and processed data

This repository contains the Python code and processed input data used to
produce the main and supplementary analyses for the sugar–water study. The
workflows cover bivariate water-risk maps, FABIO trade-flow diagrams, historical
blue- and green-water trends, water footprints, uncertainty analyses, and the
data preparation for the global Sankey diagram.

The scripts use repository-relative paths. Inputs are stored in the `data/`
folder located beside each script, and generated results are written to the
corresponding `outputs/` folder. Users should not need to edit computer-specific
paths.

## Repository structure

| Folder | Contents |
| --- | --- |
| `bivariate_maps/` | Global, India, Pakistan, and combined bivariate-map scripts and inputs |
| `fabio_trade_flows/` | Main-article blue- and green-water FABIO trade-flow figure, including domestic and international flows |
| `historical_water_consumption_trends/` | Main historical blue- and green-water consumption figure, 1981–2021 |
| `sankey_water_diagram/` | Python preparation of the 2021 country tables used in e!Sankey |
| `data_processing/gcwm_water_use/` | GCWM, FAOSTAT-scaling, and 2018 processing scripts |
| `supplementary_information/fabio_trade_flows_international_only/` | International-only FABIO trade-flow figure |
| `supplementary_information/country_level_water_use_trends/` | Country-level consumptive-water trends by continent |
| `supplementary_information/country_level_water_footprint_trends/` | Country-level water-footprint calculation and trends |
| `supplementary_information/uncertainty_analysis/` | Harvested-area scaling uncertainty analyses |
| `supplementary_information/subnational_gcwm/` | India and Pakistan subnational GCWM analyses |
| `data/supplementary_tables/` | Processed tables supplied with the article |

## Main figure workflows

### Bivariate maps

Run the scripts in this order from `bivariate_maps/`:

1. `bivarmap_2021_bluewater.py`
2. `india_state_bivar_map_2021.py`
3. `pakistan_district_bivar_map_2021.py`
4. `combine_bivarmap_global_india_pakistan_2021.py`

The first three scripts create the component maps. The fourth combines them
into the global–India–Pakistan figure.

### FABIO trade flows: domestic and international

Run the scripts in this order from `fabio_trade_flows/`:

1. `Chord_diagram_c015_c016_bluewater_2021_matplotlib.py`
2. `Chord_diagram_c015_c016_greenwater_2021_matplotlib.py`
3. `combine_blue_green_chord_figure_2021.py`

`chord_label_layout.py` is a required local helper. This workflow retains both
domestic and international country flows.

### Historical water-consumption trends

Run:

```bash
python "historical_water_consumption_trends/GCWM_world_continent_stacks_sugar_blue-green_1981_2021 V2.py"
```

The processed 1981–2021 GCWM/FAOSTAT workbook required by the script is
included in that folder's `data/` directory.

### Global Sankey diagram

Run:

```bash
python "sankey_water_diagram/Global sugar-water Sankey diagram-2021.py"
```

This script prepares and exports the country-level and global-total tables used
for the Sankey. The final diagram was assembled manually with the **e!Sankey**
application; there is no separate Python rendering script.

## Supplementary figure workflows

### International-only FABIO trade flows

Run the blue-water, green-water, and combine scripts in
`supplementary_information/fabio_trade_flows_international_only/`. These scripts
exclude flows where the producing and consuming countries are the same.

### Country-level consumptive-water trends

Run:

```bash
python "supplementary_information/country_level_water_use_trends/Sugar_Water_Spaghetti_ByContinent_1981_2021 - V2.py"
```

The script produces blue-water, green-water, and total consumptive-water trend
figures for countries grouped by continent.

### Country-level water-footprint trends

Run the scripts in this order:

1. `Sugar_water-footprint_1981_2021.py`
2. `Sugar_Water_Spaghetti_ByContinent_1981_2021 - water_footprint.py`

The first script calculates water footprints in cubic metres per tonne of
harvested crop. The second produces the continent-level figure panels.

## Data scope

The repository includes the processed datasets used directly by the figure
scripts. Large raw GCWM raster archives are not required to reproduce figures
from the included processed workbooks and are therefore not bundled here.

Scripts in `data_processing/gcwm_water_use/` document the upstream processing
workflow. Re-running that workflow from the original raw rasters requires the
external GCWM and FAOSTAT source data referenced by those scripts.

Additional information about the included supplementary tables is provided in
`data/DATA.md`.

## Python environment

The workflows use the following principal packages:

- `numpy`
- `pandas`
- `openpyxl`
- `xlsxwriter`
- `matplotlib`
- `Pillow`
- `geopandas`
- `shapely`
- `rasterio`
- `requests`
- `pyogrio`
- `country_converter`
- `pycountry`

Geospatial packages may require a compatible GDAL installation. The code was
organized for Python 3 and should be run from the repository root or by passing
the quoted script path as shown above.

## Notes

- Generated files are written to each workflow's `outputs/` directory.
- The original analysis scripts outside this repository were not moved or
  deleted.
- The Python Sankey workflow prepares the data; e!Sankey was used to create the
  final visual figure.
