import sys, os
import mmap
from concurrent.futures import ThreadPoolExecutor
import fitz  # PyMuPDF for preview
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QMessageBox, QAbstractItemView
)
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import Qt, QSize
from PyPDF2 import PdfReader, PdfWriter
import pikepdf  # faster, C‑based PDF merging

class PDFTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Toolkit")
        self.setGeometry(150, 150, 2000, 1400)
        self.current_pdf = None
        self.init_ui()

    def init_ui(self):
        tabs = QTabWidget()
        combine_tab = QWidget()
        split_tab   = QWidget()
        tabs.addTab(combine_tab, "Combine PDFs")
        tabs.addTab(split_tab,   "Split/Remove Pages")

        # Combine tab
        c_layout = QVBoxLayout()
        self.combo_list = QListWidget()
        btn_layout = QHBoxLayout()
        for name, handler in [
            ("➕ Add PDFs",        self.add_pdfs),
            ("❌ Remove Selected", self.remove_selected),
            ("⬆️ Move Up",         self.move_up),
            ("⬇️ Move Down",       self.move_down),
        ]:
            btn = QPushButton(name)
            btn.clicked.connect(handler)
            btn_layout.addWidget(btn)
        combine_btn = QPushButton("📄 Combine & Save As…")
        combine_btn.clicked.connect(self.combine_pdfs)
        c_layout.addWidget(self.combo_list)
        c_layout.addLayout(btn_layout)
        c_layout.addWidget(combine_btn)
        combine_tab.setLayout(c_layout)

        # Split tab
        s_layout = QVBoxLayout()
        select_btn = QPushButton("📂 Select PDF")
        select_btn.clicked.connect(self.select_pdf)
        self.selected_label = QLabel("No PDF selected.")
        self.preview_list = QListWidget()
        self.preview_list.setViewMode(QListWidget.IconMode)
        self.preview_list.setIconSize(QSize(200, 260))
        self.preview_list.setResizeMode(QListWidget.Adjust)
        # allow shift‑click range selection
        self.preview_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        remove_btn  = QPushButton("✂️ Remove Selected & Save As…")
        remove_btn.clicked.connect(self.split_pdf)

        s_layout.addWidget(select_btn)
        s_layout.addWidget(self.selected_label)
        s_layout.addWidget(self.preview_list, stretch=1)
        s_layout.addWidget(remove_btn)
        split_tab.setLayout(s_layout)

        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(tabs)
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def add_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF Files (*.pdf)")
        for f in files:
            if not any(self.combo_list.item(i).text() == f for i in range(self.combo_list.count())):
                self.combo_list.addItem(f)

    def remove_selected(self):
        for it in self.combo_list.selectedItems():
            self.combo_list.takeItem(self.combo_list.row(it))

    def move_up(self):
        r = self.combo_list.currentRow()
        if r > 0:
            item = self.combo_list.takeItem(r)
            self.combo_list.insertItem(r-1, item)
            self.combo_list.setCurrentRow(r-1)

    def move_down(self):
        r = self.combo_list.currentRow()
        if 0 <= r < self.combo_list.count() - 1:
            item = self.combo_list.takeItem(r)
            self.combo_list.insertItem(r + 1, item)
            self.combo_list.setCurrentRow(r + 1)

    def combine_pdfs(self):
        count = self.combo_list.count()
        if count < 2:
            QMessageBox.warning(self, "Warning", "Need at least two PDFs.")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Combined PDF As", "combined.pdf", "PDF Files (*.pdf)")
        if not save_path:
            return
        try:
            merger = pikepdf.Pdf.new()
            for i in range(count):
                path = self.combo_list.item(i).text()
                with open(path, "rb") as f:
                    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                    src = pikepdf.Pdf.open(mm)
                merger.pages.extend(src.pages)
            merger.save(save_path)
            QMessageBox.information(self, "Saved", f"Combined PDF →\n{save_path}")
        except Exception:
            writer = PdfWriter()
            for i in range(count):
                path = self.combo_list.item(i).text()
                reader = PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
            with open(save_path, "wb") as out:
                writer.write(out)
            QMessageBox.information(self, "Saved (PyPDF2)", f"Combined PDF →\n{save_path}")

    def select_pdf(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select PDF to Split", "", "PDF Files (*.pdf)")
        if not file:
            return
        self.current_pdf = file
        self.selected_label.setText(f"Selected: {os.path.basename(file)}")
        self.preview_list.clear()
        try:
            doc = fitz.open(file)
            def render_page(i):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
                return i, pix
            with ThreadPoolExecutor() as executor:
                for i, pix in executor.map(render_page, range(len(doc))):
                    img_data = pix.tobytes("ppm")
                    img = QImage.fromData(img_data)
                    icon = QIcon(QPixmap.fromImage(img))
                    item = QListWidgetItem(icon, f"{i+1}")
                    item.setData(Qt.UserRole, i+1)
                    self.preview_list.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Preview failed:\n{e}")

    def split_pdf(self):
        if not self.current_pdf:
            QMessageBox.warning(self, "Warning", "No PDF selected.")
            return
        selected = self.preview_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Select pages to remove.")
            return
        to_remove = {item.data(Qt.UserRole) for item in selected}
        reader = PdfReader(self.current_pdf)
        writer = PdfWriter()
        for i, page in enumerate(reader.pages, start=1):
            if i not in to_remove:
                writer.add_page(page)
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Split PDF As", "edited.pdf", "PDF Files (*.pdf)")
        if save_path:
            with open(save_path, 'wb') as out:
                writer.write(out)
            QMessageBox.information(self, "Saved", f"Edited PDF →\n{save_path}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("""
        QWidget { background: #2b2b2b; color: #eee; font: 10pt 'Segoe UI'; }
        QPushButton { background: #3c3f41; border: none; padding: 6px; border-radius: 4px; }
        QPushButton:hover { background: #4b4f51; }
        QListWidget, QLabel { background: #313335; border: 1px solid #444; }
        QTabBar::tab { background: #3c3f41; padding: 8px; }
        QTabBar::tab:selected { background: #292d2e; }
        QTabWidget::pane { border: 1px solid #444; }
    """)
    window = PDFTool()
    window.show()
    sys.exit(app.exec_())
