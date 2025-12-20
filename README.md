# Aeolus

*Download, standardise and store air quality data from UK monitoring networks.*

## Features

- Download data from multiple regulatory networks
- Standardise data format (using Pandas)
- Store data in a database (using SQLAlchemy/sqlmodel)

## Data sources

Currently, Aeolus supports downloading data from the following networks:
- AURN (DEFRA's Automatic Urban and Rural Network)
- SAQN (Scottish Air Quality Network)
- NI (Northern Ireland Air Quality Network)
- WAQN (Wales Air Quality Network)
- AQE (Air Quality England)
- Local (Local regulatory networks in England)
- Breathe London (requires API key set in environment variable BL_API_KEY)

Data from regulatory networks is sourced via the Openair project (using RData files provided by each regulatory network). My thanks to David Carslaw and all other contributors (see Carslaw & Ropkin, 2012 for further information).

Data from Breathe London is licensed under the Open Government Licence v3.0. For further information, see https://www.breathelondon.org.

Carslaw, D. C. and K. Ropkins, (2012) openair --- an R package for air quality data analysis. Environmental Modelling & Software. Volume 27-28, 52-61.

## Installation

To install Aeolus, run the following command in your terminal:

```bash
pip install aeolus-aq
```
Wheels and source distributions are available under Releases on Github.

## Requirements

- Python >= 3.11
- pandas >= 2.3.3
- rdata >= 0.11
- requests >= 2.32.5
- sqlmodel >= 0.0.27

## Licence

Aeolus is licensed under the GNU General Public License v3.0 or later. For further information, see https://www.gnu.org/licenses/gpl-3.0.en.html.

## Contact

For any questions or feedback, please contact Ruaraidh Dobson at [ruaraidh.dobson@gmail.com](mailto:ruaraidh.dobson@gmail.com).
