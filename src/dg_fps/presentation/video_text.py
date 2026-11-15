"""Export text is immutable per job and independent of the live UI language."""

from __future__ import annotations

import re

TEXT = {
    "projeção visual durante medição inconclusiva.": (
        "visual projection during inconclusive measurement."
    ),
    "Últimos 6 s": "Last 6 s",
    "FPS • TRANSIÇÕES QUADRO A QUADRO": "FPS • FRAME-BY-FRAME TRANSITIONS",
    "TEMPO ENTRE QUADROS (ms)": "FRAME TIME (ms)",
    "Pontilhado:": "Dotted:",
    "referência quando a medição é inconclusiva.": (
        "reference when the measurement is inconclusive."
    ),
    "Queda:": "Drop:",
    "redução confirmada da cadência medida.": "confirmed reduction in measured cadence.",
    "Meta:": "Target:",
    "valor de referência para comparação.": "reference value for comparison.",
    "REFERÊNCIA": "REFERENCE",
    "FPS MEDIDO": "MEASURED FPS",
    "Cadência visual": "Visual cadence",
    "Apresentação por segundo": "Updated once per second",
    "CADÊNCIA VISUAL POR SEGUNDO": "VISUAL CADENCE PER SECOND",
    "MAPA DE MOVIMENTO": "MOTION MAP",
    "Movimento entre quadros": "Motion between frames",
    "CADÊNCIA NOMINAL": "NOMINAL CADENCE",
    "Medido": "Measured",
    "Indexar vídeo": "Index video",
    "Meta do conteúdo": "Content target",
    "Metas por trecho…": "Targets by segment…",
    "Metas por trecho": "Targets by segment",
    "Automático — cadência observada": "Automatic — observed cadence",
    "Personalizada": "Custom",
    "Referência de apresentação; não altera a medição.": (
        "Display reference; does not change the measurement."
    ),
    "Referências do conteúdo (apresentação):": "Content references (display):",
    "indeterminada": "undetermined",
    "manual": "manual",
    "inferida": "inferred",
    "Próximo da referência": "Near reference",
    "Abaixo da referência": "Below reference",
    "Acima da referência": "Above reference",
    "Sem referência": "No reference",
    "Captura limita a comparação": "Capture limits comparison",
    "Referência": "Reference",
    "FLUIDEZ": "VISUAL CADENCE",
    "Cadência visual da captura; não é telemetria da engine.": (
        "Visual cadence of the capture; not engine telemetry."
    ),
    "fonte decodificada": "decoded source",
    "CADÊNCIA VISUAL": "VISUAL CADENCE",
    "INCONCLUSIVO": "INCONCLUSIVE",
    "RETENÇÃO": "IMAGE HOLD",
    "Escuridão sem sinal visual suficiente": "Dark image without sufficient visual signal",
    "Sem textura suficiente para medir": "Insufficient texture to measure",
    "Cena parada, pausa ou congelamento": "Static scene, pause or freeze",
    "Retenção observada; causa indeterminada": "Observed image hold; cause undetermined",
    "Apenas movimento localizado; cena principal ambígua": (
        "Only localized motion; main scene is ambiguous"
    ),
    "Mudança sem movimento confiável": "Change without reliable motion evidence",
    "Tempos da captura inválidos": "Invalid capture timestamps",
    "Aguardando períodos completos": "Waiting for complete update periods",
    "Transição de cena; cadência inconclusiva": "Scene transition; cadence inconclusive",
    "Medindo períodos completos entre atualizações": "Measuring complete update intervals",
    "CAPTURA NOMINAL": "NOMINAL CAPTURE",
    "CADÊNCIA VISUAL NOS ÚLTIMOS QUADROS": "RECENT VISUAL CADENCE",
    "IMAGEM RETIDA": "IMAGE HELD",
    "MUDANÇA VISUAL": "VISUAL CHANGE",
    "Cadência visual da captura": "Captured visual cadence",
    "lacunas = inconclusivo": "gaps = inconclusive",
    "cobertura": "coverage",
    "tempo ambíguo": "ambiguous time",
    "MAPA DE AVANÇO DO FRAME": "FRAME ADVANCE MAP",
    "EVIDÊNCIA DE MUDANÇA VISUAL": "VISUAL CHANGE EVIDENCE",
    "CAIXAS = MOVIMENTO VALIDADO": "BOXES = VALIDATED MOTION",
}


class VideoText:
    def __init__(self, language: str = "pt") -> None:
        if language not in {"pt", "en"}:
            raise ValueError("Unsupported video language")
        self.language = language

    def __call__(self, text: str) -> str:
        return TEXT.get(text, text) if self.language == "en" else text

    def segment(self, label: str) -> str:
        # Translate generated display names, never stored or user-supplied metadata.
        match = re.fullmatch(r"Trecho (\d+)", label)
        if match and self.language == "en":
            return f"Segment {match.group(1)}"
        return "Full video" if label == "Vídeo completo" and self.language == "en" else label
