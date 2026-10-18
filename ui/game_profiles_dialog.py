"""
NovaCare System Suite - Game Profiles & Auto-Boost Launcher Dialog
Allows users to manage game profiles, enable automatic game detection,
launch games with 1-click optimization, and scan installed libraries.
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QFrame, QMessageBox, QFileDialog, QAbstractItemView, QWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont
from core.game_booster import GameBooster, GameProfileManager, POPULAR_GAMES_DATABASE
from core.config import ConfigManager
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS,
    COLOR_WARNING, COLOR_DANGER, TEXT_PRIMARY, TEXT_SECONDARY
)

class GameProfilesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎮 Oyun Başlatıcı & Profil Yönetimi - NovaCare")
        self.resize(720, 540)
        self.setMinimumSize(640, 480)

        self.config = ConfigManager()
        self.game_booster = GameBooster()
        self.profile_mgr = GameProfileManager()

        self._init_ui()
        self._load_profiles()

        # Timer to update active running game indicator
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_active_status)
        self.status_timer.start(2500)
        self._update_active_status()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # 1. Header
        v_head = QVBoxLayout()
        v_head.setSpacing(4)
        lbl_title = QLabel("🎮  Oyun Başlatıcı & Otomatik Profil Yönetimi")
        lbl_title.setStyleSheet("font-size: 19px; font-weight: 800;")
        lbl_sub = QLabel(
            "Seçtiğiniz bir oyun açıldığında NovaCare otomatik olarak Oyun & Nihai Performans Moduna geçer;\n"
            "oyundan çıktığınızda ise sisteminizi standart güç ve servis durumuna geri döndürür."
        )
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.4;")
        lbl_sub.setWordWrap(True)
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)
        layout.addLayout(v_head)

        # 2. Master Automation Switch Card
        sw_card = QFrame()
        sw_card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(16, 185, 129, 0.08);
                border: 1px solid rgba(16, 185, 129, 0.28);
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        sw_layout = QHBoxLayout(sw_card)
        sw_layout.setContentsMargins(8, 6, 8, 6)

        self.chk_auto_boost = QCheckBox("⚡  Otomatik Oyun Algılama & Performans Kalkanı Aktif")
        self.chk_auto_boost.setChecked(self.config.get("auto_game_mode_enabled", True))
        self.chk_auto_boost.setCursor(Qt.PointingHandCursor)
        self.chk_auto_boost.setStyleSheet("font-weight: 700; font-size: 12.5px; color: #10B981;")
        self.chk_auto_boost.toggled.connect(self._on_auto_boost_toggled)
        sw_layout.addWidget(self.chk_auto_boost)
        sw_layout.addStretch()

        self.lbl_active_status = QLabel("⚪ Oyun bekleniyor...")
        self.lbl_active_status.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #94A3B8;")
        sw_layout.addWidget(self.lbl_active_status)
        layout.addWidget(sw_card)

        # 3. Action Toolbar (Add game & auto-scan)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        btn_add = QPushButton("➕  Özel Oyun Ekle (.exe)")
        btn_add.setProperty("class", "primary-btn")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._on_add_game_clicked)
        toolbar.addWidget(btn_add)

        btn_scan = QPushButton("🔍  Yüklü Oyunları Otomatik Tara")
        btn_scan.setProperty("class", "secondary-btn")
        btn_scan.setCursor(Qt.PointingHandCursor)
        btn_scan.clicked.connect(self._on_scan_games_clicked)
        toolbar.addWidget(btn_scan)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 4. Games Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Oyun Adı", "Çalıştırılabilir Dosya (.exe)", "Oto-Hızlandırma", "İşlemler"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                border-radius: 8px;
            }
            QHeaderView::section {
                font-weight: 700;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.table)

        # 5. Bottom Close Button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Kapat")
        btn_close.setProperty("class", "secondary-btn")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _on_auto_boost_toggled(self, checked: bool):
        self.config.set("auto_game_mode_enabled", checked)
        self._update_active_status()

    def _update_active_status(self):
        if not self.config.get("auto_game_mode_enabled", True):
            self.lbl_active_status.setText("⏸️ Otomatik Algılama Devre Dışı")
            self.lbl_active_status.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #F59E0B;")
            return

        if self.game_booster.is_active():
            self.lbl_active_status.setText("🎮 Oyun Modu Aktif (Nihai Güç Planı)")
            self.lbl_active_status.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #10B981;")
        else:
            self.lbl_active_status.setText("⚪ Oyun Bekleniyor (Arka Plan Nöbette)")
            self.lbl_active_status.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #94A3B8;")

    def _load_profiles(self):
        profiles = self.profile_mgr.get_profiles()
        self.table.setRowCount(len(profiles))

        for row, p in enumerate(profiles):
            # 0. Name
            item_name = QTableWidgetItem(f"🎮  {p.get('name', 'Bilinmeyen Oyun')}")
            item_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(row, 0, item_name)

            # 1. Executable
            item_exe = QTableWidgetItem(p.get("exe", ""))
            item_exe.setTextAlignment(Qt.AlignCenter)
            item_exe.setForeground(Qt.cyan)
            self.table.setItem(row, 1, item_exe)

            # 2. Auto-boost Checkbox Widget
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            chk_lay.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(p.get("auto_boost", True))
            chk.setCursor(Qt.PointingHandCursor)
            chk.toggled.connect(lambda state, pid=p.get("id"): self.profile_mgr.toggle_profile_boost(pid, state))
            chk_lay.addWidget(chk)
            self.table.setCellWidget(row, 2, chk_widget)

            # 3. Actions (Launch & Delete)
            act_widget = QWidget()
            act_lay = QHBoxLayout(act_widget)
            act_lay.setContentsMargins(4, 2, 4, 2)
            act_lay.setSpacing(6)

            btn_launch = QPushButton("🚀")
            btn_launch.setToolTip("Oyunu Başlat & Oyun Moduna Geç")
            btn_launch.setFixedSize(28, 26)
            btn_launch.setCursor(Qt.PointingHandCursor)
            btn_launch.setStyleSheet("background-color: #0284C7; color: white; border-radius: 4px; font-size: 12px;")
            btn_launch.clicked.connect(lambda _, path=p.get("path"), exe=p.get("exe"): self._launch_game(path, exe))
            act_lay.addWidget(btn_launch)

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Profili Listeden Sil")
            btn_del.setFixedSize(28, 26)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("background-color: #DC2626; color: white; border-radius: 4px; font-size: 11px;")
            btn_del.clicked.connect(lambda _, pid=p.get("id"): self._delete_profile(pid))
            act_lay.addWidget(btn_del)

            self.table.setCellWidget(row, 3, act_widget)
            self.table.setRowHeight(row, 36)

    def _on_add_game_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Oyun Yürütülebilir Dosyasını (.exe) Seçin",
            "",
            "Çalıştırılabilir Dosyalar (*.exe)"
        )
        if path:
            filename = os.path.basename(path)
            # Infer game name cleanly from filename
            name_stem = os.path.splitext(filename)[0].replace("-", " ").replace("_", " ").title()
            self.profile_mgr.add_profile(name=name_stem, exe=filename, path=path, auto_boost=True)
            self._load_profiles()
            QMessageBox.information(
                self,
                "Oyun Eklendi",
                f"'{name_stem}' ({filename}) başarıyla profil listenize eklendi!\n\n"
                "Bu oyunu açtığınızda NovaCare otomatik olarak Oyun Modu'na geçecektir."
            )

    def _on_scan_games_clicked(self):
        found = self.profile_mgr.scan_installed_games()
        if not found:
            QMessageBox.information(
                self,
                "Tarama Tamamlandı",
                "Sisteminizdeki standart Steam / Epic / Riot dizinlerinde yeni bir oyun bulunamadı.\n\n"
                "'Özel Oyun Ekle' butonunu kullanarak dilediğiniz herhangi bir .exe dosyasını ekleyebilirsiniz."
            )
            return

        added_cnt = 0
        existing_exes = {p.get("exe", "").lower() for p in self.profile_mgr.get_profiles()}
        for g in found:
            if g.get("exe", "").lower() not in existing_exes:
                self.profile_mgr.add_profile(name=g.get("name"), exe=g.get("exe"), path=g.get("path"), auto_boost=True)
                existing_exes.add(g.get("exe", "").lower())
                added_cnt += 1

        self._load_profiles()
        QMessageBox.information(
            self,
            "Tarama Başarılı",
            f"Sisteminiz taranarak {len(found)} adet oyun tespit edildi.\n"
            f"{added_cnt} yeni oyun profili listenize otomatik olarak dahil edildi!"
        )

    def _delete_profile(self, profile_id: str):
        if self.profile_mgr.remove_profile(profile_id):
            self._load_profiles()

    def _launch_game(self, path: str, exe: str):
        if not self.game_booster.is_active():
            self.game_booster.activate()

        if path and os.path.exists(path):
            try:
                os.startfile(path)
                QMessageBox.information(
                    self,
                    "Oyun Başlatıldı",
                    f"'{exe}' çalıştırıldı ve NovaCare Oyun Modu etkinleştirildi!"
                )
                return
            except Exception as e:
                QMessageBox.warning(self, "Başlatma Hatası", f"Oyun başlatılamadı: {e}")
        else:
            QMessageBox.information(
                self,
                "Oyun Modu Etkinleştirildi",
                f"Oyun Modu devreye alındı. Lütfen '{exe}' oyununu kendi başlatıcısından açınız."
            )
