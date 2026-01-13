# %%
import pandas as pd
from ribasim import Model

from ribasim_tools import run_ribasim, settings

# =============================================================================
# Paden
# =============================================================================
src_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "1b_fix_qh_extrapol")
src_dir_file = src_dir / "hsa.toml"
dst_dir = settings.processed_data_dir.joinpath("hsa_model", "debug", "1c_sanitize_model_fix_cyclic")
dst_toml_file = dst_dir / "hsa.toml"

# =============================================================================
# Instellingen
# =============================================================================
EXECUTE_MODEL = False

# =============================================================================
# Outlet/time uitbreiden
# =============================================================================
EXTEND_OUTLET_TIME = True
OUTLET_YEARS = [2004, 2005, 2006]

# =============================================================================
# TRC/time uitbreiden (QH in de tijd)
# =============================================================================
EXTEND_TRC_TIME = True
TRC_YEARS = [2004, 2005, 2006]


# =============================================================================
# Helper functies
# =============================================================================
def extend_outlet_time_season_boundaries(model: Model, years: list[int]) -> dict:
    """
    Zorgt dat Outlet/time voor elk jaar in years altijd de seizoensgrenzen bevat:
      31-03, 01-04, 30-09, 01-10

    Belangrijk:
    - Groepeert primair op node_id (optioneel control_state/active).
    - Kopieert waarden uit zomer- en winter-template.
    - Voegt ALTIJD ook 01-10 toe (winter start), ook als die in brondata ontbreekt.
    - Idempotent: als het tijdstip al bestaat voor die node_id, wordt niets toegevoegd.
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

    # ✅ BEPERKTE grouping key: node_id (+control_state/active als aanwezig)
    key_cols = ["node_id"]
    for c in ["control_state", "active"]:
        if c in df.columns and c not in key_cols:
            key_cols.append(c)

    season_dates = [(3, 31), (4, 1), (9, 30), (10, 1)]

    def pick_by_month_day(sub: pd.DataFrame, month: int, day: int) -> pd.Series | None:
        cand = sub[(sub["time"].dt.month == month) & (sub["time"].dt.day == day)]
        if cand.empty:
            return None
        return cand.sort_values("time").iloc[-1]

    def pick_nearest(sub: pd.DataFrame, month: int, day: int) -> pd.Series:
        target = pd.Timestamp(year=2004, month=month, day=day)
        tmp = sub.copy()
        tmp["_dist"] = tmp["time"].apply(
            lambda t: abs((pd.Timestamp(year=2004, month=t.month, day=t.day) - target).days)
        )
        return tmp.sort_values(["_dist", "time"]).iloc[0].drop(labels=["_dist"])

    def pick_summer_template(sub: pd.DataFrame) -> pd.Series:
        # voorkeur 04-01, anders nearest
        s = pick_by_month_day(sub, 4, 1)
        return s if s is not None else pick_nearest(sub, 4, 1)

    def pick_winter_template(sub: pd.DataFrame) -> pd.Series:
        # voorkeur 10-01; als die ontbreekt: 03-31; als die ontbreekt: nearest
        w = pick_by_month_day(sub, 10, 1)
        if w is not None:
            return w
        w = pick_by_month_day(sub, 3, 31)
        if w is not None:
            return w
        return pick_nearest(sub, 10, 1)

    new_rows = []
    new_fids = []

    for keys, sub in df.groupby(key_cols, dropna=False, sort=False):
        sub = sub.copy()
        existing_times = set(sub["time"].tolist())

        summer_tmpl = pick_summer_template(sub)
        winter_tmpl = pick_winter_template(sub)

        for y in years:
            for m, d in season_dates:
                t_new = pd.Timestamp(year=int(y), month=m, day=d)
                if t_new in existing_times:
                    continue

                is_summer = (m, d) in [(4, 1), (9, 30)]
                tmpl = summer_tmpl if is_summer else winter_tmpl

                r = tmpl.copy()
                r["time"] = t_new

                # meta_season netjes zetten als kolom bestaat
                if "meta_season" in df.columns:
                    r["meta_season"] = "Summer" if is_summer else "Winter"

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

        df = df.sort_values(key_cols + ["time"])
        if not fid_is_index:
            df = df.reset_index(drop=True)

        info["rows_added"] = len(new_rows)

    model.outlet.time.df = df
    return info


def extend_trc_time_season_boundaries(model: Model, years: list[int]) -> dict:
    """
    Voeg in tabulated_rating_curve.time de seizoensgrenzen toe voor elk jaar:
      31-03, 01-04, 30-09, 01-10

    Per node_id (en evt meta-sleutels): kopieer een volledig Q(h)-blok van een template-datum
    (zomer ~ 04-01, winter ~ 10-01) en zet time = nieuwe datum voor alle rijen in dat blok.

    Idempotent: als er al rijen bestaan voor node_id + (meta) + time, dan niets toevoegen.
    Ondersteunt fid als index of kolom.
    """
    info = {"blocks_added": 0, "rows_added": 0, "years": sorted(set(years))}

    trc = getattr(model, "tabulated_rating_curve", None)
    if trc is None or getattr(trc, "time", None) is None or trc.time.df is None or trc.time.df.empty:
        print("Geen tabulated_rating_curve.time.df gevonden of leeg; TRC/time niet aangepast.")
        return info

    df = trc.time.df.copy()
    if "time" not in df.columns:
        print("tabulated_rating_curve.time.df heeft geen kolom 'time'; TRC/time niet aangepast.")
        return info

    df["time"] = pd.to_datetime(df["time"])

    fid_is_column = "fid" in df.columns
    fid_is_index = df.index.name == "fid"

    next_fid = None
    if fid_is_column:
        fid_numeric = pd.to_numeric(df["fid"], errors="coerce")
        next_fid = int(fid_numeric.max()) + 1 if fid_numeric.notna().any() else 1
    elif fid_is_index:
        fid_numeric = pd.to_numeric(df.index.to_series(), errors="coerce")
        next_fid = int(fid_numeric.max()) + 1 if fid_numeric.notna().any() else 1

    # Curve-identiteit in TRC/time:
    # node_id + (eventuele meta-identifiers) + time vormt een "blok" Q(h)
    # We groeperen templates over node_id + meta's, en binnen zo'n groep kiezen we een template time-blok.
    base_key_cols = ["node_id"]
    for c in ["meta_rep_node_wl_id", "meta_rep_edge_q_id", "meta_from_agg_id", "meta_to_agg_id"]:
        if c in df.columns and c not in base_key_cols:
            base_key_cols.append(c)
    # meta_season bewust NIET, anders voeg je per season dubbel toe

    season_dates = [(3, 31), (4, 1), (9, 30), (10, 1)]

    def pick_template_time(sub: pd.DataFrame, target_month: int, target_day: int) -> pd.Timestamp:
        # voorkeur: exact month/day aanwezig
        cand = sub[(sub["time"].dt.month == target_month) & (sub["time"].dt.day == target_day)]
        if not cand.empty:
            return cand["time"].sort_values().iloc[-1]
        # anders: dichtstbijzijnde month/day
        target = pd.Timestamp(year=2004, month=target_month, day=target_day)
        tmp = sub[["time"]].drop_duplicates().copy()
        tmp["_dist"] = tmp["time"].apply(
            lambda t: abs((pd.Timestamp(year=2004, month=t.month, day=t.day) - target).days)
        )
        return tmp.sort_values(["_dist", "time"]).iloc[0]["time"]

    new_rows = []
    new_fids = []

    # Groepeer per node_id + meta's (dus over de tijd heen)
    grouped = df.groupby(base_key_cols, dropna=False, sort=False)

    for keys, sub_all_times in grouped:
        sub_all_times = sub_all_times.copy()

        # Kies template-datum voor zomer en winter
        t_summer = pick_template_time(sub_all_times, 4, 1)
        t_winter = pick_template_time(sub_all_times, 10, 1)

        # Haal de template-blokken (alle levels) op
        block_summer = sub_all_times[sub_all_times["time"] == t_summer].copy()
        block_winter = sub_all_times[sub_all_times["time"] == t_winter].copy()

        if block_summer.empty and block_winter.empty:
            continue

        existing_times = set(sub_all_times["time"].unique())

        for y in years:
            for m, d in season_dates:
                t_new = pd.Timestamp(year=int(y), month=m, day=d)
                if t_new in existing_times:
                    continue

                # welk blok kopiëren?
                is_summer = (m, d) in [(4, 1), (9, 30)]
                block = block_summer if is_summer else block_winter
                if block.empty:
                    # fallback: als één van beide templates ontbreekt, pak de andere
                    block = block_winter if is_summer else block_summer
                    if block.empty:
                        continue

                block_new = block.copy()
                block_new["time"] = t_new

                if "meta_season" in df.columns:
                    block_new["meta_season"] = "Summer" if is_summer else "Winter"

                # nieuwe fid's
                if fid_is_column:
                    block_new["fid"] = range(next_fid, next_fid + len(block_new))
                    next_fid += len(block_new)
                elif fid_is_index:
                    new_fids.extend(range(next_fid, next_fid + len(block_new)))
                    next_fid += len(block_new)

                new_rows.append(block_new)
                existing_times.add(t_new)
                info["blocks_added"] += 1
                info["rows_added"] += len(block_new)

    if new_rows:
        new_df = pd.concat(new_rows, axis=0)

        if fid_is_index:
            new_df.index = pd.Index(new_fids, name="fid")

        df = pd.concat([df, new_df], axis=0)

        sort_cols = [c for c in base_key_cols if c in df.columns] + ["time", "level"]
        df = df.sort_values(sort_cols)
        if not fid_is_index:
            df = df.reset_index(drop=True)

        model.tabulated_rating_curve.time.df = df

    return info


# =============================================================================
# INLEZEN MODEL
# =============================================================================
model = Model.read(src_dir_file)

# =============================================================================
# TRC/time uitbreiden (QH in de tijd) voor 2005 & 2006
# =============================================================================
if EXTEND_TRC_TIME:
    trc_info = extend_trc_time_season_boundaries(model=model, years=TRC_YEARS)
    print(
        f"TRC/time blocks added: {trc_info['blocks_added']} | rows added: {trc_info['rows_added']} "
        f"for years {trc_info['years']}"
    )

# =============================================================================
# Outlet/time uitbreiden
# =============================================================================
if EXTEND_OUTLET_TIME:
    out_info = extend_outlet_time_season_boundaries(model=model, years=OUTLET_YEARS)
    print(f"Outlet/time rows added: {out_info['rows_added']} for years {out_info['years']}")

# =============================================================================
# Wegschrijven
# =============================================================================
model.write(dst_toml_file)

# =============================================================================
# Run model
# =============================================================================
if EXECUTE_MODEL:
    run_ribasim(toml_path=dst_toml_file, ribasim_exe=settings.ribasim_exe)
