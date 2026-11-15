# AIDA FPS Studio — componentes de terceiros

O código próprio do AIDA 0.8.15 é disponibilizado sob Apache-2.0. As bibliotecas mantêm suas próprias
licenças. Aceitar os termos do produto não limita os direitos concedidos por elas.
Os textos completos e versões acompanham a instalação em `third_party_licenses`,
disponíveis pelo menu Ajuda > Termos e licenças.

| Componente | Licença/opção utilizada |
| --- | --- |
| Python 3.12.7 e dependências documentadas | PSF-2.0 e avisos permissivos originais |
| Qt, PySide6/Shiboken6 6.12.0 | LGPL-3.0 e avisos transitivos |
| PyAV 16.1.0 | BSD-3-Clause; nomes de importação de DLLs ajustados |
| FFmpeg 8.0.1 | LGPL-3.0-or-later, sem GPL/nonfree habilitado |
| OpenH264 2.6.0 e dav1d 1.5.1 | BSD-2-Clause |
| nv-codec-headers 12.1.14.0 | MIT |
| NumPy/OpenBLAS/LAPACK | BSD e avisos originais; GCC Runtime Exception quando aplicável |
| OpenCV | Apache-2.0 e avisos originais; plugin de vídeo FFmpeg excluído |
| platformdirs e typing_extensions | Licenças originais preservadas no inventário |
| PyInstaller | GPL com exceção de distribuição do bootloader |
| NSIS | Licença original preservada |
| OpenSSL 3, libffi e SQLite | Apache-2.0, MIT e domínio público, respectivamente |
| Microsoft VC Runtime | Microsoft Visual C++ Runtime 2015–2022 Software License Terms |

O FFmpeg foi compilado de fontes upstream não modificados, com `--disable-gpl
--disable-nonfree`. Não inclui x264/x265. A exportação CPU usa OpenH264; NVIDIA
NVENC continua opcional. O algoritmo de análise de FPS não foi alterado.

Qt é copyright da The Qt Company Ltd. e seus colaboradores. Os avisos e
atribuições upstream são preservados. A opção comercial do Qt não é utilizada.
Bibliotecas e wrappers LGPL são arquivos substituíveis, sem trava de assinatura
ou checksum que impeça sua substituição.

Fontes completos do Qt Base, Qt SVG, Qt Image Formats, PySide/Shiboken e da
composição de mídia acompanham a instalação em `third_party_licenses/sources`.
`SOURCES-AND-REPLACEMENT.txt` descreve compilação e substituição. O material de
mídia inclui fontes, argumentos de compilação e ajustes de vinculação do PyAV.
O código próprio do AIDA não é distribuído nesses arquivos.

A ponte própria `dg_nvidia_optical_flow.dll` usa os arquivos MIT do NVIDIA Optical
Flow SDK 5.0.7: NvOF.cpp, NvOF.h, NvOFCuda.cpp, NvOFCuda.h, NvOFDefines.h,
NvOFUtils.h, nvOpticalFlowCommon.h e nvOpticalFlowCuda.h. Avisos originais em
`NVIDIA-Optical-Flow-MIT.txt`. Não são distribuídos SDK completo, CUDA Toolkit ou
DLLs de driver NVIDIA. O driver é fornecido pelo usuário; CPU funciona sem NVIDIA.

Inventário, hashes, materiais de licença e fontes são verificados ao gerar o
instalador. Mudanças de binário ou componente exigem nova revisão.


## English summary

AIDA 0.8.15 application code is Apache-2.0. Third-party components retain their own
licenses; accepting installer terms does not waive their rights. Full original notices,
license texts and corresponding sources accompany public binary installations.

| Component | Selected license / distribution note |
|---|---|
| Python 3.12.7 | PSF-2.0 and original transitive notices |
| Qt, PySide6, Shiboken6 6.12.0 | LGPL-3.0 option; shared/replaceable libraries |
| PyAV 16.1.0 | BSD-3-Clause; PE import names rebound to the selected FFmpeg DLLs |
| FFmpeg 8.0.1 | LGPL-3.0-or-later; GPL/nonfree disabled |
| OpenH264 2.6.0, dav1d 1.5.1 | Original BSD notices |
| nv-codec-headers | MIT and original notices |
| NumPy, OpenBLAS, LAPACK | BSD and original notices, including applicable GCC exception |
| OpenCV | Apache-2.0 and original notices; unused FFmpeg video-I/O DLL excluded |
| NVIDIA helper/header files | MIT; not the complete proprietary SDK |
| PyInstaller | GPL with applicable exception; retain original hook notice |
| NSIS | Original compiler/runtime license |
| OpenSSL, libffi, SQLite | Apache-2.0, MIT and public-domain notices respectively |
| Microsoft VC runtime | Microsoft redistribution terms; system-library eligibility needs review |

Do not sign upstream DLLs as AIDA-owned code. Keep compatible LGPL libraries
replaceable and provide exact corresponding sources; reverse engineering for debugging
library modifications is not prohibited. User projects and videos remain user content.
The Python CycloneDX inventory in build-support covers build wheels, not every native
runtime dependency. Review the installed payload inventory for each release.
