# NovaCare System Care Suite 2026 ⚡

<p align="center">
  <img src="assets/icon.png" width="128" height="128" alt="NovaCare Logo">
  <br>
  <strong>Gelişmiş Windows Sistem Bakım, Hızlandırma, Güvenlik ve Optimizasyon Paketi</strong>
  <br><br>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-v1.0.1-00D2FF.svg?style=flat-square" alt="Version"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-10B981.svg?style=flat-square" alt="Python"></a>
  <a href="https://www.microsoft.com/windows"><img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D4.svg?style=flat-square" alt="Platform"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-F59E0B.svg?style=flat-square" alt="License"></a>
</p>

---

## 📥 İndirme ve Hızlı Kurulum

Python veya herhangi bir ek kütüphane yüklemenize gerek kalmadan doğrudan derlenmiş bağımsız Windows sürümlerini [**GitHub Releases**](https://github.com/GurpinarSG/NovaCare/releases) sayfasından edinebilirsiniz:

| Paket Türü | İndirme Bağlantısı | Açıklama |
| :--- | :--- | :--- |
| 🚀 **Kurulum Sihirbazı (Önerilen)** | [**NovaCare_Setup_v1.0.1.exe**](https://github.com/GurpinarSG/NovaCare/releases/latest) | Otomatik kısayollar, başlangıç entegrasyonu ve Denetim Masası kaldırma desteği sunan modern kurulum sihirbazı. |
| 📦 **Taşınabilir Sürüm (Portable)** | [**NovaCare_v1.0.1_Portable.zip**](https://github.com/GurpinarSG/NovaCare/releases/latest) | Kurulum gerektirmez; USB bellekten veya istediğiniz klasörden doğrudan çalışır. |

---

## 🌟 Öne Çıkan Modüller ve Özellikler

### 1. 🚀 Tek Tıkla Bakım (1-Click Maintenance & Dashboard)
* **Dinamik Sağlık Skoru:** 0-100 arasında bilgisayarınızın genel sağlık durumunu anlık analiz eden dairesel gösterge.
* **1-Tıkla Tarama & Onarım:** Gereksiz dosyalar, bozuk kayıt defteri anahtarları, gizlilik izleri ve başlangıç programları tek seferde taranıp temizlenir.
* **Canlı Metrikler:** CPU ve RAM yükü donanımsal olarak anlık izlenir.

### 2. 🧹 Gereksiz Dosya ve Önbellek Temizleyici (Junk Cleaner)
* **Kullanıcı & Sistem Temp:** `%TEMP%` ve `C:\Windows\Temp` dizinlerindeki geçici dosyaları güvenle temizler.
* **Geri Dönüşüm Kutusu:** Windows Geri Dönüşüm Kutusunu sessizce boşaltır.
* **Windows Update İndirme Önbelleği:** Güncellemelerden sonra diskte kalan eski kurulum paketlerini siler.
* **Hata Raporları & Dump Dosyaları:** Minidump ve WER hata günlüklerini temizler.
* **Web Tarayıcıları:** Google Chrome, Microsoft Edge, Brave, Mozilla Firefox, Opera ve Vivaldi önbellek ve çerezlerini temizler.
* **Geliştirici Önbellekleri:** Discord, Spotify, pip ve npm önbelleklerini temizler.

### 3. 🛠️ Kayıt Defteri Temizleyici ve Onarıcı (Registry Cleaner)
* **Güvenli Tarama:** Geçersiz başlangıç girdileri, silinmiş program kalıntıları, kayıp paylaşılan DLL'ler ve bozuk MUI Cache kayıtlarını denetler.
* **Otomatik Geri Alma Yedeği:** Her onarım işleminden önce otomatik olarak hem `.json` hem de yerel Windows `.reg` dosyası oluşturur.

### 4. ⚡ Başlangıç Yöneticisi (Startup Optimizer)
* Windows açılışında başlayan programları (Kayıt Defteri Run/RunOnce ve Başlangıç Klasörleri) listeler.
* **Açılış Etkisi Puanlaması:** Programların sistem açılışına etkisini *Yüksek*, *Orta* veya *Düşük* olarak sınıflandırır.
* **Tek Tuşla Aç/Kapat:** Girişleri silmeden geçici olarak devre dışı bırakabilme desteği.

### 5. 📦 Program ve Artık Dosya Kaldırıcı (App Uninstaller)
* Yüklü 32-bit ve 64-bit tüm yazılımları listeler (Boyut, sürüm, yayıncı bilgisi).
* **Derin Artık Temizliği (Leftover Cleaner):** Program kaldırıldıktan sonra Program Files, AppData ve Kayıt Defteri'nde unuttuğu kalıntıları bulur ve temizler.

### 6. 🧠 Bellek (RAM) Hızlandırıcı ve Süreç Yöneticisi (RAM Booster)
* **Canlı Bellek Grafikleri:** Fiziksel ve sanal bellek kullanımını gerçek zamanlı gösterir.
* **RAM'i Hızlandır & Boşalt:** Windows `EmptyWorkingSet` API'si aracılığıyla arka plandaki tüm süreçlerin gereksiz çalışma kümelerini boşaltıp gigabaytlarca RAM'i anında geri kazandırır.
* **Süreç Yöneticisi:** Çalışan işlemleri PID, bellek ve CPU kullanımına göre listeleyip sonlandırma imkanı tanır.

### 7. 📊 Disk Alanı ve Büyük Dosya Analizörü (Disk Analyzer)
* Sürücü doluluk oranlarını görselleştirir (C:, D:, vb.).
* Diski dolduran en büyük dosyaları (Video, Arşiv, ISO, Kurulum vb.) kategorilerine göre listeler ve dosya konumunu açma/silme seçenekleri sunar.

### 8. 🛡️ Gizlilik Kalkanı ve Windows Optimizasyonu (Privacy Shield)
* **Etkinlik İzleri:** Son açılan dosyalar, Çalıştır (Win+R) geçmişi, Dosya Gezgini adres geçmişi ve Pano belleğini temizler.
* **Windows 10/11 İyileştirmeleri:** Telemetri ve tanılama verisi toplama, reklam kimliği, etkinlik geçmişi, Başlat menüsü Bing aramaları ve Game DVR'ı tek tıkla kapatabilme.

### 9. 🌐 Ağ & DNS Hızlandırma (Network Optimizer)
* Ağ adaptörlerini listeler, TCP/IP ve Winsock yığınını sıfırlar.
* Google DNS, Cloudflare, Quad9, OpenDNS arasında gecikme (ping) testi yaparak en hızlı DNS'e tek tıkla geçiş sağlar.

### 10. 💾 Kurtarma ve Yedekleme Merkezi (Rescue Center)
* Temizlik işlemlerinde alınan kayıt defteri yedeklerini listeler ve tek tıkla geri yükler.
* Windows Sistem Geri Yükleme Noktası (System Restore Point) oluşturma desteği sunar.

### 11. 🔄 GitHub Otomatik ve Manuel Güncelleme Sistemi (Updater)
* **Manuel & Otomatik Güncelleme:** GitHub Releases API veya Branch Commit takibi ile yeni sürümleri arka planda denetler.
* **Tek Tıkla Kurulum:** Yeni sürüm paketini indirip arka planda güvenle günceller.
* **Windows DPAPI Şifreleme:** GitHub API anahtarlarını Windows'un yerel şifreleme altyapısıyla güvenle saklar.

---

## 🛠️ Kaynak Koddan Çalıştırma (Geliştiriciler İçin)

Eğer projeyi kaynak koddan çalıştırmak veya geliştirmek isterseniz:

### 1. Depoyu Klonlayın:
```powershell
git clone https://github.com/GurpinarSG/NovaCare.git
cd NovaCare
```

### 2. Bağımlılıkları Yükleyin:
```powershell
pip install -r requirements.txt
```

### 3. Uygulamayı Başlatın:
```powershell
python main.py
```
*(Arka planda konsolsuz başlatmak için: `pythonw main.py`)*

---

## 💻 Komut Satırı (CLI) Kısayolları

NovaCare, grafik arayüz açılmadan doğrudan komut satırından da çalıştırılabilir:

* **Hızlı RAM Temizleme:**
  ```powershell
  python main.py --boost-ram
  ```
* **Hızlı Gereksiz Dosya Taraması:**
  ```powershell
  python main.py --quick-scan
  ```
* **GitHub Güncelleştirmelerini Denetleme:**
  ```powershell
  python main.py --check-update
  ```
* **Uygulamayı Kaldırma:**
  ```powershell
  NovaCare.exe --uninstall
  ```

---

## 📦 Kendi EXE / Setup Dosyanızı Derleme

Projeyi tek dosya bağımsız `.exe` veya modern kurulum paketi olarak derlemek için:

```powershell
# 1. Geliştirici bağımlılıklarını yükleyin
pip install -r requirements-dev.txt

# 2. Ana çalıştırılabilir dosyayı derleyin (NovaCare.exe)
python scripts/build_exe.py

# 3. Modern kurulum sihirbazını derleyin (NovaCare_Setup.exe)
python scripts/build_installer.py
```

---

## 📂 Proje Dizin Yapısı

```
NovaCare/
├── assets/                  # İkonlar, logolar ve grafik kaynakları
├── core/                    # Çekirdek optimizasyon ve temizlik motorları
│   ├── auto_cleaner.py      # Zamanlanmış otomatik temizlik motoru
│   ├── autostart.py         # Windows başlangıç kayıt yöneticisi
│   ├── backup_manager.py    # Kayıt defteri yedekleme ve geri yükleme
│   ├── bloatware_cleaner.py # Windows yerleşik gereksiz uygulama kaldırıcı
│   ├── config.py            # Ayarlar ve sürüm yöneticisi
│   ├── disk_analyzer.py     # Disk alanı ve büyük dosya tarayıcı
│   ├── game_booster.py      # Oyun ve yüksek performans modu
│   ├── hardware_monitor.py  # Donanım, CPU ve GPU izleme
│   ├── junk_cleaner.py      # Geçici ve çöp dosya temizleme motoru
│   ├── memory_booster.py    # RAM optimizasyonu ve süreç yönetimi
│   ├── network_optimizer.py # Ağ ve DNS optimize edici
│   ├── privacy_tweaker.py   # Windows telemetri ve gizlilik kalkanı
│   ├── registry_cleaner.py  # Kayıt defteri tarayıcı ve onarıcı
│   ├── security.py          # DPAPI belirteç şifreleme ve maskeleme
│   ├── startup_manager.py   # Başlangıç uygulamaları yöneticisi
│   ├── uninstaller.py       # Program kaldırıcı ve artık dosya temizliği
│   ├── updater.py           # GitHub otomatik ve manuel güncelleme motoru
│   └── utils.py             # Yardımcı araçlar ve yönetici denetimleri
├── scripts/                 # Paketleme ve dağıtım araçları
│   ├── build_exe.py         # NovaCare.exe PyInstaller derleyicisi
│   ├── build_installer.py   # NovaCare_Setup.exe derleyicisi
│   ├── installer_wizard.py  # Modern kurulum sihirbazı arayüzü
│   └── publish_release.py   # GitHub sürüm ve kod yayınlama aracı
├── ui/                      # PyQt5 kullanıcı arayüzü ve bileşenleri
│   ├── components.py        # Özel kartlar, başlıklar ve göstergeler
│   ├── main_window.py       # Ana uygulama penceresi ve gezinti çubuğu
│   ├── styles.py            # Koyu tema renk paleti ve QSS stilleri
│   └── views/               # 11 ana modülün arayüz görünümleri
├── app.manifest             # Windows DPI & UAC yönetici bildirim dosyası
├── CHANGELOG.md             # Sürüm güncelleme notları
├── LICENSE                  # MIT Lisansı
├── main.py                  # Uygulama ana giriş noktası
├── README.md                # Proje dokümantasyonu
├── requirements.txt         # Çalışma zamanı bağımlılıkları
├── requirements-dev.txt     # Derleme ve geliştirici bağımlılıkları
└── VERSION                  # Güncel sürüm numarası (1.0.1)
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) altında dağıtılmaktadır. Ticari ve kişisel amaçlarla özgürce kullanılabilir, değiştirilebilir ve dağıtılabilir.
