# -*- coding: utf-8 -*-
from .vendor.Qt import QtCore, QtGui, QtWidgets
import cmath


class LineArrow(QtWidgets.QGraphicsItem):
    def __init__(self, parent, color):
        super(LineArrow, self).__init__(parent)
        self.triangle = QtGui.QPolygon()
        self.color = color

        # Pen.
        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.SolidLine)
        self.pen.setWidth(0)
        self.pen.setColor(self.color)

    @property
    def line(self):
        return self.parentItem()

    def paint(self, painter, option, widget):
        painter.setPen(self.pen)
        path = QtGui.QPainterPath()
        dx = self.line.point_b.x() - self.line.point_a.x()
        dy = self.line.point_b.y() - self.line.point_a.y()
        triangle_x = (self.line.point_a.x() + self.line.point_b.x()) / 2
        triangle_y = (self.line.point_a.y() + self.line.point_b.y()) / 2
        # パスの接線をパスの描画とは切り離して調整しないとうまいこと回転できなかった
        if dx > 0:
            ctrl1_dummy = QtCore.QPointF(self.line.point_a.x() + dx * 0.3,
                                         self.line.point_a.y() + dy * 0.1)
            ctrl2_dummy = QtCore.QPointF(self.line.point_b.x() - dx * 0.3,
                                         self.line.point_a.y() + dy * 0.9)
        else:
            ctrl1_dummy = QtCore.QPointF(self.line.point_a.x() + abs(dx * 0.7),
                                         self.line.point_a.y() + dy * 0.1)
            ctrl2_dummy = QtCore.QPointF(self.line.point_b.x() - abs(dx * 0.7),
                                         self.line.point_a.y() + dy * 0.9)

        # 三角形の中心からの先端へのベクトル
        line_vector_x = ctrl1_dummy.x() - ctrl2_dummy.x()
        line_vector_y = ctrl1_dummy.y() - ctrl2_dummy.y()
        line_vector = complex(line_vector_x, line_vector_y)
        # 単位ベクトルに変換
        _p = cmath.phase(line_vector)
        line_vector = cmath.rect(1, _p)

        #
        triangle_points = [complex(-5, 0),
                           complex(5, 7),
                           complex(5, -7),
                           complex(-5, 0)]
        triangle_points = [_p * line_vector for _p in triangle_points]
        triangle_points = [QtCore.QPoint(triangle_x + _p.real, triangle_y + _p.imag) for _p in triangle_points]
        self.triangle = QtGui.QPolygon(triangle_points)
        path.addPolygon(self.triangle)
        painter.fillPath(path, self.pen.color())
        painter.drawPath(path)

    def boundingRect(self):
        return self.triangle.boundingRect()

    def shape(self):
        path = QtGui.QPainterPath()
        path.addEllipse(self.boundingRect())
        return path


class Line(QtWidgets.QGraphicsPathItem):

    def __init__(self, point_a, point_b, color):
        from .port import Port
        self.port = Port

        super(Line, self).__init__()
        self.color = color
        self._point_a = point_a
        self._point_b = point_b
        self._source = None
        self._target = None
        self.moving = None
        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.SolidLine)
        self.pen.setWidth(1)
        self.pen.setColor(self.color)
        self.hover_port = None
        self.arrow = LineArrow(self, self.color)

        self.setZValue(-1)
        self.setBrush(QtCore.Qt.NoBrush)
        self.setPen(self.pen)
        self.setAcceptHoverEvents(True)

    def mousePressEvent(self, event):
        self.point_b = event.pos()
        self.moving = 'b'

    def _get_none_move_port(self):
        if self.source is None:
            return self.target
        return self.source

    def update_moving_point(self, pos):
        if self.source is None:
            self.point_a = pos
        else:
            self.point_b = pos

    def delete(self):
        if self.source is not None:
            self.source.disconnect(self)
        if self.target is not None:
            self.target.disconnect(self)
        self.scene().removeItem(self)

    def mouseMoveEvent(self, event):
        pos = event.scenePos().toPoint()
        self.update_moving_point(pos)
        none_move_port = self._get_none_move_port()

        # ポートのハイライト
        pos = event.scenePos().toPoint()
        item = self.scene().itemAt(pos.x(), pos.y(), QtGui.QTransform())

        if isinstance(item, self.port):
            if none_move_port.can_connection(item):
                self.hover_port = item
                self.hover_port.hoverEnterEvent(None)
        else:
            if self.hover_port is not None:
                self.hover_port.hoverLeaveEvent(None)
                self.hover_port = None

    def mouseReleaseEvent(self, event):
        pos = event.scenePos().toPoint()
        item = self.scene().itemAt(pos.x(), pos.y(), QtGui.QTransform())

        if self.moving == 'a':
            start_of_line = self.target
            end_of_line = self.source
        else:
            start_of_line = self.source
            end_of_line = self.target

        # ポート以外で離したらラインごと削除
        if not isinstance(item, self.port):
            self.delete()
            return

        if not start_of_line.can_connection(item):
            if end_of_line is None:
                # ライン新規作成時
                start_of_line.delete_old_line()
            else:
                # ライン編集時は元の位置に戻す
                pos = end_of_line.get_center()
                setattr(self, 'point_{0}'.format(self.moving), pos)
            return

        if start_of_line.type == 'out':
            # 出力ポートから入力ポートに接続した場合
            print u'出力ポートから入力ポートに接続した場合'
            # 古いポート側から削除
            if self.target is not None:
                self.target.remove_old_line()
            # 新しいポート側に追加
            self.target = item
            self.target.delete_old_line()
            self.point_b = item.get_center()

        else:
            # 入力ポートから出力ポートに接続した場合
            self.target.delete_old_line()
            self.source = item
            self.point_a = item.get_center()

        # 相手がPINの場合
        if self.source.node.TYPE == 'Pin':
            self.source.node.propagate(self.target, self.source, self)

        # 自分がPINの場合
        if self.target.node.TYPE == 'Pin':
            self.target.node.propagate(self.source, self.target, self)

        self.target.lines.append(self)
        self.source.lines.append(self)

    def updatePath(self):
        path = QtGui.QPainterPath()
        path.moveTo(self.point_a)
        dx = self.point_b.x() - self.point_a.x()
        dy = self.point_b.y() - self.point_a.y()
        ctrl1 = QtCore.QPointF(self.point_a.x() + abs(dx * 0.7), self.point_a.y() + dy * 0.1)
        ctrl2 = QtCore.QPointF(self.point_b.x() - abs(dx * 0.7), self.point_a.y() + dy * 0.9)
        path.cubicTo(ctrl1, ctrl2, self.point_b)
        self.setPath(path)

    def hoverMoveEvent(self, event):
        # Do your stuff here.
        pass

    def hoverEnterEvent(self, event):
        self.pen.setColor(QtGui.QColor(255, 200, 200, 255))
        self.arrow.pen.setColor(QtGui.QColor(255, 200, 200, 255))
        self.setPen(self.pen)

    def hoverLeaveEvent(self, event):
        self.pen.setColor(self.color)
        self.arrow.pen.setColor(self.color)
        self.setPen(self.pen)

    def paint(self, painter, option, widget):
        painter.setPen(self.pen)
        painter.drawPath(self.path())
        self.arrow.paint(painter, option, widget)

    @property
    def point_a(self):
        return self._point_a

    @point_a.setter
    def point_a(self, point):
        self._point_a = point
        self.updatePath()

    @property
    def point_b(self):
        return self._point_b

    @point_b.setter
    def point_b(self, point):
        self._point_b = point
        self.updatePath()

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, widget):
        self._source = widget

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, widget):
        self._target = widget

# -----------------------------------------------------------------------------
# EOF
# -----------------------------------------------------------------------------