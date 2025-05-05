import sys, os, fitz, mmap
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QLabel, QVBoxLayout,
    QHBoxLayout, QMessageBox, QAbstractItemView, QScrollArea,
    QLineEdit, QToolButton, QStyle, QDesktopWidget
)
from PyQt5.QtGui import QPixmap, QImage, QTransform, QIcon, QPainter
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyPDF2 import PdfReader, PdfWriter

class PDFTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Toolkit")
        geom = QDesktopWidget().availableGeometry()
        w, h = int(geom.width()*0.75), int(geom.height()*0.75)
        self.setGeometry((geom.width()-w)//2, (geom.height()-h)//2, w, h)
        self.scale, self.rotation = 1.28, 0
        self.current_pdf = None
        self.page_containers = []
        self._split_gen = None
        self._view_gen = None
        self.viewer_doc = None
        self.init_ui()

    def init_ui(self):
        tabs = QTabWidget()

        combine_tab = QWidget()
        c_main = QHBoxLayout(combine_tab)
        self.combine_preview = QListWidget()
        self.combine_preview.setViewMode(QListWidget.IconMode)
        self.combine_preview.setIconSize(QSize(400, 560))
        self.combine_preview.setResizeMode(QListWidget.Adjust)
        self.combine_preview.setSelectionMode(QAbstractItemView.NoSelection)
        self.combine_preview.setFlow(QListWidget.TopToBottom)
        self.combine_preview.setWrapping(False)
        c_main.addWidget(self.combine_preview, 1)

        c_layout = QVBoxLayout()
        self.combo_list = QListWidget()
        self.combo_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        bl = QHBoxLayout()
        for t, f in [("➕ Add", self.add_items),
                     ("❌ Remove", self.remove_selected),
                     ("⬆️ Up", self.move_up),
                     ("⬇️ Down", self.move_down),
                     ("🔀 Reverse", self.reverse_order)]:
            b = QPushButton(t); b.clicked.connect(f); bl.addWidget(b)
        combine_btn = QPushButton("📄 Combine & Save As…")
        combine_btn.clicked.connect(self.combine_pdfs)
        c_layout.addWidget(self.combo_list)
        c_layout.addLayout(bl)
        c_layout.addWidget(combine_btn)
        c_main.addLayout(c_layout, 4)
        tabs.addTab(combine_tab, "Combine")

        split_tab = QWidget()
        s_layout = QVBoxLayout(split_tab)
        sel = QPushButton("📂 Select PDF"); sel.clicked.connect(self.select_pdf)
        self.selected_label = QLabel("No PDF selected.")
        self.preview_list = QListWidget()
        self.preview_list.setViewMode(QListWidget.IconMode)
        self.preview_list.setIconSize(QSize(400, 520))
        self.preview_list.setResizeMode(QListWidget.Adjust)
        self.preview_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        rem = QPushButton("✂️ Remove & Save"); rem.clicked.connect(self.split_pdf)
        s_layout.addWidget(sel)
        s_layout.addWidget(self.selected_label)
        s_layout.addWidget(self.preview_list, 1)
        s_layout.addWidget(rem)
        tabs.addTab(split_tab, "Split/Remove")

        viewer_tab = QWidget()
        v_layout = QVBoxLayout(viewer_tab)
        nav = QHBoxLayout()
        nav.addStretch()
        self.page_label = QLabel("Page 0/0"); self.page_label.setAlignment(Qt.AlignCenter)
        self.page_input = QLineEdit(); self.page_input.setFixedWidth(60)
        self.page_input.returnPressed.connect(self.go_to_page)
        nav.addWidget(self.page_label); nav.addWidget(self.page_input); nav.addStretch()
        v_layout.addLayout(nav)

        tl = QHBoxLayout()
        for txt, fn in [
            ("📂 Open PDF", self.open_pdf_viewer),
            ("🖨️ Print", self.print_pdf),
            ("🔍+", self.zoom_in),
            ("🔍-", self.zoom_out)
        ]:
            b = QPushButton(txt); b.clicked.connect(fn); tl.addWidget(b)
        zl = QLabel("Zoom:")
        zl.setStyleSheet("background: #3c3f41; border: none; padding: 6px; border-radius: 4px;")
        tl.addWidget(zl)
        self.zoom_input = QLineEdit(str(int(self.scale*100))); self.zoom_input.setFixedWidth(50)
        self.zoom_input.returnPressed.connect(lambda: self.set_zoom(self.zoom_input.text()))
        tl.addWidget(self.zoom_input)
        rt = QToolButton(); rt.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        rt.clicked.connect(self.rotate); tl.addWidget(rt)
        v_layout.addLayout(tl)

        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True)
        self.pages_widget = QWidget(); self.pages_layout = QVBoxLayout(self.pages_widget)
        self.pages_layout.setContentsMargins(0, 0, 0, 0); self.pages_layout.setSpacing(0)
        self.scroll_area.setWidget(self.pages_widget)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_current_page)
        v_layout.addWidget(self.scroll_area, 1)
        tabs.addTab(viewer_tab, "Viewer")

        main = QWidget(); ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0); ml.addWidget(tabs)
        self.setCentralWidget(main)

    def add_items(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs/Images", "",
            "PDF (*.pdf);;Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        for f in files:
            if not any(self.combo_list.item(i).text() == f for i in range(self.combo_list.count())):
                self.combo_list.addItem(f)
        self.load_combine_previews()

    def load_combine_previews(self):
        self.combine_preview.clear()
        files = [self.combo_list.item(i).text() for i in range(self.combo_list.count())]
        def gen():
            count = 1
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext == ".pdf":
                    doc = fitz.open(f)
                    for p in range(doc.page_count):
                        pix = doc.load_page(p).get_pixmap(matrix=fitz.Matrix(0.8,0.8))
                        yield QIcon(QPixmap.fromImage(QImage.fromData(pix.tobytes("ppm")))), str(count)
                        count += 1
                else:
                    img = QImage(f).scaled(400, 560, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    yield QIcon(QPixmap.fromImage(img)), str(count)
                    count += 1
        self._gen = gen(); QTimer.singleShot(0, self._load_next)

    def _load_next(self):
        try:
            icon, text = next(self._gen)
            self.combine_preview.addItem(QListWidgetItem(icon, text))
            QTimer.singleShot(0, self._load_next)
        except StopIteration:
            pass

    def remove_selected(self):
        for it in self.combo_list.selectedItems():
            self.combo_list.takeItem(self.combo_list.row(it))
        self.load_combine_previews()

    def move_up(self):
        r = self.combo_list.currentRow()
        if r > 0:
            item = self.combo_list.takeItem(r)
            self.combo_list.insertItem(r-1, item)
            self.combo_list.setCurrentRow(r-1)
        self.load_combine_previews()

    def move_down(self):
        r = self.combo_list.currentRow()
        if 0 <= r < self.combo_list.count()-1:
            item = self.combo_list.takeItem(r)
            self.combo_list.insertItem(r+1, item)
            self.combo_list.setCurrentRow(r+1)
        self.load_combine_previews()

    def reverse_order(self):
        paths = [self.combo_list.item(i).text() for i in range(self.combo_list.count())]
        self.combo_list.clear()
        for p in reversed(paths):
            self.combo_list.addItem(p)
        self.load_combine_previews()

    def combine_pdfs(self):
        if self.combo_list.count() < 1:
            QMessageBox.warning(self, "Warning", "Add at least one item.")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save As", "combined.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
        if not save_path.lower().endswith('.pdf'):
            save_path += '.pdf'
        try:
            doc = fitz.open()
            for f in [self.combo_list.item(i).text() for i in range(self.combo_list.count())]:
                if os.path.splitext(f)[1].lower() == ".pdf":
                    doc.insert_pdf(fitz.open(f))
                else:
                    pix = fitz.Pixmap(f)
                    page = doc.new_page(width=pix.width, height=pix.height)
                    page.insert_image(page.rect, filename=f)
            doc.save(save_path)
            QMessageBox.information(self, "Saved", save_path)
        except Exception as e:
            QMessageBox.critical(self, "Error Saving PDF", str(e))

    def select_pdf(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF to Split", "", "PDF Files (*.pdf)")
        if not file:
            return
        self.current_pdf = file
        self.selected_label.setText(os.path.basename(file))
        self.preview_list.clear()
        doc = fitz.open(file)
        def gen():
            for i in range(doc.page_count):
                pix = doc.load_page(i).get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                yield QIcon(QPixmap.fromImage(QImage.fromData(pix.tobytes("ppm")))), str(i+1), i+1
        self._split_gen = gen(); QTimer.singleShot(0, self._load_split)

    def _load_split(self):
        try:
            icon, text, num = next(self._split_gen)
            item = QListWidgetItem(icon, text)
            item.setData(Qt.UserRole, num)
            self.preview_list.addItem(item)
            QTimer.singleShot(0, self._load_split)
        except StopIteration:
            pass

    def split_pdf(self):
        if not self.current_pdf:
            return
        rem = {it.data(Qt.UserRole) for it in self.preview_list.selectedItems()}
        reader = PdfReader(self.current_pdf)
        writer = PdfWriter()
        for i, p in enumerate(reader.pages, 1):
            if i not in rem:
                writer.add_page(p)
        save_path, _ = QFileDialog.getSaveFileName(self, "Save As", "edited.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
        if not save_path.lower().endswith('.pdf'):
            save_path += '.pdf'
        try:
            with open(save_path, 'wb') as o:
                writer.write(o)
            QMessageBox.information(self, "Saved", save_path)
        except Exception as e:
            QMessageBox.critical(self, "Error Saving PDF", str(e))

    def open_pdf_viewer(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if not file:
            return
        self.current_pdf = file
        self.clear_pages()
        self.viewer_doc = fitz.open(file)
        self._view_gen = self._gen_view()
        QTimer.singleShot(0, self._load_view)

    def _gen_view(self):
        for i in range(self.viewer_doc.page_count):
            pix = self.viewer_doc.load_page(i).get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
            yield pix, i+1

    def _load_view(self):
        try:
            pix, num = next(self._view_gen)
            img = QImage.fromData(pix.tobytes("ppm"))
            pm = QPixmap.fromImage(img).transformed(QTransform().rotate(self.rotation))
            lbl = QLabel(); lbl.setAlignment(Qt.AlignCenter); lbl.setPixmap(pm)
            c = QWidget(); l = QVBoxLayout(c); l.setContentsMargins(0,10,0,10); l.addWidget(lbl)
            self.pages_layout.addWidget(c); self.page_containers.append(c)
            QTimer.singleShot(0, self._load_view)
        except StopIteration:
            self.page_label.setText(f"Page 1/{self.viewer_doc.page_count}")

    def print_pdf(self):
        if not self.current_pdf:
            return
        printer = QPrinter(); dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            for i in range(self.viewer_doc.page_count):
                page = self.viewer_doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
                img = QImage.fromData(pix.tobytes("ppm"))
                pm = QPixmap.fromImage(img).transformed(QTransform().rotate(self.rotation))
                painter.drawPixmap(0, 0, pm.scaled(printer.pageRect().size(), Qt.KeepAspectRatio))
                if i < self.viewer_doc.page_count - 1:
                    printer.newPage()
            painter.end()

    def clear_pages(self):
        while self.pages_layout.count():
            w = self.pages_layout.takeAt(0).widget()
            if w:
                w.setParent(None)
        self.page_containers.clear()

    def refresh_view(self):
        if not self.viewer_doc:
            return
        self.clear_pages()
        self._view_gen = self._gen_view()
        QTimer.singleShot(0, self._load_view)

    def go_to_page(self):
        try:
            p = int(self.page_input.text())
            tot = self.viewer_doc.page_count
            if 1 <= p <= tot:
                y = self.page_containers[p-1].pos().y()
                self.scroll_area.verticalScrollBar().setValue(y)
                self.page_label.setText(f"Page {p}/{tot}")
        except:
            pass

    def zoom_in(self):
        self.scale *= 1.25
        self.zoom_input.setText(str(int(self.scale*100)))
        self.refresh_view()

    def zoom_out(self):
        self.scale /= 1.25
        self.zoom_input.setText(str(int(self.scale*100)))
        self.refresh_view()

    def set_zoom(self, t):
        try:
            self.scale = float(t)/100
            self.zoom_input.setText(str(int(self.scale*100)))
            self.refresh_view()
        except:
            pass

    def rotate(self):
        self.rotation = (self.rotation + 90) % 360
        self.refresh_view()

    def update_current_page(self, val):
        pg = 1
        for i, c in enumerate(self.page_containers):
            if c.pos().y() <= val:
                pg = i + 1
            else:
                break
        self.page_label.setText(f"Page {pg}/{self.viewer_doc.page_count}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("""
        QWidget { background: #2b2b2b; color: #eee; font: 10pt 'Segoe UI'; }
        QPushButton { background: #3c3f41; border: none; padding: 6px; border-radius: 4px; }
        QPushButton:hover { background: #4b4f51; }
    """)
    win = PDFTool()
    win.show()
    sys.exit(app.exec_())
