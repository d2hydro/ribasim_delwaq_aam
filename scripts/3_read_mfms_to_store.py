# %%
import imod
import pandas as pd
from zarr.storage import LocalStore

from ribasim_tools import settings

# TODO (for LHM):
# - qrunm3 toevoegen door qrun te vermenigvuldingen met cellsize
# - psswm3 toevoegen door pssw te vermenigvuldigen met cellsize
# - metaswap resultaten (automatisch) fillen op de juiste tijdstap
# - dxy automatisch bepalen op basis van modflow-rooster
# - distance automatisch bepalen op basis van modflow-rooster (t.b.v. flexibele toepassing)
# - zarr store met compressie (wel alle budgets!) zoals besproken met @visr

# INPUT
time_slice = slice(pd.Timestamp("2013-01-01"), pd.Timestamp("2022-12-31"))  # time slice
river_systems = range(2, 7)  # river systems to read (and expected in input!)
drainage_systems = range(1, 4)  # drainage systems to read (and expected in input!)
qrun = "qrunm3"
pssw = "psswm3"

modflow_budgets_path = (
    settings.source_data_dir / "GRAM3_2" / "100" / "GRAM32_BASIS1_TA-PRJ" / "RESULTS" / "BASIS1_TA-PRJ"
)
metaswap_budgets_path = modflow_budgets_path / "MSWAPINPUT"

zarr_storage_out = settings.processed_data_dir / "modflow_metaswap_budgets.zarr"


# PROCESSING
print(f"reading MODFLOW budgets from: {modflow_budgets_path}")
print("reading riv-budgets for sys1")
ar = (
    imod.idf.open(modflow_budgets_path / "bdgriv/bdgriv_sys1_*_l*.IDF")
    .sum(dim="layer")
    .drop_vars(["dy", "dx"])
    .sel(time=time_slice)
)
ar.name = "bdgriv_sys1"
ds = ar.to_dataset()

for isys in river_systems:
    print(f"reading riv-budgets for sys{isys}")
    try:
        ds[f"bdgriv_sys{isys}"] = (
            imod.idf.open(modflow_budgets_path / f"bdgriv/bdgriv_sys{isys}_*_l*.IDF")
            .sum(dim="layer")
            .drop_vars(["dy", "dx"])
            .sel(time=time_slice)
        )
    except FileNotFoundError:
        print("No budget-files for this system, please check and change `river_systems` variable")

for isys in drainage_systems:
    print(f"reading drn-budgets for sys {isys}")
    try:
        ds[f"bdgdrn_sys{isys}"] = (
            imod.idf.open(modflow_budgets_path / f"bdgdrn/bdgdrn_sys{isys}_*_l*.IDF")
            .sum(dim="layer")
            .drop_vars(["dy", "dx"])
            .sel(time=time_slice)
        )
    except FileNotFoundError:
        print("No budget-files for this system, please check and change `drainage_systems` variable")

print(f"reading MetaSWAP budgets from: {metaswap_budgets_path}")
bdgsw = imod.idf.open(metaswap_budgets_path / rf"bdg{pssw}/bdg{pssw}_*_l*.IDF").sum(dim="layer").drop_vars(["dy", "dx"])
bdgqr = imod.idf.open(metaswap_budgets_path / rf"bdg{qrun}/bdg{qrun}_*_l*.IDF").sum(dim="layer").drop_vars(["dy", "dx"])
ds[f"bdg{pssw}"] = bdgsw.resample(time="1D").bfill().sel(time=time_slice)
ds[f"bdg{pssw}"] = bdgqr.resample(time="1D").bfill().sel(time=time_slice)
