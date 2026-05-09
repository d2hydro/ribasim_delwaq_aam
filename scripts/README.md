# Scripts

De scripts in deze map vormen samen de workflow voor een Ribasim-Delwaq simulatie voor de Bakelse Aa.

Belangrijk:
- Draai de scripts op volgorde van nummering.
- Een later script verwacht dat de uitvoer van eerdere scripts al aanwezig is.
- Gebruik voor projectinrichting, `.env` en directorystructuur ook de root-[README.md](../README.md).

## Volgorde

1. `1_knippen_LHM_AAM.py`
   Knipt het LHM-model van Aa en Maas naar het werkgebied van de Bakelse Aa en schrijft het basismodel `LHM_BA` weg. Dit script werkt nu voor het LHM AaenMaas versie 2026.4.0. Wanneer je een nieuwe versie gebruikt is er kans dat je het knippen moet verfijnen.

2. `2_ribasim_delwaq_LHM_BA.py`
   - Verrijkt `LHM_BA` met meteorologische forcering (vliegbasis Volkel), drainage- en infiltratiebudgetten uit GRAM (Modflow-MetaSWAP). 
   - Voegt basin-(deel)fracties en fracties op level-boundaries (Peelkanalen) toe.
   - Draait Ribasim én DELWAQ
   - Voert een controle op continuiteit uit én toont het resultaat op het uitstroompunt van de Bakelse Aa

3. `3_controle_MFMS_budgetten.py`
   Vergelijkt de Ribasim-basinreeksen met MFMS/iMOD-budgetten (data-verificatie met het waterschap), zowel voor individuele basins als voor geaggregeerde systeemtotalen.

4. `3_plotten_fracties.py`
   Maakt controle- en presentatieplots van Delwaq-fracties, fractionele afvoer, metingen en leeftijden bij de gekozen uitstroomlocatie.

## Werkwijze

1. Start de repository via `open-vscode.cmd` zodat de juiste Pixi-environment actief is.
2. Controleer of de paden in `.env` goed staan.
3. Open en draai de scripts in in numerieke volgorde. De controle én de plots kunnen onafhankelijk gedraaid worden nadat script 2 heeft gedraaid.
4. Alle scripts hebbben markdown-toelichtingen in de scripts zelf voor de inhoudelijke tussenstappen.
