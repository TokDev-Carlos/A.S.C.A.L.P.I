# CJL Patch Promotion — Same ZIP SHA-256

O Patch Format 7 é relativo à raiz selecionada. Nenhum caminho absoluto de `C:\CJL` ou `C:\.Dev CJL` é permitido nas operações do patch. A branch não integra o payload; logo o mesmo ZIP é válido para DEV e MAIN quando ambas estão na mesma baseline. MAIN exige recibo de aprovação gerado após validação da DEV e vinculado ao SHA-256 integral do ZIP.
