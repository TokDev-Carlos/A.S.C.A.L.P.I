# CJL System — Patch Format 6

Contrato ativo da Base 5 / Layout 5.

Identidade: BA, ES, IN, SE. Version continua ES.IN.SE. Todo patch BA/ES/IN avanca SE obrigatoriamente; SE pode avancar sozinho. IDs tecnicos usam `CJL_Bxx_Exx_Ixx_Sxxx_<timestamp>`. Patches antigos ficam no SM_Repo e nao participam do runtime.

O formato 6 exige baseline moderna, Layout 5, validacao estrita e aplicacao pelo worker externo. Artefatos de Layouts anteriores sao somente historico/migracao e nao podem ser aceitos pelo runtime corrente.
