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
}


@pytest.mark.parametrize('name', BASELINE)
def test_data_and_ros_sources_unchanged(name):
    source = Path(__file__).parents[1] / 'rm65_teleop_dashboard' / name
    digest = hashlib.sha256(source.read_text(encoding='utf-8').encode()).hexdigest()
    assert digest == BASELINE[name]
