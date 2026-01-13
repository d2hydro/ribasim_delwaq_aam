# %%
import pandas as pd
from ribasim import Model
from ribasim_tools.case_conversions import pascal_to_snake_case

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "3_basin_area_vergroten")
src_dir_file = src_dir / "hsa.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "4_merge_basins")
dst_toml_file = dst_dir / "hsa.toml"

# =============================================================================
# Instellingen
# =============================================================================
REMOVE_NODES = [40000219, 40001316]
BASIN_NODE_IDS = [40000042, 30000029, 30000495, 20000016]
BASIN_AREA_MULTIPLICATION_FACTOR = 20
EXECUTE_MODEL = False
LINK_NODES = [(50000263, 40000042), (40000042, 90000001)]


# =============================================================================
# Helper functies
# =============================================================================
def remove_node(model, node_id: int):
    # remove node from tables
    for sub in model._nodes():
        assert sub.node.df is not None
        if node_id in sub.node.df.index:
            # Remove from node table
            sub.node.df = sub.node.df.drop(node_id)
            if sub.node.df.empty:
                sub.node.df = None

            # Remove from data tables
            for table in sub._tables():
                if table.df is not None and "node_id" in table.df.columns:
                    table.df = table.df[table.df["node_id"] != node_id]
                    if table.df.empty:
                        table.df = None

            break

    # remove node from link
    if model.link.df is not None:
        model.link.df = model.link.df.loc[
            (model.link.df["from_node_id"] != node_id) & (model.link.df["to_node_id"] != node_id)
        ]
        if model.link.df.empty:
            model.link.df = None


def link_nodes(model: Model, links: list[tuple[int, int]]):
    node_type = model.node_table().df["node_type"]
    for from_node_id, to_node_id in links:
        from_node = getattr(model, pascal_to_snake_case(node_type[from_node_id]))[from_node_id]
        to_node = getattr(model, pascal_to_snake_case(node_type[to_node_id]))[to_node_id]
        model.link.add(from_node=from_node, to_node=to_node)


def extend_all_qh_tabulated_rating_curves_static_and_time(
    model: Model,
    extra_level_margin: float,
    extra_flow_rate: float,
    plateau_delta_level: float = 0.1,
):
    """
    Breidt ALLE TabulatedRatingCurves uit:
      - tabulated_rating_curve.static
      - tabulated_rating_curve.time (per node_id + time)

    Per curve voegen we 2 punten toe:
      1) level = max_level + extra_level_margin, flow = max(existing_max_flow, extra_flow_rate)
      2) level = (bovenstaande) + plateau_delta_level, flow idem (plateau/max-capacity)

    Idempotent: verwijdert eerst bestaande rijen op exact deze nieuwe levels (per curve).
    """
    if extra_level_margin <= 0:
        raise ValueError("extra_level_margin moet > 0 zijn.")
    if plateau_delta_level <= 0:
        raise ValueError("plateau_delta_level moet > 0 zijn.")

    info = {
        "static_total": 0,
        "static_extended": 0,
        "time_total": 0,
        "time_extended": 0,
    }

    # -------------------------------------------------------------
    # STATIC
    # -------------------------------------------------------------
    df_static = getattr(model.tabulated_rating_curve, "static", None)
    df_static = None if df_static is None else df_static.df

    if df_static is not None and not df_static.empty:
        df_out = df_static.copy()
        trc_ids = sorted(df_out["node_id"].unique())
        info["static_total"] = len(trc_ids)

        for node_id in trc_ids:
            sub = df_out[df_out["node_id"] == node_id].sort_values("level")
            max_level = float(sub["level"].max())
            max_flow = float(sub["flow_rate"].max())

            target_flow = float(max(extra_flow_rate, max_flow))
            extra_level = max_level + float(extra_level_margin)
            plateau_level = extra_level + float(plateau_delta_level)

            # idempotent: verwijder eventuele bestaande rijen op precies die levels
            df_out = df_out[~((df_out["node_id"] == node_id) & (df_out["level"].isin([extra_level, plateau_level])))]

            new_rows = pd.DataFrame(
                [
                    {"node_id": node_id, "level": extra_level, "flow_rate": target_flow},
                    {"node_id": node_id, "level": plateau_level, "flow_rate": target_flow},
                ]
            )

            df_out = pd.concat([df_out, new_rows], ignore_index=True)
            info["static_extended"] += 1

        df_out = df_out.sort_values(["node_id", "level"]).reset_index(drop=True)
        model.tabulated_rating_curve.static.df = df_out
    else:
        print("Geen tabulated_rating_curve.static gevonden of tabel is leeg; static Qh niet aangepast.")

    # -------------------------------------------------------------
    # TIME
    # -------------------------------------------------------------
    df_time = getattr(model.tabulated_rating_curve, "time", None)
    df_time = None if df_time is None else df_time.df

    if df_time is not None and not df_time.empty:
        df_out = df_time.copy()

        # unique curves = unieke (node_id, time)
        pairs = df_out[["node_id", "time"]].drop_duplicates()
        info["time_total"] = len(pairs)

        for (node_id, time), sub in df_out.groupby(["node_id", "time"], sort=False):
            sub = sub.sort_values("level")
            max_level = float(sub["level"].max())
            max_flow = float(sub["flow_rate"].max())

            target_flow = float(max(extra_flow_rate, max_flow))
            extra_level = max_level + float(extra_level_margin)
            plateau_level = extra_level + float(plateau_delta_level)

            # idempotent: verwijder eventuele bestaande rijen op precies die levels, maar dan per (node_id,time)
            df_out = df_out[
                ~(
                    (df_out["node_id"] == node_id)
                    & (df_out["time"] == time)
                    & (df_out["level"].isin([extra_level, plateau_level]))
                )
            ]

            new_rows = pd.DataFrame(
                [
                    {"node_id": node_id, "time": time, "level": extra_level, "flow_rate": target_flow},
                    {"node_id": node_id, "time": time, "level": plateau_level, "flow_rate": target_flow},
                ]
            )

            df_out = pd.concat([df_out, new_rows], ignore_index=True)
            info["time_extended"] += 1

        df_out = df_out.sort_values(["node_id", "time", "level"]).reset_index(drop=True)
        model.tabulated_rating_curve.time.df = df_out
    else:
        print("Geen tabulated_rating_curve.time gevonden of tabel is leeg; time Qh niet aangepast.")

    return info


# =============================================================================
# INLEZEN MODEL EN BASINS SAMENVOEGEN
# =============================================================================
model = Model.read(src_dir_file)

# verwijderen nodes en links
for node_id in REMOVE_NODES:
    remove_node(model, node_id)

# toevoegen links
link_nodes(model=model, links=LINK_NODES)

# vergroten basin area (volume) zodat totale volume ongeveer hetzelfde blijft
model.basin.profile.df.loc[model.basin.profile.df.node_id.isin(BASIN_NODE_IDS), "area"] *= (
    BASIN_AREA_MULTIPLICATION_FACTOR
)

# =============================================================================
# Run model
# =============================================================================
if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)
