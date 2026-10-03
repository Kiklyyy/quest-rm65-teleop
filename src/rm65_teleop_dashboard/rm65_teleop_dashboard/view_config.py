"""Qt-free page registry shared by the navigation and command-line interface."""
PAGES = (('overview', '总览'), ('runtime-control', '运行控制'), ('arms', '双臂'), ('controllers', 'VR 控制器'),
         ('safety', '安全'), ('linkerhand', '灵巧手'), ('events', '事件'))
PAGE_KEYS = tuple(key for key, _ in PAGES)
