from pathlib import Path
import pandas as pd
import imod
import xarray as xr

def read_budgets(
    modflow_budgets_path: Path,
    metaswap_budgets_path: Path,
    starttime: pd.Timestamp | None = None,
    endtime: pd.Timestamp | None = None,
) -> xr.Dataset:
    """Reading budgets from MODFLOW-MetaSWAP

    Parameters
    ----------
    modflow_budgets_path : Path
        Path to Modflow bdgriv and bdgdrn
    metaswap_budgets_path : Path
        Path to Metaswap bdgPssw and bdgQrun
    starttime : pd.Timestamp | None, optional
        starttime to slice data, by default None
    endtime : pd.Timestamp | None, optional
        endtime to slice data, by default None

    Returns
    -------
    xr.Dataset
        DataSet with budgets
    """
    # time_slice, None if start_time/end_time are None
    time_slice = (
        slice(None)
        if starttime is None and endtime is None
        else slice(
            pd.Timestamp(starttime) if starttime is not None else None,
            pd.Timestamp(endtime) if endtime is not None else None,
        )
    )
    print(f"reading MODFLOW budgets from: {modflow_budgets_path}")
    print("reading riv-budgets for sys 1")
    ar = (
        imod.idf.open(modflow_budgets_path / "bdgriv/bdgriv_sys1_*_l*.IDF")
        .sum(dim="layer")
        .drop_vars(["dy", "dx"])
        .sel(time=time_slice)
    )

    ar.name = "bdgriv_sys1"
    ds = ar.to_dataset()

    for isys in range(2, 7):
        print(f"reading riv-budgets for sys {isys}")
        try:
            ds[f"bdgriv_sys{isys}"] = (
                imod.idf.open(modflow_budgets_path / f"bdgriv/bdgriv_sys{isys}_*_l*.IDF")
                .sum(dim="layer")
                .drop_vars(["dy", "dx"])
                .sel(time=time_slice)
            )
        except FileNotFoundError:
            print("No budget-files for this layer")

    for isys in range(1, 4):
        print(f"reading drn-budgets for sys {isys}")
        try:
            ds[f"bdgdrn_sys{isys}"] = (
                imod.idf.open(modflow_budgets_path / f"bdgdrn/bdgdrn_sys{isys}_*_l*.IDF")
                .sum(dim="layer")
                .drop_vars(["dy", "dx"])
                .sel(time=time_slice)
            )
        except FileNotFoundError:
            print("No budget-files for this layer")

    print(f"reading MetaSWAP budgets from: {metaswap_budgets_path}")
    print("psswm3")
    bdgsw = imod.idf.open(metaswap_budgets_path / "bdgPsswm3/bdgPsswm3_*_l*.IDF").sum(dim="layer").drop_vars(["dy", "dx"])
    ds["bdgpsswm3"] = bdgsw.resample(time="1D").bfill().sel(time=time_slice)
    bdgqr = imod.idf.open(metaswap_budgets_path / "bdgQrunm3/bdgQrunm3_*_l*.IDF").sum(dim="layer").drop_vars(["dy", "dx"])
    ds["bdgqrunm3"] = bdgqr.resample(time="1D").bfill().sel(time=time_slice)

    return ds