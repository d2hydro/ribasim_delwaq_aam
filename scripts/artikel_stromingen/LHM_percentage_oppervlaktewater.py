# %%
from pathlib import Path

from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
import rasterio

INPUT_BERGEND = Path(
    r"d:\projecten\D2306.LHM_RIBASIM\02.brongegevens\Basisgegevens\LHM\4.3\input\LHM_oppervlaktewater_percentage.tif"
)
INPUT_PRIMAIR = Path(
    r"d:\projecten\D2306.LHM_RIBASIM\02.brongegevens\Basisgegevens\LHM\4.3\input\LHM_oppervlaktewater_percentage_primair.tif"
)
OUTPUT_PAD = Path(
    r"d:\projecten\D2306.LHM_RIBASIM\02.brongegevens\Basisgegevens\LHM\4.3\input\LHM_oppervlaktewater_percentage_totaal.tif"
)
OUTPUT_KLEURPAD = OUTPUT_PAD.with_name(f"{OUTPUT_PAD.stem}_colormap.tif")
TRANSPARANTIE_DREMPEL = 0.01
KLEURSCHAAL_MAX = 3.0
SCHAALFACTOR = 100.0


def validate_layout(left: rasterio.DatasetReader, right: rasterio.DatasetReader) -> None:
    if left.count != 1 or right.count != 1:
        raise ValueError("Beide invoerbestanden moeten precies 1 band bevatten.")
    if left.width != right.width or left.height != right.height:
        raise ValueError(
            f"Rasterafmeting verschilt: {(left.width, left.height)} != {(right.width, right.height)}"
        )
    if left.transform != right.transform:
        raise ValueError("Rastertransform verschilt tussen de invoerbestanden.")
    if left.crs != right.crs:
        raise ValueError(f"CRS verschilt: {left.crs} != {right.crs}")


def make_rgba(data: np.ma.MaskedArray) -> np.ndarray:
    cmap = LinearSegmentedColormap.from_list("rood_blauw", ["red", "blue"])
    norm = Normalize(vmin=TRANSPARANTIE_DREMPEL, vmax=KLEURSCHAAL_MAX, clip=True)

    rgba = cmap(norm(data.filled(TRANSPARANTIE_DREMPEL)), bytes=True)
    rgba = np.moveaxis(rgba, -1, 0)

    transparant = np.ma.getmaskarray(data) | (data.filled(0.0) < TRANSPARANTIE_DREMPEL)
    rgba[3, transparant] = 0
    return rgba


def main() -> None:
    with rasterio.open(INPUT_BERGEND) as src_totaal, rasterio.open(INPUT_PRIMAIR) as src_primair:
        validate_layout(src_totaal, src_primair)

        totaal = src_totaal.read(masked=True).astype(np.float32)
        primair = src_primair.read(masked=True).astype(np.float32)

        result = (totaal + primair) * SCHAALFACTOR

        profile = src_totaal.profile.copy()
        profile.update(dtype=rasterio.float32)
        rgba_profile = src_totaal.profile.copy()
        rgba_profile.update(dtype=rasterio.uint8, count=4, nodata=None)

        if src_totaal.nodata is not None:
            result_to_write = result.filled(src_totaal.nodata)
        else:
            result_to_write = result.filled(np.nan)

        rgba_to_write = make_rgba(result[0])

    OUTPUT_PAD.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUTPUT_PAD, "w", **profile) as dst:
        dst.write(result_to_write)
    with rasterio.open(OUTPUT_KLEURPAD, "w", **rgba_profile) as dst:
        dst.write(rgba_to_write)


if __name__ == "__main__":
    main()
