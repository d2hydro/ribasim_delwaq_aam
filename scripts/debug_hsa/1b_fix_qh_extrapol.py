# %%
import pandas as pd
from ribasim import Model
from ribasim_tools.case_conversions import pascal_to_snake_case

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "1a_sanitize_model")
src_dir_file = src_dir / "hsa.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "1b_fix_qh_extrapol")
dst_toml_file = dst_dir / "hsa.toml"

# =============================================================================
# Instellingen
# =============================================================================
EXECUTE_MODEL = False

# =============================================================================
# QH instellingen (voor ALLE tabulated rating curves: static én time)
# =============================================================================
EXTEND_ALL_QH = True
TARGET_LEVEL = 999.0  # extrapoleer lineair tot 999m
MIN_SLOPE = 0.0  # zet op None als je negatieve slopes wilt toestaan


# =============================================================================
# Helper functies
# =============================================================================
def remove_node(model, node_id: int):
    for sub in model._nodes():
        assert sub.node.df is not None
        if node_id in sub.node.df.index:
            sub.node.df = sub.node.df.drop(node_id)
            if sub.node.df.empty:
                sub.node.df = None

            for table in sub._tables():
                if table.df is not None and "node_id" in table.df.columns:
                    table.df = table.df[table.df["node_id"] != node_id]
                    if table.df.empty:
                        table.df = None
            break

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


def _extend_trc_df_linear_to_target_keep_meta(
    df: pd.DataFrame,
    target_level: float,
    is_time_table: bool,
    min_slope: float | None = 0.0,
) -> tuple[pd.DataFrame, int]:
    """
    Breid TRC df uit door Q(h) lineair te extrapoleren tot target_level.
    Kopieert template-rij (max level) zodat meta-kolommen behouden blijven.
    Werkt voor zowel static als time tabellen.

    - Idempotent: verwijdert bestaande rij op target_level binnen dezelfde curve.
    - Ondersteunt fid als index (df.index.name == 'fid') én als kolom.
    """
    if df is None or df.empty:
        return df, 0

    if "level" not in df.columns or "flow_rate" not in df.columns:
        raise ValueError("TRC tabel mist kolommen 'level' en/of 'flow_rate'.")

    df_out = df.copy()

    # curve key kolommen
    key_cols = ["node_id"]
    if is_time_table and "time" in df_out.columns:
        key_cols.append("time")
        base_key_cols = ["node_id"]
        for c in ["meta_rep_node_wl_id", "meta_rep_edge_q_id", "meta_from_agg_id", "meta_to_agg_id"]:
            if c in df.columns and c not in base_key_cols:
                base_key_cols.append(c)
        # meta_season bewust NIET in de key, anders voeg je per season dubbel toe

    key_cols = list(dict.fromkeys(key_cols))

    # ---- fid handling: kolom of index ----
    fid_is_column = "fid" in df_out.columns
    fid_is_index = df_out.index.name == "fid"

    next_fid = None
    if fid_is_column:
        fid_numeric = pd.to_numeric(df_out["fid"], errors="coerce")
        next_fid = int(fid_numeric.max()) + 1 if fid_numeric.notna().any() else 1
    elif fid_is_index:
        fid_numeric = pd.to_numeric(df_out.index.to_series(), errors="coerce")
        next_fid = int(fid_numeric.max()) + 1 if fid_numeric.notna().any() else 1

    extended = 0
    grouped = df_out.groupby(key_cols, dropna=False, sort=False)

    new_rows = []
    new_fids = []

    for keys, sub in grouped:
        sub_sorted = sub.sort_values("level")

        # Voor lineaire extrapolatie heb je minstens 2 punten nodig
        if len(sub_sorted) < 2:
            continue

        max_level = float(sub_sorted["level"].iloc[-1])

        # Niks doen als curve al tot/over target gaat
        if max_level >= float(target_level):
            continue

        h1 = float(sub_sorted["level"].iloc[-2])
        q1 = float(sub_sorted["flow_rate"].iloc[-2])
        h2 = float(sub_sorted["level"].iloc[-1])
        q2 = float(sub_sorted["flow_rate"].iloc[-1])

        dh = h2 - h1
        if dh == 0:
            continue

        slope = (q2 - q1) / dh
        if (min_slope is not None) and (slope < float(min_slope)):
            slope = float(min_slope)

        q_target = q2 + slope * (float(target_level) - h2)

        template = sub_sorted.iloc[-1].copy()

        # idempotent remove: verwijder bestaande target_level rij binnen deze curve
        mask = pd.Series(True, index=df_out.index)
        if not isinstance(keys, tuple):
            keys = (keys,)
        for col, val in zip(key_cols, keys):
            if pd.isna(val):
                mask &= df_out[col].isna()
            else:
                mask &= df_out[col] == val
        mask &= df_out["level"].astype(float) == float(target_level)
        df_out = df_out.loc[~mask].copy()

        r = template.copy()
        r["level"] = float(target_level)
        r["flow_rate"] = float(q_target)

        if "meta_MA_level" in df_out.columns:
            r["meta_MA_level"] = "Added_linear_extrapolation"

        if fid_is_column:
            r["fid"] = next_fid
            next_fid += 1
        elif fid_is_index:
            new_fids.append(next_fid)
            next_fid += 1

        new_rows.append(r)
        extended += 1

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        if fid_is_index:
            new_df.index = pd.Index(new_fids, name="fid")
            df_out = pd.concat([df_out, new_df], axis=0)
        else:
            df_out = pd.concat([df_out, new_df], ignore_index=True)

    # Sortering
    sort_cols = [c for c in key_cols if c in df_out.columns] + ["level"]
    df_out = df_out.sort_values(sort_cols)

    # reset_index alleen als fid GEEN index is
    if not fid_is_index:
        df_out = df_out.reset_index(drop=True)

    return df_out, extended


def extend_all_qh_tabulated_rating_curves_static_and_time_linear_to_target(
    model: Model,
    target_level: float,
    min_slope: float | None = 0.0,
):
    info = {"static_extended": 0, "time_extended": 0}

    # STATIC
    df_static = getattr(model.tabulated_rating_curve, "static", None)
    df_static = None if df_static is None else df_static.df
    if df_static is not None and not df_static.empty:
        df_new, n = _extend_trc_df_linear_to_target_keep_meta(
            df=df_static,
            target_level=target_level,
            is_time_table=False,
            min_slope=min_slope,
        )
        model.tabulated_rating_curve.static.df = df_new
        info["static_extended"] = n
    else:
        print("Geen tabulated_rating_curve.static gevonden of leeg; static niet aangepast.")

    # TIME
    df_time = getattr(model.tabulated_rating_curve, "time", None)
    df_time = None if df_time is None else df_time.df
    if df_time is not None and not df_time.empty:
        df_new, n = _extend_trc_df_linear_to_target_keep_meta(
            df=df_time,
            target_level=target_level,
            is_time_table=True,
            min_slope=min_slope,
        )
        model.tabulated_rating_curve.time.df = df_new
        info["time_extended"] = n
    else:
        print("Geen tabulated_rating_curve.time gevonden of leeg; time niet aangepast.")

    return info


def extend_outlet_time_season_boundaries(model: Model, years: list[int]) -> dict:
    """
    Zorgt dat Outlet/time voor elk jaar in years altijd de seizoensgrenzen bevat:
      31-03, 01-04, 30-09, 01-10

    Werkt per node_id (en per extra meta-kolommen als aanwezig).
    Idempotent: voegt alleen ontbrekende tijdstippen toe.
    Ondersteunt fid als index of als kolom.
    """
    info = {"rows_added": 0, "years": sorted(set(years))}

    outlet = getattr(model, "outlet", None)
    if outlet is None or getattr(outlet, "time", None) is None or outlet.time.df is None or outlet.time.df.empty:
        print("Geen outlet.time.df gevonden of leeg; outlet/time niet aangepast.")
        return info

    df = outlet.time.df.copy()
    if "time" not in df.columns:
        print("outlet.time.df heeft geen kolom 'time'; outlet/time niet aangepast.")
        return info

    df["time"] = pd.to_datetime(df["time"])

    fid_is_column = "fid" in df.columns
    fid_is_index = df.index.name == "fid"

    # volgende fid
    next_fid = None
    if fid_is_column:
        fid_numeric = pd.to_numeric(df["fid"], errors="coerce")
        next_fid = int(fid_numeric.max()) + 1 if fid_numeric.notna().any() else 1
    elif fid_is_index:
        fid_numeric = pd.to_numeric(df.index.to_series(), errors="coerce")
        next_fid = int(fid_numeric.max()) + 1 if fid_numeric.notna().any() else 1

    # curve key kolommen: alles behalve fid/time/geometry
    key_cols = ["node_id"]
    for c in [
        "control_state",
        "active",
        "max_downstream_level",
        "min_upstream_level",
        "meta_description",
        "meta_correction",
        "meta_rep_node_wl_id",
        "meta_rep_edge_q_id",
        "meta_from_agg_id",
        "meta_to_agg_id",
        "meta_season",
    ]:
        if c in df.columns and c not in key_cols:
            key_cols.append(c)

    # templates voor zomer en winter:
    def pick_template(sub: pd.DataFrame, target_month: int, target_day: int) -> pd.Series:
        exact = sub[(sub["time"].dt.month == target_month) & (sub["time"].dt.day == target_day)]
        if not exact.empty:
            return exact.sort_values("time").iloc[-1]
        target = pd.Timestamp(year=2004, month=target_month, day=target_day)
        tmp = sub.copy()
        tmp["_dist"] = tmp["time"].apply(
            lambda t: abs((pd.Timestamp(year=2004, month=t.month, day=t.day) - target).days)
        )
        return tmp.sort_values(["_dist", "time"]).iloc[0].drop(labels=["_dist"])

    season_dates = [(3, 31), (4, 1), (9, 30), (10, 1)]

    new_rows = []
    new_fids = []

    grouped = df.groupby(key_cols, dropna=False, sort=False)
    for keys, sub in grouped:
        sub = sub.copy()
        existing_times = set(sub["time"].tolist())

        summer_tmpl = pick_template(sub, 4, 1)
        winter_tmpl = pick_template(sub, 10, 1)

        for y in years:
            for m, d in season_dates:
                t_new = pd.Timestamp(year=int(y), month=m, day=d)
                if t_new in existing_times:
                    continue

                tmpl = summer_tmpl if (m, d) in [(4, 1), (9, 30)] else winter_tmpl

                r = tmpl.copy()
                r["time"] = t_new

                if "meta_season" in df.columns:
                    r["meta_season"] = "Summer" if (m, d) in [(4, 1), (9, 30)] else "Winter"

                if fid_is_column:
                    r["fid"] = next_fid
                    next_fid += 1
                elif fid_is_index:
                    new_fids.append(next_fid)
                    next_fid += 1

                new_rows.append(r)
                existing_times.add(t_new)

    if new_rows:
        new_df = pd.DataFrame(new_rows)

        if fid_is_index:
            new_df.index = pd.Index(new_fids, name="fid")
            df = pd.concat([df, new_df], axis=0)
        else:
            df = pd.concat([df, new_df], ignore_index=True)

        sort_cols = [c for c in key_cols if c in df.columns] + ["time"]
        df = df.sort_values(sort_cols)
        if not fid_is_index:
            df = df.reset_index(drop=True)

        info["rows_added"] = len(new_rows)

    model.outlet.time.df = df
    return info


# =============================================================================
# INLEZEN MODEL
# =============================================================================
model = Model.read(src_dir_file)

# =============================================================================
# Qh uitbreiden (ALLE TabulatedRatingCurves: static én time) - LINEAIR TOT 10m
# =============================================================================
if EXTEND_ALL_QH:
    info = extend_all_qh_tabulated_rating_curves_static_and_time_linear_to_target(
        model=model,
        target_level=TARGET_LEVEL,
        min_slope=MIN_SLOPE,
    )
    print(f"Extended static curves: {info['static_extended']} | Extended time curves: {info['time_extended']}")

model.write(dst_toml_file)
# =============================================================================
# Run model
# =============================================================================
if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)
