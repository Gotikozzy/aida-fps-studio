# Validação e evidências

Execute integridade e verificação do repositório, depois `python -m pytest -q`.
Testes usam fixtures FFV1 sintéticas com seed, sem redistribuir gameplay privado.
O baseline cobre fontes do aplicativo, exceto mudanças explícitas de versão/texto legal/
opção offline, e C++/headers. Protege esta release; mudanças futuras de algoritmo exigem
novo baseline revisado, sem regeneração automática para esconder diferenças.

Camadas: unidade/mídia/cadência, controladores/UI, ZIPs de atualização e limites/hash,
caminhos de instalação e exigências de avisos/fontes. Após build, rode EXE com
`--self-test <diretório-vazio>`. CPU obrigatório; GPU exige hardware compatível e registro
de driver/backend. Teste CPU hospedado não valida GPU. Confira instalação/upgrade/
desinstalação em conta de teste.

Evidências históricas 0.8.14 ficam em ../reference, com suas limitações. Não comprovam
build limpo 0.8.15, assinatura ou auditoria científica independente. Resultados locais
0.8.15: ../LOCAL_VALIDATION.md.

Benchmarks registram CPU/GPU, driver, SO, entrada, cache, repetições e variabilidade.
Separe latência do primeiro frame, miniaturas e término do índice. Compare resultados,
PTS e proveniência, além de tempo. Não publique caminhos ou capturas privados.

[Other language / Outro idioma](../en/VALIDATION.md)
