# V-G1 — revisão independente do editor de modelos

**Alvo:** `64eeed2ed5734c626846e9cb8c76d66b318a95fc` (`claude/producao`, PR #5)  
**Data:** 10/10/2026  
**Revisor:** Codex / ChatGPT  
**Veredito:** **AJUSTES PEDIDOS**

## Verificações executadas

```text
python -m unittest discover -s tests -t . -v
Ran 97 tests in 67.012s
OK
```

A revisão também executou duas reproduções sintéticas isoladas, sem dados reais e sem alterar o código do Claude.

## Achado V-G1-01 — versão publicada pode ser apagada pela reimportação

**Severidade:** bloqueante para o aceite do G1.

### Reprodução

1. Publicar a primeira versão G1 de um modelo sem emitir O.P. com ela.
2. Publicar uma segunda versão do mesmo modelo.
3. Reimportar o livro legado da prefeitura.
4. Conferir os dois caminhos registrados em `modelo_edicoes.arquivo_publicado`.

Resultado observado:

```text
VERSOES_ANTES = [(versao_1, True), (versao_2, True)]
VERSOES_DEPOIS_REIMPORTAR = [(versao_1, False), (versao_2, True)]
```

### Causa confirmada

`legado._limpar_modelos_sem_uso()` preserva somente arquivos referenciados por `modelos.arquivo` e `ops.modelo_arquivo`. Ela ignora `modelo_edicoes.arquivo_origem` e `modelo_edicoes.arquivo_publicado`. Assim, uma versão publicada que ainda não foi usada em uma O.P. deixa de ser o modelo corrente após nova publicação e é removida na próxima reimportação.

### Comportamento exigido

Toda versão publicada pelo G1 deve permanecer imutável e recuperável, mesmo quando nenhuma O.P. ainda a utilizou. A limpeza deve considerar as referências históricas de `modelo_edicoes`.

### Teste exigido ao Claude

Adicionar teste automatizado que publique duas versões, reimporte o livro e confirme que ambos os arquivos continuam existentes e que os registros de histórico continuam válidos.

## Achado V-G1-02 — alteração externa da origem não gera conflito

**Severidade:** bloqueante para a garantia de concorrência e imutabilidade.

### Reprodução

1. Iniciar uma sessão de edição.
2. Alterar a cópia de trabalho.
3. Alterar em disco o arquivo publicado indicado por `arquivo_origem`, mantendo o mesmo caminho.
4. Validar a sessão.

Resultado observado:

```text
HASH_ORIGEM_CONFLITO=NAO_DETECTADO True
```

### Causa confirmada

`modelo_edicoes.hash_origem` é gravado ao iniciar a sessão, mas nunca é conferido. `EdicaoModelos._origem()` compara somente o caminho salvo em `modelos.arquivo`; se o conteúdo desse caminho mudar, a sessão continua sendo validada e pode ser publicada contra uma origem diferente daquela da abertura.

### Comportamento exigido

`validar` e `publicar` devem recalcular o SHA-256 do arquivo de origem e gerar conflito 409 quando ele divergir de `hash_origem`. A sessão não deve atualizar o modelo nem gerar novo arquivo publicado.

### Teste exigido ao Claude

Adicionar teste automatizado que modifique a origem no mesmo caminho após iniciar a edição e confirme conflito tanto em `validar` quanto em `publicar`, sem alteração no banco e sem arquivo órfão.

## Gate de aceite

A suíte vigente está verde, mas os dois casos acima quebram garantias centrais do G1. Portanto:

- G1 permanece **AJUSTES PEDIDOS**;
- o teste manual no Windows/Excel e a H-1 não devem servir como aceite enquanto esses bloqueantes estiverem abertos;
- após a correção, o Claude deve publicar novo SHA, executar a suíte completa e responder no quadro;
- o Codex repetirá a V-G1 no novo SHA antes do teste final no Windows.
