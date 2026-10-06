"""The visual redesign keeps the 4a9be3a data/ROS/demo sources byte-equivalent.

Normalize checkout line endings so the same contract holds on Windows and Linux.
Intentional future behavior changes must explicitly revisit this regression gate.
"""
import hashlib
from pathlib import Path
import pytest

BASELINE = {
    'models.py': '508bb820cbf2e6a3efa7965540f86c1385f5bd4c969328a1a36a2614238a4d72',
    'ros_monitor.py': '149dee314f2d321a7c59ddd914b0fb26efa9529d487a62fa64e512c360130322',
    'demo_data.py': 'f1d43debd7f5c773cb1d8150242aeca27ccf620d2930e51835fb093c7554a57c',
    # V4 freezes all V3 runtime behavior as well as the original data layer.
    'app.py': 'e2844026023676aadd653caf5bc81f6c69bb8f235d09cab59968d342e636e559',
    'process_manager.py': '0ced19f4b0e8d94225c2359695e97439b21c32fbd8380dd316bc80a594ad8822',
    'preflight.py': '3a699c004589a4b4e31152ba7fb7672ba6848b211682a96ffcb84cd67c6b9f66',
    'runtime_service.py': '126a2fafe0877f3c026f75d8768c194689657d3f66e1ae4030ecb9580799e79f',
    'runtime_observer.py': 'b4e4a373c94c4e5828f1f9ebfadfb7b1773128413ba49773b431d17e8faf1844',
    'process_environment.py': 'e963ee5dc5c56e95f3ff1972f9442b34147cf4bf3e52f9afc18f6c4f70799bdc',
    'runtime_dialogs.py': '8201e17b228f9a3a192e3c5db6da06964c69350298cfb9ee455710c5f2100597',
}


@pytest.mark.parametrize('name', BASELINE)
def test_data_and_ros_sources_unchanged(name):
    source = Path(__file__).parents[1] / 'rm65_teleop_dashboard' / name
    digest = hashlib.sha256(source.read_text(encoding='utf-8').encode()).hexdigest()
    assert digest == BASELINE[name]
