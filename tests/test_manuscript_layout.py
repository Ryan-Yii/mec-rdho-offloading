from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from tools.revise_manuscript import set_equation


def test_set_equation_adds_center_and_right_tab_stops():
    doc = Document()
    paragraph = doc.add_paragraph('placeholder')
    math_node = OxmlElement('m:oMath')
    math_run = OxmlElement('m:r')
    math_text = OxmlElement('m:t')
    math_text.text = 'x=1'
    math_run.append(math_text)
    math_node.append(math_run)

    set_equation(paragraph, math_node, 16)

    tabs = paragraph._p.xpath('./w:pPr/w:tabs/w:tab')
    tab_values = [(tab.get(qn('w:val')), tab.get(qn('w:pos'))) for tab in tabs]
    assert tab_values == [('center', '4860'), ('right', '9720')]


def test_ablation_label_does_not_duplicate_elite_word():
    from tools.revise_manuscript import ablation_label

    assert ablation_label('RDHO-w/o elite preservation') == 'w/o elite'
