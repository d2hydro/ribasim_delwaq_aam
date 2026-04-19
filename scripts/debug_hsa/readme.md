# Scripts

Aantal scripts gegerereerd t.b.v. beknopte analyse/debugging HSA model. Deze scripts horen bij de presentatie `Beknopte analyse HSA model` welke is uitgevoerd begin 2026 (gestuurd op 12-1-2026)
Let op(!); deze scripts zijn niet meer getest-gedraaid met Ribasim 2026.1.0 (en verder):
- Deze versie was niet beschikbaar bij het uitvoeren van de analyse
- Er is geen enkele reden om aan te nemen dat de conclusies uit de analyse anders uitpakt bij gebruik van 2026.1.0 

Overzicht van de acties die worden uitgevoerd per script:
- 1a_sanitize_model.py -> Converteren Ribasim 2025.3.0 model naar 2025.6.0
- 1b_fix_qh_extrapol.py -> Extrapoleren Qh relaties om model stabieler te maken (basismodel = 1a)
- 1c_sanitize_model fix_cyclic.py -> time wordt in Qh relaties niet meer cyclic toegepast. Tijd extrapoleren zodat model rekent als in 2025.3.0 (basismodel = 1b)
- 2_stationaire_run.py -> Dynamische forcering zoals gelevert vervangen voor constant 5mm/dag (basismodel = 1c)
- 3a_basin_area_vergroten.py -> stationaire run met een aantal basins vergroot (basismodel = 2)
- 3b_basin_area_vergroten_ns.py -> niet stationaire run met met een aantal basins vergroot (basismodel = 1c)
- 4a_merge_basins.py -> stationaire run met een aantal basins samengevoegd (basismodel = 3a)
- 4b_merge_basins ns.py -> niet stationaire run met met een aantal basins samengevoegd (basismodel = 3b)
- plot_profielen.py -> aantal grafieken geplot (basismodel = 1a)