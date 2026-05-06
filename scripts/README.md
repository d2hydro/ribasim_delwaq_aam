# Scripts

Laatst bijgewerkt: 06-05-2026

Met de scripts in deze map voer een een Ribasim-Delwaq simulatie uit voor de Bakelse Aa.De python-scripts zijn in volgorde opgebouwd:
1. `1_clip_LHM_AAM.py`: Het model van het volledige beheergebied van Aa en Maas (LHM AAM) wordt geclipt tot een model voor Bakelse Aa (LHM_BA)
2. `2_forcering_LHM_BA.py`: Het model voor de Bakelse Aa (LHM_BA) wordt voorzien van randvoorwaarden; uniforme neerslag/verdamping op openwater en drainage/infiltratie uit GRAM.

Dit maakt deze scripts-map structuur:
```text
scripts/
|- 1_ribasim_delwaq_basic_example.py    # Basic example workflow
|- 2_clip_HSA.py                        # Knippen HSA voor Bakelse Aa
|- 2_clip_LHM_AAM.py                    # Knippen LHM_AAM voor Bakelse Aa (-> LHM_BA) 
|- 3_rvw_LHM_BA.py                      # Aanpassen randvoorwaarden LHM_BA
|- 4_LHM_AAM_Delwaq.py                  # Toevoegen fracties en runnen Ribasim-Delwaq LHM_BA
```
