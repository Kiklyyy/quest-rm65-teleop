"""A quiet local event list. Filtering never alters the event model."""
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem
from ..widgets import Card, Page, SegmentControl, label


class EventsPage(Page):
    def __init__(self):
        super().__init__('事件', '本地状态变化记录')
        self.filter = SegmentControl((('All', 'All'), ('Info', 'Info'),
                                      ('Warning', 'Warnings'), ('Error', 'Errors')))
        self.header.addWidget(self.filter)
        self.filter.changed.connect(self._render)
        card = Card()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(('Time', 'Level', 'Source', 'Message'))
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(330)
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 180)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setFixedHeight(46)
        card.body.addWidget(self.table, 1)
        self.count_label = label('', 'caption')
        card.body.addWidget(self.count_label)
        self.body.addWidget(card, 1)
        self._events = ()
        self._rendered = None

    def update_snapshot(self, snapshot):
        self._events = snapshot.events[-500:]
        self._render()

    def _render(self, _choice=None):
        allowed = {'Info': 'INFO', 'Warning': 'WARN', 'Error': 'ERROR'}.get(self.filter.current)
        events = tuple(event for event in self._events if allowed is None or event.level == allowed)
        if events == self._rendered:
            return
        self._rendered = events
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(events))
        for row, event in enumerate(events):
            level = {'INFO': 'Info', 'WARN': '●  Warning', 'ERROR': '●  Error'}.get(event.level, event.level)
            values = (datetime.fromtimestamp(event.time_s).strftime('%H:%M:%S'), level, event.source, event.message)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 1:
                    item.setData(Qt.UserRole, event.level)
                    item.setForeground(QColor('#A36000' if event.level == 'WARN' else
                                              '#C12E26' if event.level == 'ERROR' else '#6E6E73'))
                self.table.setItem(row, column, item)
        self.count_label.setText(f'{len(events)} 条记录 · 最多保留 500 条')
        self.table.scrollToBottom()
        self.table.setUpdatesEnabled(True)
