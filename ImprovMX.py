import os
import sys
import csv
import json
import subprocess
from typing import Any, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from improvmx_api import ImprovMxClient, ImprovMxError
from ui_i18n import I18n, read_env_with_json, get_app_meta
from ui_themes import themes_map, Theme

APP_DIR = os.path.abspath(os.path.dirname(__file__))
ENV_PATH = os.path.join(APP_DIR, ".env")

def clamp(n: int, a: int, b: int) -> int:
    return max(a, min(b, n))

class AcrylicBackground(QtWidgets.QWidget):
    def __init__(self, theme: Theme):
        super().__init__()
        self._theme = theme
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._noise = QtGui.QPixmap()
        self._regen_noise()

    def set_theme(self, theme: Theme):
        self._theme = theme
        self._regen_noise()
        self.update()

    def _regen_noise(self):
        w = 160
        h = 160
        img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QtCore.Qt.GlobalColor.transparent)

        rng = QtCore.QRandomGenerator.global_()
        alpha = int(clamp(int(self._theme.grain_opacity * 255), 0, 255))

        for y in range(h):
            for x in range(w):
                v = int(rng.bounded(256))
                img.setPixelColor(x, y, QtGui.QColor(v, v, v, alpha))

        self._noise = QtGui.QPixmap.fromImage(img)

    def paintEvent(self, e: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        r = self.rect()

        grad = QtGui.QLinearGradient(r.topLeft(), r.bottomLeft())
        grad.setColorAt(0.0, QtGui.QColor(self._theme.bg_top))
        grad.setColorAt(1.0, QtGui.QColor(self._theme.bg_bottom))
        p.fillRect(r, grad)

        if not self._noise.isNull():
            p.setOpacity(0.55)
            p.drawTiledPixmap(r, self._noise)
            p.setOpacity(1.0)

class Toast(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget, text: str, theme: Theme):
        super().__init__(parent)
        self.setObjectName("Toast")
        self._label = QtWidgets.QLabel(text)
        self._label.setWordWrap(True)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.addWidget(self._label, 1)
        self._theme = theme
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.ToolTip)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
#Toast {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
}}
#Toast QLabel {{
  color: {self._theme.text};
  font-size: 12.5px;
}}
""")

    def show_for(self, ms: int = 1400):
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            pr = parent.rect()
            x = pr.left() + (pr.width() - self.width()) // 2
            y = pr.bottom() - self.height() - 22
            self.move(parent.mapToGlobal(QtCore.QPoint(x, y)))
        self.show()
        QtCore.QTimer.singleShot(ms, self.close)

class ConfirmDialog(QtWidgets.QDialog):
    def __init__(self, title: str, message: str, ok_text: str, cancel_text: str, theme: Theme, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        self.setObjectName("ConfirmDialog")
        self._theme = theme

        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("ConfirmTitle")
        self._msg = QtWidgets.QLabel(message)
        self._msg.setWordWrap(True)
        self._msg.setObjectName("ConfirmMsg")

        self._btn_ok = QtWidgets.QPushButton(ok_text)
        self._btn_cancel = QtWidgets.QPushButton(cancel_text)
        self._btn_ok.clicked.connect(self.accept)
        self._btn_cancel.clicked.connect(self.reject)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self._btn_cancel)
        btns.addWidget(self._btn_ok)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        lay.addWidget(self._title)
        lay.addWidget(self._msg)
        lay.addLayout(btns)

        self._apply_style()
        self.setFixedWidth(440)

    def _apply_style(self):
        self.setStyleSheet(f"""
#ConfirmDialog {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
#ConfirmTitle {{
  color: {self._theme.text};
  font-size: 15px;
  font-weight: 700;
}}
#ConfirmMsg {{
  color: {self._theme.subtext};
  font-size: 12.5px;
}}
QPushButton {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 12px;
  min-width: 96px;
}}
QPushButton:hover {{
  border-color: rgba(255,255,255,0.22);
}}
QPushButton:pressed {{
  background: rgba(255,255,255,0.06);
}}
""")

class DomainForm(QtWidgets.QFrame):
    submitted = QtCore.Signal(str, str, str)

    def __init__(self, i18n: I18n, theme: Theme):
        super().__init__()
        self._i18n = i18n
        self._theme = theme
        self.setObjectName("DomainForm")
        self._title = QtWidgets.QLabel(self._i18n.t("domains.add_title"))
        self._title.setObjectName("CardTitle")

        self._domain = QtWidgets.QLineEdit()
        self._domain.setPlaceholderText(self._i18n.t("domains.domain_placeholder"))

        self._notify = QtWidgets.QLineEdit()
        self._notify.setPlaceholderText(self._i18n.t("domains.notification_email"))

        self._wl = QtWidgets.QLineEdit()
        self._wl.setPlaceholderText(self._i18n.t("domains.whitelabel"))

        self._btn = QtWidgets.QPushButton(self._i18n.t("common.create"))
        self._btn.clicked.connect(self._emit)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.addRow("Domain", self._domain)
        form.addRow("Notification", self._notify)
        form.addRow("Whitelabel", self._wl)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)
        lay.addWidget(self._title)
        lay.addLayout(form)
        lay.addWidget(self._btn, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
#DomainForm {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
#CardTitle {{
  color: {self._theme.text};
  font-size: 14px;
  font-weight: 700;
}}
QLineEdit {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 10px;
}}
QLineEdit:focus {{
  border-color: {self._theme.accent};
}}
QLabel {{
  color: {self._theme.subtext};
}}
QPushButton {{
  background: rgba(90,166,255,0.16);
  color: {self._theme.text};
  border: 1px solid rgba(90,166,255,0.28);
  border-radius: 12px;
  padding: 8px 14px;
}}
QPushButton:hover {{
  background: rgba(90,166,255,0.22);
}}
QPushButton:pressed {{
  background: rgba(90,166,255,0.12);
}}
""")

    def _emit(self):
        d = self._domain.text().strip()
        n = self._notify.text().strip()
        w = self._wl.text().strip()
        if d:
            self.submitted.emit(d, n, w)

    def reset(self):
        self._domain.clear()
        self._notify.clear()
        self._wl.clear()

    def relabel(self):
        self._title.setText(self._i18n.t("domains.add_title"))
        self._domain.setPlaceholderText(self._i18n.t("domains.domain_placeholder"))
        self._notify.setPlaceholderText(self._i18n.t("domains.notification_email"))
        self._wl.setPlaceholderText(self._i18n.t("domains.whitelabel"))
        self._btn.setText(self._i18n.t("common.create"))

    def set_theme(self, theme: Theme):
        self._theme = theme
        self._apply_style()

class AliasForm(QtWidgets.QFrame):
    submitted = QtCore.Signal(str, str)

    def __init__(self, i18n: I18n, theme: Theme):
        super().__init__()
        self._i18n = i18n
        self._theme = theme
        self.setObjectName("AliasForm")
        self._title = QtWidgets.QLabel(self._i18n.t("aliases.add_title"))
        self._title.setObjectName("CardTitle")

        self._alias = QtWidgets.QLineEdit()
        self._alias.setPlaceholderText(self._i18n.t("aliases.alias_placeholder"))

        self._forward = QtWidgets.QLineEdit()
        self._forward.setPlaceholderText(self._i18n.t("aliases.forward_placeholder"))

        self._hint = QtWidgets.QLabel(self._i18n.t("aliases.multi_hint"))
        self._hint.setObjectName("Hint")

        self._btn = QtWidgets.QPushButton(self._i18n.t("common.create"))
        self._btn.clicked.connect(self._emit)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.addRow(self._i18n.t("aliases.alias"), self._alias)
        form.addRow(self._i18n.t("aliases.forward"), self._forward)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        lay.addWidget(self._title)
        lay.addLayout(form)
        lay.addWidget(self._hint)
        lay.addWidget(self._btn, 0, QtCore.Qt.AlignmentFlag.AlignRight)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
#AliasForm {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
#CardTitle {{
  color: {self._theme.text};
  font-size: 14px;
  font-weight: 700;
}}
#Hint {{
  color: {self._theme.subtext};
  font-size: 11.5px;
}}
QLineEdit {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 10px;
}}
QLineEdit:focus {{
  border-color: {self._theme.accent};
}}
QLabel {{
  color: {self._theme.subtext};
}}
QPushButton {{
  background: rgba(90,166,255,0.16);
  color: {self._theme.text};
  border: 1px solid rgba(90,166,255,0.28);
  border-radius: 12px;
  padding: 8px 14px;
}}
QPushButton:hover {{
  background: rgba(90,166,255,0.22);
}}
QPushButton:pressed {{
  background: rgba(90,166,255,0.12);
}}
""")

    def _emit(self):
        a = self._alias.text().strip()
        f = self._forward.text().strip()
        if a and f:
            self.submitted.emit(a, f)

    def reset(self):
        self._alias.clear()
        self._forward.clear()

    def relabel(self):
        self._title.setText(self._i18n.t("aliases.add_title"))
        self._alias.setPlaceholderText(self._i18n.t("aliases.alias_placeholder"))
        self._forward.setPlaceholderText(self._i18n.t("aliases.forward_placeholder"))
        self._hint.setText(self._i18n.t("aliases.multi_hint"))
        self._btn.setText(self._i18n.t("common.create"))

    def set_theme(self, theme: Theme):
        self._theme = theme
        self._apply_style()

class TableCard(QtWidgets.QFrame):
    def __init__(self, theme: Theme):
        super().__init__()
        self._theme = theme
        self.setObjectName("TableCard")
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
#TableCard {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
QTableWidget {{
  background: transparent;
  border: none;
  gridline-color: rgba(255,255,255,0.06);
  color: {self._theme.text};
}}
QHeaderView::section {{
  background: rgba(255,255,255,0.04);
  color: {self._theme.subtext};
  border: none;
  padding: 8px 10px;
  font-weight: 600;
}}
QTableWidget::item {{
  padding-left: 8px;
  padding-right: 8px;
}}
QTableWidget::item:selected {{
  background: rgba(90,166,255,0.18);
}}
""")

    def set_theme(self, theme: Theme):
        self._theme = theme
        self._apply_style()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1080, 680)
        self.setWindowTitle("ImprovMX Studio")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._env = read_env_with_json(ENV_PATH)
        self._i18n = I18n(self._env.raw)
        self._meta = get_app_meta(self._env.raw)

        self._themes = themes_map()
        theme_name = (self._meta.get("default_theme") or "Midnight Acrylic").strip()
        self._theme = self._themes.get(theme_name) or list(self._themes.values())[0]

        self._token = (self._env.token or "").strip()
        self._client: Optional[ImprovMxClient] = ImprovMxClient(self._token) if self._token else None

        self._root = QtWidgets.QWidget()
        self.setCentralWidget(self._root)

        self._bg = AcrylicBackground(self._theme)
        self._bg.setParent(self._root)
        self._bg.lower()

        self._shell = QtWidgets.QFrame(self._root)
        self._shell.setObjectName("Shell")

        self._title = QtWidgets.QLabel(self._meta.get("name") or "ImprovMX Studio")
        self._title.setObjectName("AppTitle")
        self._subtitle = QtWidgets.QLabel(self._meta.get("subtitle") or "")
        self._subtitle.setObjectName("AppSubTitle")

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText(self._i18n.t("common.search"))
        self._search.textChanged.connect(self._on_search)

        self._btn_refresh = QtWidgets.QPushButton(self._i18n.t("common.refresh"))
        self._btn_refresh.clicked.connect(self._refresh_current)

        self._seg = QtWidgets.QTabBar()
        self._seg.setObjectName("Segment")
        self._seg.setExpanding(False)
        self._seg.setUsesScrollButtons(False)
        self._seg.addTab(self._i18n.t("nav.domains"))
        self._seg.addTab(self._i18n.t("nav.aliases"))
        self._seg.addTab(self._i18n.t("nav.bulk"))
        self._seg.addTab(self._i18n.t("nav.settings"))
        self._seg.currentChanged.connect(self._on_tab)

        header_left = QtWidgets.QVBoxLayout()
        header_left.setSpacing(2)
        header_left.addWidget(self._title)
        header_left.addWidget(self._subtitle)

        header_right = QtWidgets.QHBoxLayout()
        header_right.setSpacing(10)
        header_right.addWidget(self._search, 1)
        header_right.addWidget(self._btn_refresh)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addLayout(header_left, 0)
        header.addStretch(1)
        header.addLayout(header_right, 1)

        self._stack = QtWidgets.QStackedWidget()

        self._page_domains = self._build_domains()
        self._page_aliases = self._build_aliases()
        self._page_bulk = self._build_bulk()
        self._page_settings = self._build_settings()

        self._stack.addWidget(self._page_domains)
        self._stack.addWidget(self._page_aliases)
        self._stack.addWidget(self._page_bulk)
        self._stack.addWidget(self._page_settings)

        top = QtWidgets.QVBoxLayout(self._shell)
        top.setContentsMargins(22, 18, 22, 18)
        top.setSpacing(14)
        top.addLayout(header)
        top.addWidget(self._seg)
        top.addWidget(self._stack, 1)

        root_l = QtWidgets.QVBoxLayout(self._root)
        root_l.setContentsMargins(18, 18, 18, 18)
        root_l.addWidget(self._shell, 1)

        self._status = QtWidgets.QLabel(self._i18n.t("status.ready"))
        self._status.setObjectName("Status")
        root_l.addWidget(self._status)

        self._apply_shell_style()
        self._apply_window_opacity_from_env()

        QtCore.QTimer.singleShot(50, self._initial_load)

    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        self._bg.setGeometry(self._root.rect())

    def _apply_window_opacity_from_env(self):
        wnd = (self._meta.get("window") or {})
        op = int((wnd.get("opacity_percent") or 92))
        op = clamp(op, 55, 100)
        self.setWindowOpacity(op / 100.0)

    def _apply_shell_style(self):
        self._shell.setStyleSheet(f"""
#Shell {{
  background: rgba(0,0,0,0.12);
  border: 1px solid {self._theme.stroke};
  border-radius: 24px;
}}
#AppTitle {{
  color: {self._theme.text};
  font-size: 18px;
  font-weight: 800;
}}
#AppSubTitle {{
  color: {self._theme.subtext};
  font-size: 12px;
}}
#Status {{
  color: {self._theme.subtext};
  font-size: 11.5px;
  padding-left: 8px;
}}
QLineEdit {{
  background: {self._theme.card};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
  padding: 9px 12px;
}}
QLineEdit:focus {{
  border-color: {self._theme.accent};
}}
QPushButton {{
  background: {self._theme.card};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
  padding: 9px 12px;
}}
QPushButton:hover {{
  border-color: rgba(255,255,255,0.22);
}}
QPushButton:pressed {{
  background: rgba(255,255,255,0.06);
}}
QTabBar::tab {{
  background: {self._theme.card};
  color: {self._theme.subtext};
  border: 1px solid {self._theme.stroke};
  padding: 9px 14px;
  border-radius: 14px;
  margin-right: 10px;
  min-width: 110px;
  font-weight: 600;
}}
QTabBar::tab:selected {{
  color: {self._theme.text};
  border-color: rgba(90,166,255,0.34);
  background: rgba(90,166,255,0.12);
}}
""")

    def _set_status(self, key: str, **fmt: Any):
        self._status.setText(self._i18n.t(key, **fmt))

    def _toast(self, text: str):
        Toast(self, text, self._theme).show_for()

    def _guard_token(self) -> bool:
        if not self._token:
            self._toast(self._i18n.t("settings.token_hint"))
            self._seg.setCurrentIndex(3)
            return False
        if not self._client:
            self._client = ImprovMxClient(self._token)
        return True

    def _initial_load(self):
        self._refresh_domains()

    def _on_tab(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._search.setVisible(idx in (0, 1))
        self._btn_refresh.setEnabled(idx in (0, 1, 2))
        self._refresh_current()

    def _on_search(self, _t: str):
        self._refresh_current()

    def _refresh_current(self):
        idx = self._seg.currentIndex()
        if idx == 0:
            self._refresh_domains()
        elif idx == 1:
            self._refresh_aliases()
        elif idx == 2:
            pass

    def _build_domains(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        self._domain_form = DomainForm(self._i18n, self._theme)
        self._domain_form.submitted.connect(self._create_domain)

        self._domains_card = TableCard(self._theme)
        card_l = QtWidgets.QVBoxLayout(self._domains_card)
        card_l.setContentsMargins(14, 12, 14, 14)
        card_l.setSpacing(10)

        self._domains_table = QtWidgets.QTableWidget(0, 4)
        self._domains_table.setHorizontalHeaderLabels(["Domain", "Active", "Notification", "Whitelabel"])
        self._domains_table.horizontalHeader().setStretchLastSection(True)
        self._domains_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._domains_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._domains_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._domains_table.customContextMenuRequested.connect(self._domains_menu)
        self._domains_table.doubleClicked.connect(self._go_aliases_for_selected_domain)

        card_l.addWidget(self._domains_table, 1)

        lay.addWidget(self._domain_form, 0)
        lay.addWidget(self._domains_card, 1)
        return page

    def _domains_menu(self, pos: QtCore.QPoint):
        row = self._domains_table.currentRow()
        if row < 0:
            return
        domain = self._domains_table.item(row, 0).text()
        menu = QtWidgets.QMenu(self)
        a_open_aliases = menu.addAction(self._i18n.t("nav.aliases"))
        a_copy = menu.addAction(self._i18n.t("common.copy"))
        a_del = menu.addAction(self._i18n.t("common.delete"))
        act = menu.exec(self._domains_table.mapToGlobal(pos))
        if act == a_open_aliases:
            self._domain_combo.setCurrentText(domain)
            self._seg.setCurrentIndex(1)
        elif act == a_copy:
            QtWidgets.QApplication.clipboard().setText(domain)
            self._toast(self._i18n.t("common.copied"))
        elif act == a_del:
            self._delete_domain(domain)

    def _go_aliases_for_selected_domain(self):
        row = self._domains_table.currentRow()
        if row < 0:
            return
        domain = self._domains_table.item(row, 0).text()
        self._domain_combo.setCurrentText(domain)
        self._seg.setCurrentIndex(1)

    def _refresh_domains(self):
        if not self._guard_token():
            return
        q = self._search.text().strip()
        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            domains, _ = self._client.list_domains(q=q if q else None, limit=100, page=1)
            self._domains_table.setRowCount(0)
            for d in domains:
                r = self._domains_table.rowCount()
                self._domains_table.insertRow(r)
                self._domains_table.setItem(r, 0, QtWidgets.QTableWidgetItem(d.domain))
                self._domains_table.setItem(r, 1, QtWidgets.QTableWidgetItem("1" if d.active else "0"))
                self._domains_table.setItem(r, 2, QtWidgets.QTableWidgetItem(d.notification_email or ""))
                self._domains_table.setItem(r, 3, QtWidgets.QTableWidgetItem(d.whitelabel or ""))
            self._domains_table.resizeColumnsToContents()
            self._sync_domain_combo(domains)
            self._set_status("status.updated")
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _sync_domain_combo(self, domains: List[Any]):
        items = [d.domain for d in domains]
        cur = self._domain_combo.currentText().strip()

        self._domain_combo.blockSignals(True)
        self._bulk_domain.blockSignals(True)

        self._domain_combo.clear()
        self._bulk_domain.clear()
        self._domain_combo.addItems(items)
        self._bulk_domain.addItems(items)

        if cur and cur in items:
            self._domain_combo.setCurrentText(cur)
        elif items:
            self._domain_combo.setCurrentIndex(0)

        if items:
            self._bulk_domain.setCurrentIndex(0)

        self._domain_combo.blockSignals(False)
        self._bulk_domain.blockSignals(False)

    def _create_domain(self, domain: str, notification: str, whitelabel: str):
        if not self._guard_token():
            return
        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self._client.add_domain(domain=domain, notification_email=notification or None, whitelabel=whitelabel or None)
            self._domain_form.reset()
            self._refresh_domains()
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _delete_domain(self, domain: str):
        if not self._guard_token():
            return
        dlg = ConfirmDialog(
            self._i18n.t("common.confirm"),
            self._i18n.t("domains.delete_confirm", domain=domain),
            self._i18n.t("common.delete"),
            self._i18n.t("common.cancel"),
            self._theme,
            self
        )
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self._client.delete_domain(domain)
            self._refresh_domains()
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _build_aliases(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        topbar = QtWidgets.QFrame()
        topbar.setObjectName("TopBar")
        tb = QtWidgets.QHBoxLayout(topbar)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(10)

        self._domain_combo = QtWidgets.QComboBox()
        self._domain_combo.setEditable(True)
        self._domain_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self._domain_combo.currentTextChanged.connect(lambda _t: self._refresh_aliases())

        self._alias_form = AliasForm(self._i18n, self._theme)
        self._alias_form.submitted.connect(self._create_alias)

        tb.addWidget(QtWidgets.QLabel(self._i18n.t("aliases.domain_select")))
        tb.addWidget(self._domain_combo, 1)

        self._aliases_card = TableCard(self._theme)
        card_l = QtWidgets.QVBoxLayout(self._aliases_card)
        card_l.setContentsMargins(14, 12, 14, 14)
        card_l.setSpacing(10)

        self._aliases_table = QtWidgets.QTableWidget(0, 3)
        self._aliases_table.setHorizontalHeaderLabels([self._i18n.t("aliases.alias"), self._i18n.t("aliases.forward"), "ID"])
        self._aliases_table.horizontalHeader().setStretchLastSection(True)
        self._aliases_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._aliases_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._aliases_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._aliases_table.customContextMenuRequested.connect(self._aliases_menu)

        card_l.addWidget(self._aliases_table, 1)

        lay.addWidget(topbar, 0)
        lay.addWidget(self._alias_form, 0)
        lay.addWidget(self._aliases_card, 1)
        self._apply_combo_style(page)
        return page

    def _apply_combo_style(self, page: QtWidgets.QWidget):
        page.setStyleSheet(f"""
QLabel {{
  color: {self._theme.subtext};
  font-size: 12px;
}}
QComboBox {{
  background: {self._theme.card};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
  padding: 8px 10px;
}}
QComboBox:focus {{
  border-color: {self._theme.accent};
}}
QComboBox QAbstractItemView {{
  background: rgba(10,20,40,0.92);
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  selection-background-color: rgba(90,166,255,0.20);
}}
""")

    def _aliases_menu(self, pos: QtCore.QPoint):
        row = self._aliases_table.currentRow()
        if row < 0:
            return
        domain = self._domain_combo.currentText().strip()
        alias = self._aliases_table.item(row, 0).text()
        forward = self._aliases_table.item(row, 1).text()
        alias_id = int(self._aliases_table.item(row, 2).text())

        menu = QtWidgets.QMenu(self)
        a_copy = menu.addAction(self._i18n.t("common.copy"))
        a_edit = menu.addAction(self._i18n.t("common.edit"))
        a_del = menu.addAction(self._i18n.t("common.delete"))
        act = menu.exec(self._aliases_table.mapToGlobal(pos))
        if act == a_copy:
            QtWidgets.QApplication.clipboard().setText(f"{alias}@{domain} -> {forward}")
            self._toast(self._i18n.t("common.copied"))
        elif act == a_edit:
            self._edit_alias_dialog(domain, alias_id, alias, forward)
        elif act == a_del:
            self._delete_alias(domain, alias_id, alias)

    def _refresh_aliases(self):
        if not self._guard_token():
            return
        domain = self._domain_combo.currentText().strip()
        if not domain:
            return
        q = self._search.text().strip()
        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            aliases, _ = self._client.list_aliases(domain=domain, q=q if q else None, limit=100, page=1)
            self._aliases_table.setRowCount(0)
            for a in aliases:
                r = self._aliases_table.rowCount()
                self._aliases_table.insertRow(r)
                self._aliases_table.setItem(r, 0, QtWidgets.QTableWidgetItem(a.alias))
                self._aliases_table.setItem(r, 1, QtWidgets.QTableWidgetItem(a.forward))
                self._aliases_table.setItem(r, 2, QtWidgets.QTableWidgetItem(str(a.id)))
            self._aliases_table.resizeColumnsToContents()
            self._set_status("status.updated")
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _create_alias(self, alias: str, forward: str):
        if not self._guard_token():
            return
        domain = self._domain_combo.currentText().strip()
        if not domain:
            return
        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self._client.add_alias(domain=domain, alias=alias, forward=forward)
            self._alias_form.reset()
            self._refresh_aliases()
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _edit_alias_dialog(self, domain: str, alias_id: int, alias: str, forward: str):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(self._i18n.t("common.edit"))
        dlg.setModal(True)
        dlg.setObjectName("EditAliasDlg")

        t = QtWidgets.QLabel(f"{alias}@{domain}")
        t.setObjectName("EditTitle")

        e_alias = QtWidgets.QLineEdit(alias)
        e_forward = QtWidgets.QLineEdit(forward)

        b_save = QtWidgets.QPushButton(self._i18n.t("common.save"))
        b_cancel = QtWidgets.QPushButton(self._i18n.t("common.cancel"))
        b_cancel.clicked.connect(dlg.reject)

        def do_save():
            a2 = e_alias.text().strip()
            f2 = e_forward.text().strip()
            if not a2 or not f2:
                return
            self._set_status("status.loading")
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            try:
                self._client.update_alias(domain=domain, alias_id=alias_id, alias=a2, forward=f2)
                dlg.accept()
                self._refresh_aliases()
            except ImprovMxError as ex:
                self._set_status("status.request_failed", details=str(ex.payload))
                self._toast(self._i18n.t("common.error"))
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()

        b_save.clicked.connect(do_save)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.addRow(self._i18n.t("aliases.alias"), e_alias)
        form.addRow(self._i18n.t("aliases.forward"), e_forward)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(b_cancel)
        btns.addWidget(b_save)

        lay = QtWidgets.QVBoxLayout(dlg)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        lay.addWidget(t)
        lay.addLayout(form)
        lay.addLayout(btns)

        dlg.setStyleSheet(f"""
#EditAliasDlg {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
#EditTitle {{
  color: {self._theme.text};
  font-size: 14px;
  font-weight: 800;
}}
QLabel {{
  color: {self._theme.subtext};
}}
QLineEdit {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 10px;
}}
QLineEdit:focus {{
  border-color: {self._theme.accent};
}}
QPushButton {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 14px;
  min-width: 100px;
}}
QPushButton:hover {{
  border-color: rgba(255,255,255,0.22);
}}
QPushButton:pressed {{
  background: rgba(255,255,255,0.06);
}}
""")
        dlg.setFixedWidth(520)
        dlg.exec()

    def _delete_alias(self, domain: str, alias_id: int, alias: str):
        if not self._guard_token():
            return
        dlg = ConfirmDialog(
            self._i18n.t("common.confirm"),
            self._i18n.t("aliases.delete_confirm", alias=alias, domain=domain),
            self._i18n.t("common.delete"),
            self._i18n.t("common.cancel"),
            self._theme,
            self
        )
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self._client.delete_alias(domain=domain, alias_id=alias_id)
            self._refresh_aliases()
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _build_bulk(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        head = QtWidgets.QFrame()
        h = QtWidgets.QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        self._bulk_domain = QtWidgets.QComboBox()
        self._bulk_domain.setEditable(True)
        self._bulk_domain.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)

        self._bulk_behavior = QtWidgets.QComboBox()
        self._bulk_behavior.addItems([
            self._i18n.t("bulk.behavior_add"),
            self._i18n.t("bulk.behavior_update"),
            self._i18n.t("bulk.behavior_delete")
        ])

        h.addWidget(QtWidgets.QLabel(self._i18n.t("aliases.domain_select")))
        h.addWidget(self._bulk_domain, 1)
        h.addWidget(QtWidgets.QLabel(self._i18n.t("bulk.behavior")))
        h.addWidget(self._bulk_behavior, 0)

        self._bulk_help = QtWidgets.QLabel(self._i18n.t("bulk.help"))
        self._bulk_help.setWordWrap(True)
        self._bulk_help.setObjectName("BulkHelp")

        self._bulk_text = QtWidgets.QPlainTextEdit()
        self._bulk_text.setPlaceholderText("info,you@gmail.com\nsupport,a@x.com,b@y.com\n*,catchall@somewhere.com")

        self._bulk_run = QtWidgets.QPushButton(self._i18n.t("bulk.run"))
        self._bulk_run.clicked.connect(self._run_bulk)

        card = QtWidgets.QFrame()
        card.setObjectName("BulkCard")
        c = QtWidgets.QVBoxLayout(card)
        c.setContentsMargins(16, 14, 16, 14)
        c.setSpacing(10)
        c.addWidget(self._bulk_help)
        c.addWidget(self._bulk_text, 1)
        c.addWidget(self._bulk_run, 0, QtCore.Qt.AlignmentFlag.AlignRight)

        lay.addWidget(head, 0)
        lay.addWidget(card, 1)

        page.setStyleSheet(f"""
QLabel {{
  color: {self._theme.subtext};
  font-size: 12px;
}}
QComboBox {{
  background: {self._theme.card};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
  padding: 8px 10px;
}}
QComboBox QAbstractItemView {{
  background: rgba(10,20,40,0.92);
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  selection-background-color: rgba(90,166,255,0.20);
}}
#BulkCard {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
#BulkHelp {{
  color: {self._theme.subtext};
  font-size: 12px;
}}
QPlainTextEdit {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
  padding: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}}
QPlainTextEdit:focus {{
  border-color: {self._theme.accent};
}}
QPushButton {{
  background: rgba(90,166,255,0.16);
  color: {self._theme.text};
  border: 1px solid rgba(90,166,255,0.28);
  border-radius: 12px;
  padding: 8px 14px;
}}
""")
        return page

    def _run_bulk(self):
        if not self._guard_token():
            return
        domain = self._bulk_domain.currentText().strip()
        if not domain:
            return
        behavior = self._bulk_behavior.currentText().strip()
        raw = self._bulk_text.toPlainText()

        rows: List[Dict[str, str]] = []
        for line in raw.splitlines():
            s = line.strip()
            if not s:
                continue
            parts = list(csv.reader([s]))[0]
            alias = (parts[0].strip() if parts else "")
            if not alias:
                continue
            if behavior == "delete":
                rows.append({"alias": alias})
                continue
            forward = ""
            if len(parts) > 1:
                forward = ",".join([p.strip() for p in parts[1:] if p.strip()])
            if not forward:
                continue
            rows.append({"alias": alias, "forward": forward})

        if not rows:
            return

        self._set_status("status.loading")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            res = self._client.bulk_aliases(domain=domain, aliases=rows, behavior=behavior)
            txt = json.dumps(res, ensure_ascii=False, indent=2)
            self._toast("Bulk: ok")

            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Bulk result")
            dlg.setModal(True)
            dlg.setObjectName("BulkResultDlg")

            box = QtWidgets.QPlainTextEdit()
            box.setReadOnly(True)
            box.setPlainText(txt)

            b = QtWidgets.QPushButton(self._i18n.t("common.close"))
            b.clicked.connect(dlg.accept)

            lay = QtWidgets.QVBoxLayout(dlg)
            lay.setContentsMargins(16, 14, 16, 14)
            lay.setSpacing(10)
            lay.addWidget(box, 1)
            lay.addWidget(b, 0, QtCore.Qt.AlignmentFlag.AlignRight)

            dlg.setStyleSheet(f"""
#BulkResultDlg {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
QPlainTextEdit {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 14px;
  padding: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}}
QPushButton {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 14px;
  min-width: 100px;
}}
""")
            dlg.setFixedSize(760, 520)
            dlg.exec()
        except ImprovMxError as ex:
            self._set_status("status.request_failed", details=str(ex.payload))
            self._toast(self._i18n.t("common.error"))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _build_settings(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        card = QtWidgets.QFrame()
        card.setObjectName("SettingsCard")
        c = QtWidgets.QVBoxLayout(card)
        c.setContentsMargins(16, 14, 16, 14)
        c.setSpacing(12)

        self._token_edit = QtWidgets.QLineEdit(self._token)
        self._token_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        self._token_hint = QtWidgets.QLabel(self._i18n.t("settings.token_hint"))
        self._token_hint.setWordWrap(True)
        self._token_hint.setObjectName("Hint")

        self._lang = QtWidgets.QComboBox()
        self._lang.addItems(list(self._i18n.available_langs()))
        self._lang.setCurrentText(self._i18n.lang)
        self._lang.currentTextChanged.connect(self._apply_language)

        self._theme_combo = QtWidgets.QComboBox()
        self._theme_combo.addItems(list(self._themes.keys()))
        self._theme_combo.setCurrentText(self._theme.name)
        self._theme_combo.currentTextChanged.connect(self._apply_theme)

        self._opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._opacity.setMinimum(55)
        self._opacity.setMaximum(100)
        self._opacity.setValue(int(self.windowOpacity() * 100))
        self._opacity.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))

        self._btn_open_env = QtWidgets.QPushButton(self._i18n.t("settings.open_env"))
        self._btn_open_env.clicked.connect(self._reveal_env)

        self._btn_save = QtWidgets.QPushButton(self._i18n.t("common.save"))
        self._btn_save.clicked.connect(self._save_settings)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        form.addRow(self._i18n.t("settings.token"), self._token_edit)
        form.addRow("", self._token_hint)
        form.addRow(self._i18n.t("settings.language"), self._lang)
        form.addRow(self._i18n.t("settings.theme"), self._theme_combo)
        form.addRow(self._i18n.t("settings.opacity"), self._opacity)

        c.addLayout(form)
        b = QtWidgets.QHBoxLayout()
        b.addWidget(self._btn_open_env)
        b.addStretch(1)
        b.addWidget(self._btn_save)
        c.addLayout(b)

        lay.addWidget(card, 0)
        lay.addStretch(1)

        page.setStyleSheet(f"""
#SettingsCard {{
  background: {self._theme.card};
  border: 1px solid {self._theme.stroke};
  border-radius: 18px;
}}
QLabel {{
  color: {self._theme.subtext};
  font-size: 12px;
}}
#Hint {{
  color: {self._theme.subtext};
  font-size: 11.5px;
}}
QLineEdit {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 10px;
}}
QComboBox {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 10px;
}}
QComboBox QAbstractItemView {{
  background: rgba(10,20,40,0.92);
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  selection-background-color: rgba(90,166,255,0.20);
}}
QSlider::groove:horizontal {{
  height: 6px;
  background: rgba(255,255,255,0.10);
  border-radius: 999px;
}}
QSlider::handle:horizontal {{
  width: 18px;
  margin: -7px 0;
  border-radius: 9px;
  background: rgba(90,166,255,0.80);
}}
QPushButton {{
  background: {self._theme.card2};
  color: {self._theme.text};
  border: 1px solid {self._theme.stroke};
  border-radius: 12px;
  padding: 8px 14px;
}}
""")
        return page

    def _reveal_env(self):
        path = ENV_PATH
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])

    def _save_settings(self):
        token = self._token_edit.text().strip()
        self._token = token
        self._client = ImprovMxClient(self._token) if self._token else None

        with open(ENV_PATH, "r", encoding="utf-8") as f:
            text = f.read()

        lines = text.splitlines()
        out: List[str] = []
        replaced = False
        for line in lines:
            if line.strip().startswith("TOKEN=") and not replaced:
                out.append(f"TOKEN={token}")
                replaced = True
            else:
                out.append(line)

        if not replaced:
            out.insert(0, f"TOKEN={token}")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(out).rstrip() + "\n")

        self._toast(self._i18n.t("status.updated"))

    def _apply_language(self, lang: str):
        self._i18n.set_lang(lang)
        self._seg.setTabText(0, self._i18n.t("nav.domains"))
        self._seg.setTabText(1, self._i18n.t("nav.aliases"))
        self._seg.setTabText(2, self._i18n.t("nav.bulk"))
        self._seg.setTabText(3, self._i18n.t("nav.settings"))
        self._btn_refresh.setText(self._i18n.t("common.refresh"))
        self._search.setPlaceholderText(self._i18n.t("common.search"))
        self._alias_form.relabel()
        self._domain_form.relabel()
        self._bulk_help.setText(self._i18n.t("bulk.help"))
        self._bulk_run.setText(self._i18n.t("bulk.run"))
        self._btn_open_env.setText(self._i18n.t("settings.open_env"))
        self._btn_save.setText(self._i18n.t("common.save"))
        self._token_hint.setText(self._i18n.t("settings.token_hint"))
        self._set_status("status.ready")
        self._refresh_current()

    def _apply_theme(self, theme_name: str):
        th = self._themes.get(theme_name)
        if not th:
            return
        self._theme = th
        self._bg.set_theme(th)
        self._apply_shell_style()
        self._domain_form.set_theme(th)
        self._aliases_card.set_theme(th)
        self._domains_card.set_theme(th)
        self._alias_form.set_theme(th)
        self._apply_combo_style(self._page_aliases)
        self._toast(theme_name)

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("ImprovMX Studio")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
