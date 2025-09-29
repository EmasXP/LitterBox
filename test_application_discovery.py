import os, tempfile, textwrap, sys

# Add src directory to import path
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(CURRENT_DIR, 'src')
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.application_manager import ApplicationManager

ODT_MIME = 'application/vnd.oasis.opendocument.text'

# Minimal fake desktop file templates
ONLYOFFICE_DESKTOP = textwrap.dedent('''
[Desktop Entry]
Name=ONLYOFFICE Writer
Exec=onlyoffice %f
Icon=onlyoffice
Type=Application
MimeType=application/vnd.oasis.opendocument.text;application/x-extension-odt;application/vnd.openxmlformats-officedocument.wordprocessingml.document;
Categories=Office;WordProcessor;
''')

CALLIGRA_DESKTOP = textwrap.dedent('''
[Desktop Entry]
Name=Calligra Words
Exec=calligrasheets %f
Icon=calligra-words
Type=Application
MimeType=application/vnd.oasis.opendocument.text;application/x-extension-odt;
Categories=Office;WordProcessor;
''')

BASIC_TEXT_EDITOR = textwrap.dedent('''
[Desktop Entry]
Name=PlainTxt
Exec=plaintxt %f
Type=Application
MimeType=text/plain;
Categories=Utility;TextEditor;
''')

def test_ranked_applications_include_office_odt():
    with tempfile.TemporaryDirectory() as tmp:
        # Create fake desktop entries
        for fname, content in [
            ('onlyoffice.desktop', ONLYOFFICE_DESKTOP),
            ('calligra.desktop', CALLIGRA_DESKTOP),
            ('plain.desktop', BASIC_TEXT_EDITOR)
        ]:
            with open(os.path.join(tmp, fname), 'w', encoding='utf-8') as f:
                f.write(content)
        # Create fake file path
        fake_file = os.path.join(tmp, 'doc.odt')
        with open(fake_file, 'wb') as f:
            f.write(b'PK\x03\x04 odt like header')
        # Provide a simple mime override by naming .odt; stub get_mime_type will still compute
        mgr = ApplicationManager(extra_desktop_dirs=[tmp])
        ranked = mgr.get_ranked_applications_for_file(fake_file)
        names = [a.name for a in ranked]
    assert 'ONLYOFFICE Writer' in names, names
    assert 'Calligra Words' in names, names
