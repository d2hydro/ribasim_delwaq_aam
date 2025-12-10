# Scripts

De scripts beschrijven de werkstappen om tot een volledige Ribasim-Delwaq modelsimulatie te komen voor twee modellen:
- HSA het model gemaakt voor het Peelvenenproject
- LHM_AAM, het model gemaakt voor het Landelijk Hydrologisch Model

De python-scripts zijn in volgorde opgebouwd:
1. `1_ribasim_delwaq_basic_example.py`: Een basisvoorbeeld waarmee je de workflow kunt testen op het `basic_example` Ribasim testmodel
2. `2_clip_***.py`: Knippen van het HSA en LHM_AAM op het stroomgebied van de Bakelse Aa (BA)
3. `3_rvw_***.py`: Aanpassen van meteorologische en hydrologische randvoorwaarden (GRAM en vanuit kanalen) voor de uitgeknipte modellen uit stap `2`
4. `4_***_Delwaq.py`: Toevoegen van fracties (tracers met default concentraties) aan de modellen uit stap `3` en runnen van de Ribasim-Delwaq simulaties

Dit maakt deze scripts-map structuur:
```text
scripts/
|- 1_ribasim_delwaq_basic_example.py    # Basic example workflow
|- 2_clip_HSA.py                        # Knippen HSA voor Bakelse Aa
|- 2_clip_LHM_AAM.py                    # Knippen LHM_AAM voor Bakelse Aa (-> LHM_BA) 
|- 3_rvw_LHM_BA.py                      # Aanpassen randvoorwaarden LHM_BA
|- 4_LHM_AAM_Delwaq.py                  # Toevoegen fracties en runnen Ribasim-Delwaq LHM_BA
```
