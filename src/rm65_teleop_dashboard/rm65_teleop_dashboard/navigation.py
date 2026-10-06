"""Seven workstation destinations with original monochrome vector icons."""
from PyQt5.QtCore import Qt, QSize, QRectF, QPointF
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPainterPath
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QListWidget, QListWidgetItem, QVBoxLayout
from .view_config import PAGES
from .widgets import label


def navigation_icon(key, color='#77777E'):
    image = QPixmap(48, 48)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(2, 2)
    painter.setPen(QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    if key == 'play':
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        path = QPainterPath(QPointF(7, 4))
        path.lineTo(20, 12)
        path.lineTo(7, 20)
        path.closeSubpath()
        painter.drawPath(path)
    elif key == 'stop':
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(5, 5, 14, 14), 2, 2)
    elif key == 'check':
        painter.drawLine(QPointF(5, 12), QPointF(10, 17))
        painter.drawLine(QPointF(10, 17), QPointF(19, 7))
    elif key == 'overview':
        for x, y in ((4, 4), (14, 4), (4, 14), (14, 14)):
            painter.drawRoundedRect(QRectF(x, y, 6, 6), 1.5, 1.5)
    elif key == 'runtime-control':
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        path = QPainterPath(QPointF(10, 7))
        path.lineTo(17, 12)
        path.lineTo(10, 17)
        path.closeSubpath()
        painter.drawPath(path)
    elif key == 'arms':
        painter.drawLine(QPointF(6, 20), QPointF(18, 20))
        points = (QPointF(12, 19), QPointF(6, 13), QPointF(11, 6), QPointF(18, 9))
        for first, second in zip(points, points[1:]):
            painter.drawLine(first, second)
        painter.setBrush(QColor('#F2F2F5'))
        for point in points[:-1]:
            painter.drawEllipse(point, 2, 2)
        painter.drawLine(QPointF(18, 9), QPointF(21, 5))
    elif key == 'controllers':
        painter.drawRoundedRect(QRectF(3, 6, 18, 12), 5, 5)
        painter.drawLine(QPointF(6, 12), QPointF(10, 12))
        painter.drawLine(QPointF(8, 10), QPointF(8, 14))
        painter.drawEllipse(QPointF(16, 10.5), .7, .7)
        painter.drawEllipse(QPointF(18, 13.5), .7, .7)
    elif key == 'safety':
        path = QPainterPath(QPointF(12, 3))
        path.lineTo(20, 6)
        path.lineTo(19, 14)
        path.quadTo(17, 19, 12, 21)
        path.quadTo(7, 19, 5, 14)
        path.lineTo(4, 6)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(8, 12), QPointF(11, 15))
        painter.drawLine(QPointF(11, 15), QPointF(16, 9))
    elif key == 'linkerhand':
        path = QPainterPath(QPointF(6, 12))
        path.lineTo(6, 7)
        path.quadTo(6, 4, 8, 5)
        path.lineTo(8, 12)
        path.lineTo(9, 4)
        path.quadTo(10, 2, 11, 4)
        path.lineTo(11, 12)
        path.lineTo(13, 5)
        path.quadTo(15, 3, 15, 6)
        path.lineTo(15, 12)
        path.lineTo(17, 8)
        path.quadTo(19, 7, 19, 10)
        path.lineTo(18, 17)
        path.quadTo(16, 23, 10, 20)
        path.lineTo(4, 15)
        path.quadTo(2, 12, 4, 12)
        path.lineTo(8, 15)
        painter.drawPath(path)
    elif key == 'lock':
        painter.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
        painter.drawArc(QRectF(8, 3, 8, 13), 0, 180 * 16)
    else:
        for y in (6, 12, 18):
            painter.drawEllipse(QPointF(5, y), .6, .6)
            painter.drawLine(QPointF(10, y), QPointF(20, y))
    painter.end()
    icon = QIcon(image)
    icon.addPixmap(image, QIcon.Disabled)
    return icon


class Sidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Sidebar')
        self.setFixedWidth(224)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 24, 12, 22)
        layout.setSpacing(8)
        brand = QHBoxLayout()
        mark = label()
        mark.setPixmap(navigation_icon('arms', '#55555B').pixmap(28, 28))
        mark.setFixedWidth(28)
        brand.setSpacing(10)
        brand.addWidget(mark)
        names = QVBoxLayout()
        names.setSpacing(5)
        names.addWidget(label('双臂遥操作', 'brand'))
        names.addWidget(label('Monitoring Console', 'caption'))
        brand.addLayout(names)
        brand.addStretch()
        layout.addLayout(brand)
        layout.addSpacing(36)
        self.navigation = QListWidget()
        self.navigation.setObjectName('Navigation')
        self.navigation.setIconSize(QSize(18, 18))
        self.navigation.setSpacing(0)
        for key, title in PAGES:
            item = QListWidgetItem(navigation_icon(key), title)
            item.setData(Qt.UserRole, key)
            self.navigation.addItem(item)
        self.navigation.currentRowChanged.connect(self._selection)
        layout.addWidget(self.navigation)
        layout.addWidget(label('ROS 2 Humble', 'caption'))
        layout.addWidget(label('Dual RM65', 'caption'))

    def _selection(self, index):
        for row, (key, _) in enumerate(PAGES):
            self.navigation.item(row).setIcon(navigation_icon(
                key, '#007AFF' if row == index else '#77777E'))
