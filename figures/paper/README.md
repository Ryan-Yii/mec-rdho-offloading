# Paper Figure Sources

Figure 1 is maintained as one editable source and two exports:

- `fig1_system_architecture.svg`: editable source and text authority;
- `fig1_system_architecture.png`: exact raster inserted into Word;
- `fig1_system_architecture.pdf`: vector submission export.

Regenerate the exports from the repository root without running experiments:

```bash
mkdir -p work/fig1-export
soffice --headless --convert-to png --outdir work/fig1-export figures/paper/fig1_system_architecture.svg
soffice --headless --convert-to pdf --outdir work/fig1-export figures/paper/fig1_system_architecture.svg
cp work/fig1-export/fig1_system_architecture.png figures/paper/
cp work/fig1-export/fig1_system_architecture.pdf figures/paper/
```

The manuscript generator reads the PNG directly, and the verifier compares its
SHA-256 with `word/media/image2.png`. Figure 1 belongs in Section 3.1 after the
opening architecture paragraph and before the task tuple. Its caption is:

`Fig. 1. Three-tier cloud-edge-device architecture with legal execution-node choices and shared physical CPU-capacity pools.`

The `v2/` subdirectory contains the remaining experiment-derived manuscript
figures. Those files are generated from the existing V2 CSV artifacts by
`experiments/generate_v2_artifacts.py`.
