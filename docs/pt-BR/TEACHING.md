# Guia para o curso de engenharia de software

Use tag fixa e branch separada por aluno; mantenha baseline de produção acessível.

| Tema | Exercício | Evidência exigida |
|---|---|---|
| Requisitos | Separar FPS de captura e cadência | Escopo e exemplos de aceitação |
| Arquitetura | Percorrer UI -> job -> decoder -> evidência | Diagrama e ADR |
| Testes | Fixture de timestamp limítrofe | Falha reproduzida e regressão |
| Desempenho | Comparar abertura fria/quente | Hardware, cache, repetições, saídas iguais |
| Cadeia de suprimentos | Rastrear DLL até fonte/licença | Versão, hash, aviso e fonte |
| Release | Gerar candidato de checkout limpo | Commit, logs e hashes finais |
| Segurança | Modelar comprometimento do servidor | Fronteiras de confiança e mitigação |

Alunos distinguem medido/inferido e mostram evidência visual. Não exija gameplay privado.
Fixtures em tests/conftest.py são pequenas e reproduzíveis. Testes aprovados não provam
toda conclusão sobre jogos. Revise contribuições; exercício não muda silenciosamente
limiares, licenças ou assinatura de produção. Avalie rastreabilidade e limites, além de velocidade.

[Other language / Outro idioma](../en/TEACHING.md)
