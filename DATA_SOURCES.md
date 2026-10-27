# Data sources and attribution

The MIT licence in `LICENSE` covers the code in this repository (Python, SQL, shell scripts).
It does **not** cover the third-party data. The files in `data/marts/`, `qa/` and the Tableau extracts are
aggregates derived from the public sources below and remain subject to their original terms.
Raw downloads are not included; `make all` fetches them from the publishers.

The project uses six source types, logged as 10 entries in `docs/source_log.csv`:

| Source type | Publisher | Terms |
|---|---|---|
| 1. Trip history files: Citi Bike (New York) and Divvy (Chicago) | Lyft Bikes and Scooters, LLC (operator of Citi Bike and Divvy) | Citi Bike: Data License Agreement, published on the "Data Sharing Policy" page, https://citibikenyc.com/data-sharing-policy. Divvy: Divvy Data License Agreement, https://divvybikes.com/data-license-agreement |
| 2. Citi Bike monthly operating reports | Citi Bike (Lyft), submitted to NYC DOT | Public reports; revenue is preliminary and unaudited, as the reports state |
| 3. Pricing pages (Citi Bike, Divvy; live pages, Wayback Machine snapshots and the 2026 Citi Bike price notice) | Citi Bike, Divvy; snapshots via the Internet Archive Wayback Machine | Official public price lists; the Wayback Machine is used only to read archived public pages |
| 4. Docked Bikeshare Ridership, daily (New York, Chicago and Jersey City series) | U.S. DOT Bureau of Transportation Statistics | U.S. government work, public domain (dataset metadata: "Public Domain U.S. Government") |
| 5. GHCN-Daily weather (Central Park USW00094728, Chicago O'Hare USW00094846) | NOAA National Centers for Environmental Information | U.S. government work, public domain |
| 6. Citywide Mobility Survey - Person 2024, https://data.cityofnewyork.us/d/i2im-iqtt | NYC Department of Transportation, via NYC Open Data | NYC.gov Terms of Use: https://www.nyc.gov/main/terms-of-use |

## Attribution

Attribution is given here as good practice; neither data licence agreement asks for a specific attribution line.

- Trip data: provided by Lyft Bikes and Scooters, LLC for Citi Bike (New York) and Divvy (Chicago).
- Daily ridership: U.S. Department of Transportation, Bureau of Transportation Statistics.
- Weather: NOAA National Centers for Environmental Information, GHCN-Daily (Menne et al., 2012).
- Survey: NYC Department of Transportation, Citywide Mobility Survey 2024, via NYC Open Data.

No endorsement is implied. Lyft, Citi Bike, Divvy, the cities of New York and Chicago and the federal agencies do
not endorse this project, and the analysis, figures and conclusions are my own. Citi Bike and Divvy names are used
only to describe the data source. The trip data is not redistributed as a stand-alone dataset: only aggregates are
committed.
