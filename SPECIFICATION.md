# AIDA FPS Studio — normative standalone specification / especificação normativa

Version / Versão: 0.8.15. Scope / Escopo: native Windows video cadence and FPS
studio only. No other DG Graphics Analyzer modules are included.

The application imports local video, indexes frame timestamps, previews frames,
measures observable visual cadence, preserves analysis provenance, saves .aida
projects and exports evidence. Capture rate and observable content cadence are
different quantities. Results do not establish the internal rendering rate of a
game engine without independent evidence. Preview thumbnails are navigation aids;
they must never replace the authoritative PTS index used for measurements.

Architecture: Qt Widgets UI -> asynchronous controllers/jobs -> media and analysis
modules. CPU and optional NVIDIA processing preserve their documented provenance.
GPU work is serialized. Network services are not measurement dependencies.
Project files retain source references, ROI, parameters and analyzer versions.
Performance work must preserve validated outputs and timestamp semantics.

O aplicativo importa vídeos locais, indexa timestamps, mostra prévias, mede a
cadência visual observável, preserva proveniência, salva projetos .aida e exporta
evidências. Taxa de captura e cadência de conteúdo são grandezas diferentes.
Resultados não demonstram a taxa interna de renderização sem evidência independente.
Miniaturas servem à navegação e não substituem o índice PTS autoritativo.

Arquitetura: UI Qt Widgets -> controladores/jobs assíncronos -> mídia e análise.
CPU e NVIDIA opcional mantêm proveniência; trabalho GPU é serializado. Serviços
de rede não são dependências da medição. Projetos preservam referências, ROI,
parâmetros e versões. Otimizações preservam resultados e semântica temporal.

This document scopes the standalone extraction; changes require an ADR.
Este documento delimita a extração independente; alterações exigem ADR.
