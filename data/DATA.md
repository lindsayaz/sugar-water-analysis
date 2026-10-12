# Data availability

This directory contains processed supplementary datasets distributed with the
article. Large or third-party raw datasets should not be duplicated here unless
their licenses explicitly permit redistribution. Instead, cite their official
source and persistent identifier in this document.

## Included supplementary datasets

All included files are stored in `supplementary_tables/`.

### `supplementary_bluewater_region_flows_2021.csv`

Regional producer-to-consumer blue-water flows used to report the 2021 FABIO
sugar trade-flow results. Columns are `producer_region`, `consumer_region`, and
`blue_m3`. The table was generated from `blue_fabio_water_all_2021.csv` by
`supplementary_information/data_exports/export_supplementary_tables.py`.

### `supplementary_greenwater_region_flows_2021.csv`

Regional producer-to-consumer green-water flows used to report the 2021 FABIO
sugar trade-flow results. Columns are `producer_region`, `consumer_region`, and
`green_m3`. The table was generated from `green_fabio_water_all_2021.csv` by
`supplementary_information/data_exports/export_supplementary_tables.py`.

### `bivarmap_2021_bluewater_supplementary_table.csv`

Country-level values supporting the 2021 bivariate map. It contains country and
ISO3 identifiers together with blue-water use, baseline water stress,
population, aridity, and food-insecurity values.

## GCWM datasets supplied by the coauthor

Eight processed or intermediate Excel workbooks were supplied and copied into
the figure or analysis folders that consume them. These include the S1 Sankey
input, S2 water-footprint input, aggregated GCWM historical series,
country-level ET table, country-region lookup, two cleaned FAOSTAT
intermediates, and the separate 2018 country dataset.

Still missing for a full pipeline rerun:

- Raw FAOSTAT sugarcane and sugar beet workbooks with the original `hravest`
  filenames used by the scripts.
- Raw monthly GCWM CROP12 and CROP13 rasters and an archived Natural Earth
  boundary dataset (or documented acquisition instructions and checksums).
- Four reproducible intermediates: the two crop extraction workbooks and their
  two `with_region` versions.
- Pakistan analysis-zone GeoPackage, MIRCA `AH_CROP12.ASC`, and required 2021
  GCWM rasters.
- The final standalone India analysis script and its spatial inputs.
- The Sankey-rendering code; the supplied Sankey script exports tables only.

The supplied README also notes that no provided script explicitly creates the
prepared S1, S2, country-level ET, or 2018 workbooks. Their preparation and
provenance must be documented even though the workbooks themselves are now
included.

Before publishing, add official download links, citations, licenses, and any
supplementary-data DOI assigned by the journal or repository.
