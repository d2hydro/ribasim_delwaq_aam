"""Utilities to compare Ribasim basin series with iMOD/MFMS budget series."""

import pandas as pd
from ribasim import Model


def compare_series(
    model: Model,
    budgets_df: pd.DataFrame,
    model_node_id: int,
    imod_node_id: int,
    systems: list[str],
    *,
    absolute: bool = False,
    model_column: str = "drainage_infiltration",
    basin_label: str = "Basin (drainage/infiltratie)",
) -> pd.DataFrame:
    """Compare a Ribasim basin series with aggregated iMOD/MFMS budget series.

    Parameters
    ----------
    model
        Ribasim model containing basin time series.
    budgets_df
        DataFrame with MFMS or iMOD budget output. Expected columns are
        ``ZONE``, ``DATE_TIME`` and for each system both ``*_OUT`` and ``*_IN``.
    model_node_id
        Basin ``node_id`` in the Ribasim model.
    imod_node_id
        Zone identifier in the budget table to compare against.
    systems
        Budget system names without ``_IN``/``_OUT`` suffix. These are converted
        to upper case before selecting columns.
    absolute
        If ``True``, take the absolute value of the budget sum. Useful for series
        such as surface runoff that should always be positive.
    model_column
        Basin series to compare. Use ``"drainage_infiltration"`` to compare the
        net series ``drainage - infiltration`` or provide a column name from
        ``model.basin.time.df`` such as ``"surface_runoff"``.
    basin_label
        Legend label for the Ribasim series in the returned DataFrame.

    Returns
    -------
    pandas.DataFrame
        DataFrame with aligned Ribasim and budget series, indexed by time.
    """
    model_df = model.basin.time.df[model.basin.time.df.node_id == model_node_id].set_index("time")
    if model_column == "drainage_infiltration":
        model_series = model_df["drainage"] - model_df["infiltration"]
    else:
        model_series = model_df[model_column]

    mask = budgets_df["ZONE"] == imod_node_id
    imod_df = budgets_df[mask].groupby(["DATE_TIME", "ZONE"], as_index=False).sum(numeric_only=True).set_index("DATE_TIME")
    imod_series = -(
        imod_df[[f"{system.upper()}_OUT" for system in systems]].sum(axis=1)
        + imod_df[[f"{system.upper()}_IN" for system in systems]].sum(axis=1)
    ) / 86400

    if absolute:
        imod_series = imod_series.abs()

    compare_df = pd.concat([model_series, imod_series], axis=1)
    compare_df.columns = [basin_label, f"iMOD ({','.join(systems)})"]
    return compare_df
