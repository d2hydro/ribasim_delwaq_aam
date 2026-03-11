# %%
# original from https://github.com/Deltares/Ribasim-NL/blob/main/src/ribasim_nl/ribasim_nl/assign_offline_budgets.py
# Modified read differend IMODFLOW models
# Tested on GRAM Aa en Maas

from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import imod
import numpy as np
import pandas as pd
import shapely
import xarray as xr
from ribasim import Model

try:
    from ribasim_nl import CloudStorage
except ImportError:
    CloudStorage = None

if TYPE_CHECKING:
    from ribasim_nl import CloudStorage as _CloudStorage


def budgets_from_dir(
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
    bdgsw = imod.idf.open(metaswap_budgets_path / "bdgPssw/bdgPssw_*_l*.IDF").sum(dim="layer").drop_vars(["dy", "dx"])
    bdgqr = imod.idf.open(metaswap_budgets_path / "bdgQrun/bdgQrun_*_l*.IDF").sum(dim="layer").drop_vars(["dy", "dx"])
    ds["bdgpssw"] = bdgsw.resample(time="1D").bfill().sel(time=time_slice)
    ds["bdgqrun"] = bdgqr.resample(time="1D").bfill().sel(time=time_slice)

    return ds


class AssignOfflineBudgets:
    def __init__(
        self,
        zipped_budgets_path: Path | str | None = "Basisgegevens/LHM/4.3/results/LHM_433_budget.zip",
        modflow_budgets_path: Path | str | None = None,
        metaswap_budgets_path: Path | str | None = None,
    ):
        self.cloud: _CloudStorage | None = None
        # If you don't provide modflow_budgets_path and metaswap_budgets_path you will use LHM budgets from Ribasim-NL
        # In that case you'll need access to Deltares CloudStorage
        if (modflow_budgets_path is None) | (metaswap_budgets_path is None):
            self.cloud = CloudStorage()
            self.zipped_budgets_path = self.cloud.joinpath(zipped_budgets_path)
            self.modflow_budgets_path = None
            self.metaswap_budgets_path = None
        else:
            self.zipped_budgets_path = None
            self.modflow_budgets_path = Path(modflow_budgets_path)
            self.metaswap_budgets_path = Path(metaswap_budgets_path)

    def compute_budgets(
        self,
        model: Model | Path | str,
        basin_split: str = "area",
        basin_subtype: str = "state",
        basin_metacol: str = "meta_categorie",
        primary_budgets: list[str] = ["bdgriv_sys1", "bdgriv_sys4", "bdgriv_sys5"],
        secondary_budgets: list[str] = [
            "bdgriv_sys3",
            "bdgriv_sys6",
            "bdgdrn_sys1",
            "bdgdrn_sys2",
            "bdgdrn_sys3",
            "bdgpssw",
            "bdgqrun",
        ],
        ignore_budgets: list[str] = [],
    ) -> Model:
        """Compute budgets for Ribasim model

        MODFLOW/MetaSWAP budgets for LHM are computed in the following scheme
        RIV-package
        sys1: primary system
        sys2: secondary system
        sys3: tertiary system
        sys4: main system; layer 1
        sys5: main system; layer 2
        sys6: boil's / well's

        DRN-package
        sys1: tube drainage
        sys2: ditch dranage
        sys3: OLF

        MetaSWAP budgets
        qrun: OLF via MetaSWAP
        pssw: irrigation from surface water
        TODO: evaluate if we need to add urban runoff

        For the Ribasim schematization we distinguish:
          - Primary system for all basins
          - Secondary system in basins other than the main river system

        For drainage an infiltration input based on LHM-output budgets, we distubute the LHM-systems in the following matter:
         - Primary system   -> RIV-sys 1 + 4 + 5
         - Secondary system -> RIV-sys 2 + 3 + 6, DRN-sys 1 + 2 + 3, qrun + pssw

        Parameters
        ----------
        model : Model | Path | str
            _description_
        basin_split : str, optional
            _description_, by default "area"
        basin_subtype : str, optional
            _description_, by default "state"
        basin_metacol : str, optional
            _description_, by default "meta_categorie"
        primary_budgets : list[str], optional
            _description_, by default []
        secondary_budgets : list[str], optional
            _description_, by default []

        Returns
        -------
        Model
            Ribasim Model
        """
        # Synchronize LHM budget and model files
        print("📖 read and validate budgets")
        budgets, model = self._sync_files(model)

        # Validate budgets
        self._validate_budgets(
            budgets=budgets,
            primary_budgets=primary_budgets,
            secondary_budgets=secondary_budgets,
            ignore_budgets=ignore_budgets,
        )

        # Split into primary and secondary basin definition
        print("🪓 split basins into primary and secondary")
        primary_basin_definition, secondary_basin_definition = self.split_basin_definitions(
            model,
            basin_split=basin_split,
            basin_subtype=basin_subtype,
            basin_metacol=basin_metacol,
        )

        # create masks
        print("▦ rasterize basins to masks")
        array = budgets["bdgriv_sys1"].isel(time=0, drop=True)
        primary_basin_mask = imod.prepare.rasterize(
            primary_basin_definition, column="node_id", like=array, fill=-999, dtype=np.int32
        )
        secondary_basin_mask = imod.prepare.rasterize(
            secondary_basin_definition, column="node_id", like=array, fill=-999, dtype=np.int32
        )

        # compute budgets
        print("⚙️ compute budgets per basin")
        budgets_per_node_id = self._compute_budgets_per_node_id(
            budgets, primary_basin_mask, secondary_basin_mask, primary_budgets, secondary_budgets
        )

        # convert budgets from m3/day to m3/s
        print("🧹 misc cleaning operations")
        budgets_per_node_id /= 24 * 60 * 60

        # Align model
        budgets_per_node_id.columns += model.starttime - budgets_per_node_id.columns.min()

        # split to drainage and infiltration budgets
        # negative budgets means drainage from the groundwatermodel
        drainage_per_node_id = budgets_per_node_id[budgets_per_node_id.lt(0.0)].abs().fillna(0.0)
        infiltration_per_node_id = budgets_per_node_id[budgets_per_node_id.gt(0.0)].fillna(0.0)

        # Reindex basin.time to drainage and infiltration time series. Fill any
        # missing values (e.g. due to upsampling) by padding (forward fill).
        basin_time: list[pd.DataFrame] = []
        for _, group in model.basin.time.df.groupby("node_id"):
            group = group.sort_values("time").set_index("time")
            group = group.reindex(budgets_per_node_id.columns)
            for c in group.columns:
                if pd.api.types.is_numeric_dtype(group[c]):
                    group[c] = group[c].interpolate(method="pad")
            basin_time.append(group.reset_index(drop=False))
        basin_time_df = pd.concat(basin_time, ignore_index=True)

        # Add infiltration and drainage
        print("✅ assign to model basin time-table")
        infiltration_per_node_id = infiltration_per_node_id.unstack().to_frame("infiltration")
        drainage_per_node_id = drainage_per_node_id.unstack().to_frame("drainage")
        basin_time_df = basin_time_df.set_index(["time", "node_id"])
        basin_time_df.loc[infiltration_per_node_id.index, "infiltration"] = infiltration_per_node_id
        basin_time_df.loc[drainage_per_node_id.index, "drainage"] = drainage_per_node_id
        model.basin.time.df = basin_time_df.reset_index(drop=False)

        return model

    def _validate_budgets(
        self, budgets: xr.Dataset, primary_budgets: list[str], secondary_budgets: list[str], ignore_budgets: list[str]
    ):
        expected_budgets = set(primary_budgets + secondary_budgets)
        available_budgets = {i for i in budgets.data_vars if i not in ignore_budgets}
        if not (expected_budgets == available_budgets):
            raise ValueError(
                f"Budgets in budget-file(s) ({available_budgets}) do not match expected budgets ({expected_budgets}). Evaluate inputs!"
            )

    def _sync_files(
        self,
        model: Model | Path | str,
    ) -> tuple[xr.Dataset, Model]:
        """Synchronize files from the CloudStorage. Note, this is Ribasim-NL only and requires the ribasim-nl module

        Parameters
        ----------
        model : Model | Path | str
            Ribasim model or path

        Returns
        -------
        tuple[xr.Dataset, Model]
            Budgets and Ribasim model
        """
        # Synchronize files from cloud (LHM-case)
        filepaths = [self.zipped_budgets_path]
        if self.cloud is not None:
            if not isinstance(model, Model):
                filepaths.append(Path(model))
            self.cloud.synchronize(filepaths=filepaths)

        # Read the ribasim model if needed
        if not isinstance(model, Model):
            model = Model.read(model)

        # Open the budget-file as zarr if zip-file
        if self.zipped_budgets_path is None:
            budgets = budgets_from_dir(
                modflow_budgets_path=self.modflow_budgets_path,
                metaswap_budgets_path=self.metaswap_budgets_path,
                starttime=model.starttime,
                endtime=model.endtime,
            )
        elif self.zipped_budgets_path.is_file() & (self.zipped_budgets_path.suffix == ".zip"):
            budgets = xr.open_zarr(str(self.zipped_budgets_path))
        else:
            raise ValueError(
                f"{self.zipped_budgets_path} does not seem to be a zarr store or modflow budgets directory so can't be opened"
            )

        return budgets, model

    def _compute_budgets_per_node_id(
        self,
        budgets: xr.Dataset,
        primary_basin_mask: xr.DataArray,
        secondary_basin_mask: xr.DataArray,
        primary_budgets: list[str],
        secondary_budgets: list[str],
    ) -> pd.DataFrame:
        # sum primairy systems
        primary_summed_budgets = budgets[primary_budgets[0]]
        primary_summed_budgets = primary_summed_budgets.rename("primair")
        for budget in primary_budgets[1:]:
            primary_summed_budgets += budgets[budget]

        # sum secondary systems
        secondary_summed_budgets = budgets[secondary_budgets[0]]
        secondary_summed_budgets = secondary_summed_budgets.rename("secondair")
        for budget in secondary_budgets[1:]:
            secondary_summed_budgets += budgets[budget]

        # sum per system and node_id
        primary_budgets_per_node_id = (
            primary_summed_budgets.groupby(primary_basin_mask)
            .sum(dim="stacked_y_x")
            .to_dataframe()
            .unstack(1)
            .transpose()
        )
        primary_budgets_per_node_id.index = primary_budgets_per_node_id.index.droplevel(0)
        primary_budgets_per_node_id = primary_budgets_per_node_id.loc[
            primary_budgets_per_node_id.index != -999, :
        ]  # remove non overlapping budgets

        secundary_budgets_per_node_id = (
            secondary_summed_budgets.groupby(secondary_basin_mask)
            .sum(dim="stacked_y_x")
            .to_dataframe()
            .unstack(1)
            .transpose()
        )
        secundary_budgets_per_node_id.index = secundary_budgets_per_node_id.index.droplevel(0)
        secundary_budgets_per_node_id = secundary_budgets_per_node_id.loc[
            secundary_budgets_per_node_id.index != -999, :
        ]  # remove non overlapping budgets

        # combine dataframe's based on node_id
        budgets_per_node_id = pd.concat([primary_budgets_per_node_id, secundary_budgets_per_node_id])
        budgets_per_node_id.index.name = "node_id"

        return budgets_per_node_id

    def _transpose_basin_definition_polygons(
        self,
        basin_definition_in: gpd.GeoDataFrame,
        basin_definition_out: gpd.GeoDataFrame,
    ) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Retruns basin_difinition_out with index of basin_definition_in that intersect the basin_definition_out polygons

        Args:
            basin_definition_in (gpd.GeoDataFrame): Basin definition with (multi) polygons
            basin_definition_out (gpd.GeoDataFrame): Basin definition with (multi) polygons

        Returns
        -------
            tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: Basin definition with new index, Basin definition with
            polygons without any intersection
        """
        tree = shapely.STRtree(basin_definition_out["geometry"])
        index_in, index_out = tree.query(basin_definition_in.representative_point(), predicate="intersects")
        index_in = basin_definition_in.index[index_in]
        index_out = basin_definition_out.index[index_out]
        index_undifined = basin_definition_out.index[~np.isin(basin_definition_out.index, index_out)]
        basin_definition_undifined = basin_definition_out.loc[index_undifined]
        basin_definition_out = basin_definition_out.loc[index_out]
        return basin_definition_out.set_index([index_in]), basin_definition_undifined

    def _fill_basin_definition_from_points(
        self,
        basin_definition: gpd.GeoDataFrame,
        nodes: gpd.GeoDataFrame,
    ) -> gpd.GeoDataFrame:
        """
        Retuns basin_definition filled with index of basins within polygon definition

        Args:
            basin_definition (gpd.GeoDataFrame): Basin definition with (multi) polygons
            nodes (gpd.GeoDataFrame): Ribasim Basin nodes

        Returns
        -------
            gpd.GeoDataFrame: basin_definition with index from underlying Ribasim Basins
        """
        tree = shapely.STRtree(basin_definition["geometry"])
        (
            index_nodes,
            index_basin_definition,
        ) = tree.query(nodes["geometry"], predicate="within")  #'overlaps', 'within'
        index_basin_definition = basin_definition.index[index_basin_definition]
        index_nodes = nodes.index[index_nodes]
        basin_definition = basin_definition.loc[index_basin_definition]
        return basin_definition.set_index(index_nodes)

    def _split_basin_definition(
        self,
        basin_definition: gpd.GeoDataFrame,
        nodes: gpd.GeoDataFrame,
        metacol: str,
        basin_primary: str,
    ) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Splits basin definition based on 'meta_categorie' in Ribasim Basin nodes

        Args:
            basin_definition (gpd.GeoDataFrame): Basin definition with (multi) polygons
            nodes (gpd.GeoDataFrame): Ribasim Basin nodes

        Returns
        -------
            tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: Basin definition with (multi) polygons for primary ans secondary Basins
        """
        secondary_nodes = nodes[nodes[metacol] == basin_primary]
        primary_nodes = nodes[nodes[metacol] != basin_primary]
        basin_definition = basin_definition.set_index("node_id", drop=True)
        secondary_mask = np.isin(secondary_nodes["node_id"], basin_definition.index)
        primary_mask = np.isin(primary_nodes["node_id"], basin_definition.index)
        if not secondary_mask.all():
            popped = secondary_nodes["node_id"][~secondary_mask]
            print(f"poped following secondary nodes: {popped}")
        if not primary_mask.all():
            popped = primary_nodes["node_id"][~primary_mask]
            print(f"poped following primary nodes: {popped}")
        basin_definition_primair = basin_definition.loc[primary_nodes["node_id"][primary_mask]]
        basin_definition_secondair = basin_definition.loc[secondary_nodes["node_id"][secondary_mask]]

        return basin_definition_primair, basin_definition_secondair

    def split_basin_definitions(
        self,
        ribasim_model: Model,
        basin_split: str = "area",
        basin_subtype: str = "state",
        basin_metacol: str = "meta_categorie",
        basin_primary: str = "bergend",
    ) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Split basin areas into primary and secondary categories

        Parameters
        ----------
        ribasim_model : Model
            Ribasim Model
        basin_split : str, optional
            Table to be splitted, by default "area"
        basin_subtype : str, optional
            subtype to optionally read basin_metacol from, by default "state"
        basin_metacol : str, optional
            column with category, by default "meta_categorie"
        basin_primary : str, optional
            Not (?) primary value in metacolumn, by default "bergend"

        Returns
        -------
        tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]
            primary and secondary basins
        """
        # optionally get basin_metacol from other basin_subtype
        if "meta_categorie" in ribasim_model.basin.node.df.columns:
            nodes = ribasim_model.basin.node.df[["meta_categorie", "geometry"]].copy().reset_index(drop=False)
        else:
            nodes = ribasim_model.basin.node.df[["geometry"]].copy()

            df_cat = getattr(ribasim_model.basin, basin_subtype).df.copy()
            if "node_id" in df_cat.columns:
                df_cat = df_cat[["node_id", basin_metacol]].set_index("node_id")
            else:
                # assume node_id is already the index
                df_cat = df_cat[[basin_metacol]]

            nodes = nodes.join(df_cat, how="left").reset_index(drop=False)

        # split based on meta_label in Ribasim model definition
        basin_definition = getattr(ribasim_model.basin, basin_split).df.copy()
        basin_definition_primair, basin_definition_secondair = self._split_basin_definition(
            basin_definition, nodes, basin_metacol, basin_primary
        )

        # transpose primairy basins to secondary basin definition to get rid of the narrow polygons
        basin_definition_primair_polygon, basin_definition_undifined = self._transpose_basin_definition_polygons(
            basin_definition_primair, basin_definition_secondair
        )

        # fill empty basins based on pip for secondary nodes
        basin_definition_primair_points = self._fill_basin_definition_from_points(
            basin_definition_undifined, nodes[nodes[basin_metacol] != basin_primary]
        )
        basin_definition_primair = pd.concat([basin_definition_primair_polygon, basin_definition_primair_points])
        basin_definition_primair = basin_definition_primair.reset_index(names="node_id")
        basin_definition_secondair = basin_definition_secondair.reset_index()

        return basin_definition_primair, basin_definition_secondair
