# User guide

1. Open a local capture with **New analysis**, or reopen an `.aida` project.
2. The first frame and representative thumbnails appear progressively. Wait for the
   precise index before placing measurement marks, running analysis or exporting.
3. Select intervals appropriate to the question. Record capture conditions.
4. Run the CPU or supported NVIDIA backend. Inspect evidence, confidence and warnings.
5. Save the project, preserving access to its original video. A project is not a video copy.
6. Export an evidence presentation. Check the delivery before publishing conclusions.

Prefer original captures, stable recording rates and minimal recompression. Cutscenes,
scene transitions, loading screens, overlays and capture limitations affect interpretation.
Compare capture FPS and content cadence separately. Do not turn an inconclusive interval
into a measured rendering claim. See [methodology](METHODOLOGY.md).

Use preferences for language, storage and cache management. Remove cache through the app
when possible; preserve original media and projects. An incompatible/missing GPU should
not prevent CPU use. Logs and diagnostics are local; inspect paths before sharing.
Automatic update checks can be disabled as described in [privacy](../../PRIVACY.md).

## Timeline and intervals

The Analysis workspace contains project/interval controls, a monitor, results and a
timeline. Resize panels as needed; **View → Restore panels** resets their arrangement.
Space plays/pauses, and arrow keys navigate frames. Drag the interval track to create
a selection, its handles to resize, or its body to move it. Overlaps are rejected.
With the timeline focused, **I** marks the start and **O** creates the interval at its
end. Delete removes a selection; F2 or double-click renames it. Ctrl+mouse wheel or
Zoom changes scale. Ctrl+Z and Ctrl+Shift+Z undo/redo interval changes.

**Analyze intervals** processes included selections. Changing intervals invalidates
previous analysis. Presentation changes do not change measured results. Read summaries,
capture rate, reference, coverage and warnings together. Inconclusive is not zero FPS;
a dotted/projected chart value is not a new observation.

## Projects and recovery

Ctrl+S saves; Ctrl+Shift+S saves another `.aida`. Projects store source references,
selections, settings and available reports. Original video and caches remain external;
preserve both project and video when moving or backing up work. If the source moved,
locate it when prompted. Source checks use size and modification time, not cryptographic
content authentication. Changed sources require reanalysis before reusing results.

Saving uses a temporary file followed by replacement. Recent projects and local recovery
are available from Home. Switching with unsaved changes offers save, discard or cancel.
Exporting an older result does not silently apply a new analyzer version; request another
analysis when you intend to apply updated methodology.

## Export formats

In **Export**, choose name, destination, language, encoding and content. Refresh the
preview after changing selections, reference or language. Export runs analysis first if
needed; valid results can be reused. Cancellation stops the pending operation.

| Content | Delivery |
|---|---|
| Video and LLM report | Silent 1080p H.264 MP4 and structured JSON |
| Video only | MP4 without audio |
| LLM report only | JSON; no video encoding |

The LLM report contains measurements, coverage, decisions and interpretation guidance;
it does not call an LLM. Intermediate reports/maps stay in application project storage.
Check delivered files after export. Presentation references must fit the nominal capture
rate: 59.94 supports a 60 FPS reference, for example. A reference is a display/comparison
setting, not a forced measurement. For unreadable frames, use report-only delivery or
adjust intervals to obtain a complete MP4 sequence. Read gaps split comparisons.

## Troubleshooting

| Symptom | Action |
|---|---|
| Analysis unavailable during opening | Wait for the precise index; thumbnails alone do not indicate measurement readiness. |
| Missing thumbnails | Use **View → Generate thumbnails again**. |
| Slow navigation | Use **View → Optimize preview** near the cursor, via CPU or available NVIDIA. Measurement timestamps remain those of the original. |
| Suspected stale index | Use **File → Index cache → Reindex current video**; analyze again if frame times change. |
| Cache storage pressure | Use **File → Index cache → Clear cache for all videos**. Preserve projects/originals; the open index stays in memory. |
| NVIDIA unavailable | Check hardware diagnostics in Preferences and use CPU. |
| Publisher warning | Check official origin and SHA-256; see [distribution policy](../../CODE_SIGNING.md). |

Settings, caches and rotating logs are local to the Windows profile. Uninstall preserves
projects, settings/cache and unknown files. Review diagnostic paths before sharing a
[bug report](https://github.com/Gotikozzy/aida-fps-studio/issues).

[Other language / Outro idioma](../pt-BR/USER_GUIDE.md)
