# Atualizações e hospedagem

O site permanece https://detonandogueek.com.br/aida/update.json. O atualizador monta URLs
de ZIPs versionados no domínio oficial e restringe redirecionamento à mesma origem.
Assets GitHub com redirecionamentos não substituem esse endereço diretamente.

Manifesto: `{"version":"0.8.15","sha256":"<64 caracteres hex>","size":123}`.
Use tamanho/hash reais do ZIP final. Versões têm três componentes decimais.
ZIP contém somente `AIDA-FPS-Studio-<versão>-windows-x64-setup.exe`.
O app limita tamanhos, verifica SHA-256, rejeita entradas inesperadas, solicita confirmação
e valida estrutura PE. **Não** exige Authenticode. Essa melhoria requer alteração separada,
revisão e política de rotação; não fixe eternamente certificado de curta duração.

Ordem: artefato CI sem assinatura revisado -> GitHub Release -> espelho idêntico -> manifesto.
Preserve nomes/URLs para usuários existentes. Calcule o hash do instalador final e
o hash do ZIP após empacotar esse EXE exato. SHA-256 da mesma origem não protege contra comprometimento dela.
Manifesto assinado/TUF poderá ser avaliado depois; não está implementado nesta versão.
Opção offline: ../../PRIVACY.md.

[Other language / Outro idioma](../en/UPDATES.md)
