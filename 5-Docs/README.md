# 5-Docs

Área dos documentos principais e duráveis do ASCALPI.

## Regra documental

Esta pasta não é depósito de relatórios, checkpoints ou documentos criados para cada alteração.

A documentação deve permanecer pequena, estável e sem autoridades concorrentes. O histórico de alteração de cada documento já é preservado pelo Git.

Não criar arquivos `V1`, `V2`, `R1`, `R2` ou cópias datadas apenas para versionar conteúdo informacional.

## Documentos principais atuais

### `Execution_Contract.md`

Contrato operacional e de governança do sistema. Define regras que precisam ser respeitadas por humanos, IA, scripts e ferramentas quando aplicáveis.

### `Souvenir.md`

Memória/orientação durável para reconstrução de contexto por IA e agentes. Deve conter conhecimento realmente útil e persistente, não relato de cada execução.

### `Black_Book.md`

Registro consolidado de falhas, riscos, limitações e problemas técnicos cuja recorrência ou impacto justifique memória permanente.

### `White_Book.md`

Registro consolidado de conhecimento técnico comprovado, soluções válidas e práticas reutilizáveis.

## O que não pertence aqui

- logs;
- receipts;
- checkpoints de execução;
- manifests operacionais;
- estado de branch;
- inventário físico da máquina;
- auditorias transitórias;
- arquivos gerados apenas para registrar que uma operação aconteceu.

Esses itens podem existir em áreas locais de evidência, especialmente sob `C:\.Dev CJL\Git`, sem se tornarem documentação oficial.

## Atualização

Um documento principal só deve ser alterado quando seu conteúdo permanente realmente mudou. Eventos operacionais não devem reescrever automaticamente estes documentos.
