from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

INPUT_PATH = Path(r"d:\projecten\D2513.Tauw.Ribasim-Delwaq\03.artikel_stromingen\age_outlet_v3_stromingen.xlsx")
OUTPUT_PATH = Path(__file__).with_name("leeftijd_2023_2025.png")
STARTTIME = "2023-01-01"
ENDTIME = "2025-01-01"
EXCEL_NAMESPACE = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
PLOT_COLUMNS = ["A", "B", "C", "D"]
COLOR_SEQUENCE = ["#1f77b4", "#d62728", "#2ca02c"]
AXIS_LABEL_SIZE = 16
TICK_LABEL_SIZE = 13
LEGEND_SIZE = 14


def _load_shared_strings(zip_file: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zip_file.namelist():
        return []

    root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    shared_strings: list[str] = []
    for item in root.findall("a:si", EXCEL_NAMESPACE):
        text = "".join(node.text or "" for node in item.findall(".//a:t", EXCEL_NAMESPACE))
        shared_strings.append(text)
    return shared_strings


def _read_sheet_rows(zip_file: ZipFile, shared_strings: list[str]) -> list[dict[str, str | None]]:
    sheet = ET.fromstring(zip_file.read("xl/worksheets/sheet1.xml"))
    rows: list[dict[str, str | None]] = []

    for row in sheet.findall(".//a:sheetData/a:row", EXCEL_NAMESPACE):
        values: dict[str, str | None] = {}
        for cell in row.findall("a:c", EXCEL_NAMESPACE):
            reference = cell.attrib.get("r", "")
            column = "".join(character for character in reference if character.isalpha())
            value_node = cell.find("a:v", EXCEL_NAMESPACE)
            value = value_node.text if value_node is not None else None
            if cell.attrib.get("t") == "s" and value is not None:
                value = shared_strings[int(value)]
            values[column] = value
        rows.append(values)

    return rows


def read_age_data(path: Path) -> pd.DataFrame:
    with ZipFile(path) as zip_file:
        shared_strings = _load_shared_strings(zip_file)
        rows = _read_sheet_rows(zip_file, shared_strings)

    if not rows:
        raise ValueError(f"Geen rijen gevonden in {path}.")

    header = rows[0]
    column_names = [header.get(column) for column in PLOT_COLUMNS]
    if any(name is None for name in column_names):
        raise ValueError(f"Niet alle kolommen {PLOT_COLUMNS} zijn gevonden in {path}.")

    records: list[list[float]] = []
    for row in rows[1:]:
        if row.get("A") is None:
            continue
        records.append(
            [
                float(row["A"]),
                float(row["B"]) if row.get("B") is not None else float("nan"),
                float(row["C"]) if row.get("C") is not None else float("nan"),
                float(row["D"]) if row.get("D") is not None else float("nan"),
            ]
        )

    df = pd.DataFrame(records, columns=column_names)
    df[column_names[0]] = pd.to_datetime(df[column_names[0]], unit="D", origin="1899-12-30")
    return df


def main() -> None:
    df = read_age_data(INPUT_PATH)
    date_column = df.columns[0]
    value_columns = list(df.columns[1:4])
    age_tr1, age_tr2, age_tr3 = value_columns

    selection = df.loc[(df[date_column] >= pd.Timestamp(STARTTIME)) & (df[date_column] <= pd.Timestamp(ENDTIME))].copy()
    if selection.empty:
        raise ValueError(f"Geen data gevonden tussen {STARTTIME} en {ENDTIME} in {INPUT_PATH}.")

    fig, (ax_top, ax_bottom) = plt.subplots(figsize=(11, 7), nrows=2, sharex=True)

    ax_top.plot(selection[date_column], selection[age_tr2], label=age_tr2, color=COLOR_SEQUENCE[1], linewidth=2)
    ax_top.plot(selection[date_column], selection[age_tr3], label=age_tr3, color=COLOR_SEQUENCE[2], linewidth=2)

    ax_bottom.plot(
        selection[date_column],
        selection[age_tr1],
        label=age_tr1,
        color=COLOR_SEQUENCE[0],
        linewidth=2,
    )

    for ax in (ax_top, ax_bottom):
        ax.set_ylabel("Leeftijd (dagen)", fontsize=AXIS_LABEL_SIZE)
        ax.grid(True, color="grey", linewidth=1, alpha=1)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xlim(pd.Timestamp(STARTTIME), pd.Timestamp(ENDTIME))
        ax.margins(x=0)
        ax.tick_params(axis="y", labelsize=TICK_LABEL_SIZE)

    ax_top.set_ylim(0, 130)
    ax_bottom.set_ylim(0, 10)
    ax_top.legend(frameon=False, loc="upper right", fontsize=LEGEND_SIZE)
    ax_bottom.legend(frameon=False, loc="upper right", fontsize=LEGEND_SIZE)
    ax_top.tick_params(axis="x", labelbottom=False)
    ax_bottom.set_xlabel("Time", fontsize=AXIS_LABEL_SIZE)

    locator = mdates.MonthLocator(interval=2)
    formatter = mdates.ConciseDateFormatter(locator)
    ax_bottom.xaxis.set_major_locator(locator)
    ax_bottom.xaxis.set_major_formatter(formatter)
    ax_bottom.tick_params(axis="x", labelsize=TICK_LABEL_SIZE)

    fig.tight_layout()
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
