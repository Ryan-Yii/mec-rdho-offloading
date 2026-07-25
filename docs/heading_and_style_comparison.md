# Heading and Style Comparison

The final manuscript retains the supplied 0722 review document as its layout
base while replacing the abstract-control model and obsolete results.

| Area | Earlier risk | V2 treatment |
|---|---|---|
| Title | criteria-only title did not name the physical decision | provisional title names joint offloading and computing-resource allocation; left for author confirmation |
| Introduction | model details could precede the research gap | background, problem, gap, method, three contributions, organisation |
| Related Work | method and objective categories were mixed | one primary methodology axis: model-based, learning-based, metaheuristic |
| System figure | architecture could appear in the Introduction | original editable SVG/PNG appears in System Model |
| System Model | normalised control risked being presented as a physical variable | physical node and CPU variables are primary; the normalised coordinate is internal encoding only |
| Problem Formulation | multiple objectives and penalties could appear inconsistent | one P1, explicit hard constraints, soft CSR, separate search and reporting fitness |
| Algorithm section | implementation narration and many small headings | compact strategy/encoding/search presentation with equation-linked procedure |
| Evaluation | end-to-end advantage could be attributed to the fusion operator | main, equal-NFE, common-control, ablation, scalability, and sensitivity evidence are separated |
| Claims | every metric/component could be described as superior | metric leaders, NFE, insignificant ablations, and controlled disadvantages are stated directly |
| Tables | manually transcribed values risked drift | experiment tables are generated from V2 CSV summaries |
| Figures | Word-only or raster-only edits risked drift | repository PNG and SVG sources are hash-linked in the artifact manifest |
| Comments | stand-alone comments could resemble replies | original anchors remain; V2 responses use `paraIdParent` threaded relationships and remain unresolved |

Body text remains Times New Roman and equation runs use Cambria Math within the
review document's A4 layout.  Formulae occupy dedicated paragraphs, tables use
the inherited compact three-line style, citations retain bracketed numbering,
and substantive reviewed text is highlighted only in the comments-preserving
version.  Final journal-template conversion is an author-confirmation item.
