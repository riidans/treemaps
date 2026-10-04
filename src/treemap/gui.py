from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QRectF, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from treemap.layout import FOLDER_HEADER_HEIGHT, LayoutItem, compute_layout
from treemap.models import AggregateLeaf, FileNode
from treemap.scanner import scan_filesystem

MAX_PARENT_COLORS = 10


def prepare_display_root(root: FileNode) -> FileNode:
    """Keep the ten largest directories visible and group the rest as Other."""
    if any(child.is_dir and child.name.startswith("Other (") for child in root.children):
        return root

    directories = sorted(
        (child for child in root.children if child.is_dir),
        key=lambda child: child.size,
        reverse=True,
    )
    visible = directories[:MAX_PARENT_COLORS]
    visible_ids = {id(child) for child in visible}
    remaining = [child for child in directories if id(child) not in visible_ids]
    if not remaining:
        return root

    other = FileNode(
        path=root.path / "Other",
        name=f"Other ({len(remaining)} folders)",
        size=sum(child.size for child in remaining),
        is_dir=True,
    )
    for child in remaining:
        other.add_child(child)

    root.children = [
        child for child in root.children
        if not child.is_dir or id(child) in visible_ids
    ]
    root.add_child(other)
    return root


class ScanWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            root = scan_filesystem(
                self.path,
                on_progress=lambda _path, count: self.progress.emit(count),
            )
        except (FileNotFoundError, OSError) as exc:
            self.failed.emit(str(exc))
        else:
            self.finished.emit(root)


class TreemapCanvas(QWidget):
    """Small, interactive canvas that paints the current LayoutItems."""

    _HUES = (8, 42, 76, 118, 162, 205, 250, 292, 330)

    def __init__(self, root: FileNode, on_open_directory, on_select_file) -> None:
        super().__init__()
        self.root = root
        self.current_root = root
        self._history: list[FileNode] = []
        self._items: list[LayoutItem] = []
        self._selected: LayoutItem | None = None
        self._on_open_directory = on_open_directory
        self._on_select_file = on_select_file
        self.setMinimumSize(500, 350)
        self.setMouseTracking(True)
        self.setToolTip("Click a directory to open it")

    @property
    def can_go_back(self) -> bool:
        return bool(self._history)

    def go_back(self) -> None:
        if not self._history:
            return
        self.current_root = self._history.pop()
        self._selected = None
        self._rebuild_layout()
        self.update()

    def open_directory(self, node: FileNode) -> None:
        if node is self.current_root or not node.is_dir:
            return
        self._history.append(self.current_root)
        self.current_root = node
        self._selected = None
        self._rebuild_layout()
        self.update()

    def resizeEvent(self, event) -> None:
        self._rebuild_layout()
        super().resizeEvent(event)

    def _rebuild_layout(self) -> None:
        self._items = compute_layout(
            self.current_root,
            (0.0, 0.0, float(max(0, self.width())), float(max(0, self.height()))),
            min_size=24.0,
            max_depth=5,
            padding=2.0,
        )

    def _top_level_directory(self, node: FileNode) -> FileNode:
        current = node
        while current.parent is not None and current.parent is not self.root:
            current = current.parent
        return current

    def _current_level_directory(self, node: FileNode) -> FileNode:
        current = node
        while current.parent is not None and current.parent is not self.current_root:
            current = current.parent
        return current

    def color_for(self, node: FileNode) -> QColor:
        if isinstance(node, AggregateLeaf):
            return QColor("#7f8c8d")

        top_level = self._top_level_directory(node)
        top_level_nodes = [child for child in self.root.children if child.is_dir]
        try:
            index = top_level_nodes.index(top_level)
        except ValueError:
            index = 0

        hue = self._HUES[index % len(self._HUES)]
        depth = max(0, len(node.path.parts) - len(top_level.path.parts))
        saturation = max(75, 175 - (depth * 18))
        value = min(245, 215 + (depth * 6))
        return QColor.fromHsv(hue, saturation, value)

    def _item_at(self, position) -> LayoutItem | None:
        x, y = position.x(), position.y()
        for item in reversed(self._items):
            ix, iy, width, height = item.rect
            if ix <= x <= ix + width and iy <= y <= iy + height:
                return item
        return None

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024.0 or unit == "TB":
                if unit == "B":
                    return f"{int(value)} {unit}"
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{int(size)} B"

    def _folder_group_bounds(self) -> dict[int, tuple[FileNode, QRectF, bool, int, bool]]:
        groups: dict[int, tuple[FileNode, QRectF, bool, int, bool]] = {}
        for item in self._items:
            x, y, width, height = item.rect
            item_rect = QRectF(x, y, width, height)
            item_has_text = width >= 70 and height >= 28
            folder = item.node if item.node.is_dir else item.node.parent
            if folder is None or folder is self.current_root or not folder.is_dir:
                continue

            depth = 0
            depth_node = folder
            while depth_node.parent is not None and depth_node.parent is not self.current_root:
                depth += 1
                depth_node = depth_node.parent

            key = id(folder)
            if key not in groups:
                groups[key] = (folder, item_rect, item.node is not folder, depth, item_has_text)
            else:
                groups[key] = (
                    folder,
                    groups[key][1].united(item_rect),
                    groups[key][2] or item.node is not folder,
                    groups[key][3],
                    groups[key][4] or item_has_text,
                )
        return groups

    def _folder_label(self, folder: FileNode) -> str:
        return folder.name

    def _main_folder_group_bounds(self) -> dict[int, tuple[FileNode, QRectF, bool]]:
        groups: dict[int, tuple[FileNode, QRectF, bool]] = {}
        for item in self._items:
            ancestor = item.node if item.node.is_dir else item.node.parent
            main_folder = None
            while ancestor is not None and ancestor is not self.current_root:
                if ancestor.parent is self.current_root:
                    main_folder = ancestor
                    break
                ancestor = ancestor.parent
            if main_folder is None:
                continue

            x, y, width, height = item.rect
            item_rect = QRectF(x, y, width, height)
            key = id(main_folder)
            if key not in groups:
                groups[key] = (main_folder, item_rect, item.node is not main_folder)
            else:
                groups[key] = (
                    main_folder,
                    groups[key][1].united(item_rect),
                    groups[key][2] or item.node is not main_folder,
                )
        return groups

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        item = self._item_at(event.position())
        if item is None:
            self._selected = None
            self.update()
            return
        self._selected = item
        self._on_select_file(item.node)
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        item = self._item_at(event.position())
        if item is None:
            return

        self._selected = item
        directory = self._current_level_directory(item.node)
        if directory.is_dir:
            self._on_open_directory(directory)
        else:
            self._on_select_file(item.node)
        self.update()

    def contextMenuEvent(self, event) -> None:
        item = self._item_at(event.pos())
        if item is None:
            return

        self._selected = item
        menu = QMenu(self)
        open_action = menu.addAction("Open in File Manager")
        chosen_action = menu.exec(event.globalPos())
        if chosen_action is open_action:
            self._open_in_file_manager(item.node)
        self.update()

    @staticmethod
    def _open_in_file_manager(node: FileNode) -> None:
        path = Path(node.path)
        if isinstance(node, AggregateLeaf) or node.is_dir:
            target = path
            select_file = False
        else:
            target = path.parent
            select_file = True

        if sys.platform.startswith("win"):
            if select_file:
                subprocess.Popen(["explorer.exe", f"/select,{path}"])
            else:
                os.startfile(str(target))
        elif sys.platform == "darwin":
            if select_file:
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def mouseMoveEvent(self, event) -> None:
        item = self._item_at(event.position())
        self.setToolTip(str(item.node.path) if item is not None else "Click a directory to open it")
        super().mouseMoveEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#17202a"))

        if not self._items:
            painter.setPen(QColor("#aab7c4"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No files to display")
            painter.end()
            return

        for item in self._items:
            x, y, width, height = item.rect
            rect = QRectF(x, y, width, height)
            painter.fillRect(rect, self.color_for(item.node))
            border_color = QColor("#ffffff") if item is self._selected else QColor("#263746")
            border_width = 2 if item is self._selected else 1
            painter.setPen(QPen(border_color, border_width))
            painter.drawRect(rect)

            if width >= 70 and height >= 28:
                painter.setPen(QColor("#101820"))
                font = QFont(self.font())
                font.setPointSize(9)
                painter.setFont(font)
                painter.drawText(
                    rect.adjusted(5, 3, -5, -3),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    item.node.name,
                )

        # Outline each main legend folder, even when all visible rectangles
        # are descendants several levels below it.
        label_font = QFont(self.font())
        label_font.setBold(True)
        label_font.setPointSize(9)
        painter.setFont(label_font)
        metrics = QFontMetrics(label_font)

        for folder, group_rect, has_descendants in self._main_folder_group_bounds().values():
            if has_descendants:
                group_rect = group_rect.adjusted(0, -FOLDER_HEADER_HEIGHT, 0, 0)
            if group_rect.width() < 90 or group_rect.height() < 34:
                continue

            outline = self.color_for(folder).darker(145)
            outline.setAlpha(235)
            painter.setPen(QPen(outline, 2))
            painter.drawRect(group_rect.adjusted(1, 1, -1, -1))

            label = f"{self._folder_label(folder)} · {self._format_size(folder.size)}"
            label_width = min(
                max(90.0, float(metrics.horizontalAdvance(label) + 12)),
                max(90.0, group_rect.width() - 8.0),
            )
            label_rect = QRectF(group_rect.left() + 4, group_rect.top() + 4, label_width, 22)
            painter.fillRect(label_rect, QColor(16, 24, 32, 220))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                label_rect.adjusted(6, 0, -6, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

        # Nested labels are fallback labels only, so the map stays readable.
        for folder, group_rect, has_descendants, depth, has_text in self._folder_group_bounds().values():
            if folder.parent is self.current_root or has_text:
                continue
            if group_rect.width() < 90 or group_rect.height() < 34:
                continue

            outline = self.color_for(folder).darker(145)
            outline.setAlpha(235)
            painter.setPen(QPen(outline, 2))
            painter.drawRect(group_rect.adjusted(1, 1, -1, -1))

            label = f"{self._folder_label(folder)} · {self._format_size(folder.size)}"
            label_width = min(
                max(90.0, float(metrics.horizontalAdvance(label) + 12)),
                max(90.0, group_rect.width() - 8.0),
            )
            label_rect = QRectF(
                group_rect.right() - label_width - 4,
                group_rect.top() + 4 + (depth * 20),
                label_width,
                22,
            )
            painter.fillRect(label_rect, QColor(16, 24, 32, 220))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                label_rect.adjusted(6, 0, -6, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

        painter.end()


class TreemapWindow(QMainWindow):
    def __init__(self, root: FileNode | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Treemap")
        self.resize(1100, 750)
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None

        if root is None:
            root = FileNode(Path(), "", is_dir=True)

        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setStyleSheet("font-size: 13px; padding: 5px 2px;")

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._go_back)
        self.choose_button = QPushButton("Choose Folder")
        self.choose_button.clicked.connect(self._choose_folder)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedWidth(170)
        self.progress_bar.setVisible(False)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.choose_button)
        toolbar.addWidget(self.progress_bar)
        toolbar.addWidget(self.path_label, 1)

        self.canvas = TreemapCanvas(root, self._open_directory, self._select_file)
        self.legend_widget = QWidget()
        self.legend_layout = QHBoxLayout(self.legend_widget)
        self.legend_layout.setContentsMargins(0, 0, 0, 4)
        self.legend_layout.setSpacing(6)
        self.legend_widget.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.legend_scroll = QScrollArea()
        self.legend_scroll.setWidget(self.legend_widget)
        self.legend_scroll.setWidgetResizable(False)
        self.legend_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.legend_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.legend_scroll.setFixedHeight(48)
        self.legend_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._rebuild_legend()
        self.status_label = QLabel("Click a directory to drill down.")
        self.status_label.setStyleSheet("color: #657786; padding: 3px 2px;")
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #657786; padding: 3px 2px;")
        footer = QHBoxLayout()
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.summary_label)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.addLayout(toolbar)
        layout.addWidget(self.legend_scroll)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(footer)
        self.setCentralWidget(central)

        self._update_header()

    def _update_header(self) -> None:
        self.path_label.setText(str(self.canvas.current_root.path))
        self.back_button.setEnabled(self.canvas.can_go_back)
        self._update_summary()

    def _update_summary(self) -> None:
        file_count = 0
        pending = [self.canvas.current_root]
        while pending:
            node = pending.pop()
            for child in node.children:
                if child.is_dir:
                    pending.append(child)
                elif isinstance(child, AggregateLeaf):
                    file_count += child.count
                else:
                    file_count += 1

        self.summary_label.setText(
            f"{file_count:,} files · {self.canvas._format_size(self.canvas.current_root.size)}"
        )

    def _rebuild_legend(self) -> None:
        self.legend_widget.setMinimumSize(0, 0)
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget() is not None:
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()

        directories = [
            child for child in self.canvas.current_root.children
            if child.is_dir and child.size > 0
        ]
        for directory in directories:
            color = self.canvas.color_for(directory)
            label = QPushButton(f"  {directory.name}  ")
            label.setToolTip(str(directory.path))
            label.setStyleSheet(
                f"background-color: {color.name()}; color: #101820; "
                "padding: 3px 2px; border-radius: 3px; border: 0px;"
            )
            label.clicked.connect(lambda checked=False, node=directory: self._open_directory(node))
            self.legend_layout.addWidget(label)

        if not directories:
            self.legend_layout.addWidget(QLabel("No non-empty parent directories"))
        self.legend_layout.addStretch(1)
        self.legend_layout.activate()
        widgets = [
            self.legend_layout.itemAt(index).widget()
            for index in range(self.legend_layout.count())
            if self.legend_layout.itemAt(index).widget() is not None
        ]
        content_width = 16 + sum(widget.sizeHint().width() for widget in widgets)
        content_width += max(0, len(widgets) - 1) * self.legend_layout.spacing()
        self.legend_widget.setMinimumSize(max(1, content_width), 40)
        self.legend_widget.resize(max(1, content_width), 40)
        self.legend_widget.updateGeometry()
        self.legend_scroll.ensureVisible(0, 0)

    def _open_directory(self, node: FileNode) -> None:
        if node.is_dir:
            node = prepare_display_root(node)
        self.canvas.open_directory(node)
        self._rebuild_legend()
        self._update_header()
        self.status_label.setText(f"Opened {node.name}")

    def _select_file(self, node: FileNode) -> None:
        self.status_label.setText(str(node.path))

    def start_scan(self, path: Path) -> None:
        if self._scan_thread is not None:
            return

        path = path.resolve()
        self.choose_button.setEnabled(False)
        self.back_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.path_label.setText(str(path))
        self.status_label.setText("Scanning... 0 files discovered")

        thread = QThread(self)
        worker = ScanWorker(path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._scan_progress)
        worker.finished.connect(self._scan_finished)
        worker.failed.connect(self._scan_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._scan_thread_finished)
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    def _scan_progress(self, count: int) -> None:
        self.status_label.setText(f"Scanning... {count:,} files discovered")

    def _scan_finished(self, root: FileNode) -> None:
        display_root = prepare_display_root(root)
        self.canvas.root = display_root
        self.canvas.current_root = display_root
        self.canvas._history.clear()
        self.canvas._selected = None
        self.canvas._rebuild_layout()
        self.canvas.update()
        self._rebuild_legend()
        self._update_header()
        self.status_label.setText(f"Scan complete: {root.size:,} bytes")
        self.progress_bar.setVisible(False)
        self.choose_button.setEnabled(True)

    def _scan_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Unable to scan folder", message)
        self.status_label.setText("Scan failed.")
        self.progress_bar.setVisible(False)
        self.choose_button.setEnabled(True)

    def _scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None

    def _go_back(self) -> None:
        self.canvas.go_back()
        self._rebuild_legend()
        self._update_header()
        self.status_label.setText("Returned to the parent directory.")

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Choose folder", str(self.canvas.current_root.path))
        if not selected:
            return
        self.start_scan(Path(selected))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Display a directory as a treemap")
    parser.add_argument("path", nargs="?", type=Path, help="directory to scan")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])

    path = args.path
    if path is None:
        selected = QFileDialog.getExistingDirectory(None, "Choose folder")
        if not selected:
            return 0
        path = Path(selected)

    window = TreemapWindow()
    window.show()
    window.start_scan(path)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
