"""Pages consume immutable SystemSnapshot values; they own no ROS state."""
from .overview_page import OverviewPage
from .arms_page import ArmsPage
from .controllers_page import ControllersPage
from .safety_page import SafetyPage
from .linkerhand_page import LinkerHandPage
from .events_page import EventsPage


def create_pages():
    return dict(overview=OverviewPage(), arms=ArmsPage(), controllers=ControllersPage(),
                safety=SafetyPage(), linkerhand=LinkerHandPage(), events=EventsPage())
