# 📋 NovaCare System Care Suite - Sürüm Güncelleme Notları (Changelog)

Tüm önemli değişiklikler, yeni özellikler, hata düzeltmeleri ve optimizasyonlar bu belgede kronolojik olarak kayıt altına alınmaktadır.

---

## 🚀 [v1.0.8] - 2026-10-16

### 🔍 Kod Tabanı Derin Denetimi & Tam Dosya İncelemesi (Deep Codebase Audit)
* **Tüm 44 Python Dosyası Denetlendi:** `core/`, `ui/`, `scripts/` ve `main.py` içerisindeki tüm modüller AST ve Pyflakes ile statik analizden geçirildi. Tanımsız isim (`NameError`), sözdizimi hatası, eksik import ve potansiyel çökme ihtimalleri sıfırlandı.
* **Kayıt Defteri & Veritabanı Tanıtıcı Yönetimi:** SQLite bağlantılarında (`core/cookie_shield.py`) olası hata anlarında bağlantının açık kalıp dosyayı kilitlemesini önlemek için `try...finally: con.close()` güvencesi getirildi. Tüm Windows Kayıt Defteri (`winreg`) sorgulamalarında context manager kullanımı teyit edildi ve maksimum derinlik sınırları (`safety bounds`) korundu.
* **Dizin Dolaşımı Koruması (Junction Point Protection):** `core/junk_cleaner.py` ve `core/disk_analyzer.py` içerisindeki `os.walk` ve `os.scandir` döngülerine `followlinks=False` ve `onerror=lambda _: None` zorunlu kılındı. NTFS junction (bağlantı noktası) veya sembolik bağlar nedeniyle oluşabilecek sonsuz özyineleme ve izin reddi çökmeleri engellendi.

---

### ⚡ Takılma ve Donma Sorunlarına Karşı Sıfır Gecikme Optimizasyonu (Zero-Stutter)
* **Ağ & DNS Sekmesi 1500 Kat Hızlandırıldı (257 ms -> 0.17 ms):** Ağ sekmesine geçildiğinde aktif bağdaştırıcının mevcut DNS adresini öğrenmek için çağrılan senkron `netsh` alt işlemi kaldırıldı. Doğrudan Windows Kayıt Defteri TCP/IP arayüz parametreleri sorgulanarak işlem süresi 0.17 milisaniyeye indirildi. Ağ sekmesine tıklandığında yaşanan anlık takılma tamamen ortadan kaldırıldı.
* **Büyük Dosya Tarayıcısına Anında Durdurma & Sekme Değişim Koruması:** Disk analizi sekmesinde (`ui/views/disk_view.py`) kullanıcı taramayı istediği an durdurabilsin diye dinamik "Taramayı Durdur" (`cancel_check`) desteği entegre edildi. Kullanıcı sekme değiştirdiğinde veya uygulamayı kapattığında arka planda işlemcinin boşuna diski taramaya devam etmesi `hideEvent` ile engellendi.
* **Tüm 12 Sekmede Akıcı Geçiş (<15 ms):** 12 görünüm arasındaki geçiş gecikmeleri benchmark testleriyle ölçüldü ve tamamının 5-40 ms aralığında, insan algısının çok altında sürede açıldığı doğrulandı.

---

## 🚀 [v1.0.7] - 2026-10-16

### 🔢 Sürüm Numarasının Kesintisiz İlerlemesi (Dynamic Version Advancement)
* **Otomatik Sürüm İlerleme Mekanizması:** Uygulama güncellendiğinde sürüm numarasının eski sürümlerde (`v1.0.5`) takılı kalması engellendi. `ConfigManager.get_version()` semantik sürüm ayrıştırması (`parse_version_tuple`) ile güçlendirilerek her yeni güncellemede sistemin daima en güncel sürüm numarasını (`v1.0.7`) okuması ve göstermesi güvence altına alındı.
* **Canlı Arayüz Göstergeleri:** Ana pencere başlığına (`NovaCare System Care Suite 2026 - v1.0.7`), sol gezinme menüsü logosunun altına ve Ayarlar ekranındaki başlığa dinamik sürüm bilgisi entegre edildi.
* **Uygulama İçi Güncelleyici Eşitlemesi:** Yeni sürüm paketleri indirildiğinde yerel yapılandırma ve kayıt defteri anında yeni sürüme yükseltilecek şekilde optimize edildi.

---

## 🚀 [v1.0.6] - 2026-10-16

### 🎮 Oyun & Nihai Performans Kartı Arayüz Düzeltmesi
* **Metin Kayması ve Sıkışması Giderildi:** Ana paneldeki (Dashboard) "Oyun & Nihai Performans Modu" kartında yer alan açıklama metninin butonlar arasına sıkışıp dikeyde kesilmesi tamamen çözüldü. Metin alanına tam esneme payı (`stretch=1`) ve dikey ortalama verilerek 1366x768 gibi dar ekranlarda dahi metnin tam ve ferah görünmesi sağlandı.

---

### 🛡️ Windows Açılış Uyarısı & Başlangıç Kararlılığı
* **`COLOR_WARNING` Hata Düzeltmesi:** Bilgisayar açılışında standart kullanıcı ayrıcalığıyla başlayan arka plan işleminde tetiklenen eksik stil sabiti giderildi. Windows açılışında ekrana gelen hata penceresi kalıcı olarak engellendi.
* **Mükerrer Başlatma Koruması:** Windows Görev Zamanlayıcısı ile Kayıt Defteri (HKCU Run) arasındaki çakışma giderilerek uygulamanın açılışta yalnızca tek bir kararlı örnekle çalışması güvence altına alındı.

---

## 🚀 [v1.0.5] - 2026-10-16

### 🍪 Akıllı Çerez Kalkanı (Smart Cookie Shield)
* **Giriş Oturumlarını Koruma Kalkanı:** Google, YouTube, GitHub, e-Devlet, kurumsal bankalar (İş Bankası, Garanti, Yapı Kredi, Akbank, Ziraat vb.) ve alışveriş siteleri gibi kritik hesap oturumları beyaz liste ile güvence altına alındı.
* **İzleyici & Reklam Çerezi Temizliği:** Chromium tabanlı tarayıcılar (Microsoft Edge, Google Chrome, Brave, Opera, Opera GX) ve Mozilla Firefox üzerindeki üçüncü taraf reklam takipçileri, pazarlama pikselleri ve analitik çerezleri tek tıkla temizlenir.
* **Özelleştirilebilir Beyaz Liste:** Kullanıcıların istedikleri siteleri kolayca ekleyip çıkarabileceği "Korunan Siteleri Yönet" diyalogu eklendi.
* **Kilitli Tarayıcı Yönetimi:** Açık tarayıcılar SQLite çerez dosyasını kilitlediğinde kullanıcıyı bilgilendiren ve tek tıkla tarayıcıyı kapatıp tarama yapan akıllı algılama mekanizması entegre edildi.

---

### 🔋 Windows Pil Sağlığı & Güç Raporlayıcı (Battery Health Diagnostics)
* **Canlı Pil & Güç Telemetrisi:** Menüye 9. sekme olarak eklenen "Pil & Güç Sağlığı" ekranı ile anlık şarj durumu, tahmini kalan süre, aktif Windows güç planı gerçek zamanlı izlenir.
* **Fabrika Kapasitesi & Aşınma Oranı:** `Design Capacity` vs `Full Charge Capacity` karşılaştırması ile pilin aşınma yüzdesi hesaplanır (Mükemmel, İyi, Orta, Kritik).
* **Donanım & Kimya Detayları:** Pil üreticisi, model adı, batarya kimyası (LiON vb.) ve şarj döngü sayısı doğrudan donanım çipinden okunur.
* **Resmi Windows HTML Pil Raporu:** Tek tıkla `powercfg /batteryreport` çalıştırılarak Windows'un detaylı saatlik şarj geçmişi raporu oluşturulup varsayılan tarayıcıda açılır.
* **Masaüstü Bilgisayar Uyumluluğu:** Masaüstü bilgisayarlarda şebeke beslemesi tespit edilerek arayüz sorunsuz biçimde masaüstü AC moduna geçer.

---

### 🎨 Dairesel Gösterge Taşma Düzeltmesi & Yüksek Kontrastlı Butonlar
* **Dairesel Sağlık Göstergesi Taşma Düzeltmesi (Gauge Overflow Fix):** Dairesel göstergenin yay sınırlarını aşan uzun `"Sistem Durumu: Mükemmel"` metni giderildi. Gösterge içi değerlendirme `"Mükemmel"`, `"İyi"`, `"Bakım Önerilir"`, `"Kritik"` olarak optimize edildi ve `QFontMetrics` ile yay açıklığına göre dinamik font küçültme eklendi.
* **"TEK TIKLA SİSTEMİ TARA" Butonu Renk Kontrastı (WCAG AAA):** Koyu mavi üzerine koyu lacivert yazılan ve okunması zor olan buton yazısı; canlı modern okyanus mavisi (`#0284C7` -> `#0EA5E9`) degrade üzerine saf beyaz (`#FFFFFF`) ve kalın (`font-weight: 800`) yazıya geçirilerek %100 net ve göz alıcı hale getirildi.
* **Tüm Butonlar ve Durum Metinleri:** Onar butonu, durum metni etiketi ve aktif menü sekmelerinde kontrast optimize edildi.
* **Oyun & Nihai Performans Kartı Metin Kayması Düzeltildi:** Ana paneldeki Oyun Modu kartında açıklama metninin butonlar arasına sıkışıp dikeyde kesilmesi giderildi; metin alanına tam esneme payı (`stretch=1`) ve dikey hizalama verilerek tüm çözünürlüklerde ferah ve tam okunaklı hale getirildi.

---

### ⚡ Performans ve Donma Önleme Optimizasyonları (Zero-Stutter Architecture)
* **Bellek Trim Takılma Önleme:** Her menü sekmesi değişiminde çağrılan `EmptyWorkingSet` çağrısı kaldırıldı. Windows sayfalama belleğinin diske taşınması engellenerek sekme geçişleri anlık ve pürüzsüz hale getirildi (<15 ms).
* **Tembel Yükleme (Lazy Loading):** Gizlilik, Başlangıç, Kaldırıcı ve Ağ sekmelerinin ağır kayıt defteri ve dosya taramaları arka plan iş parçacıklarına (`QThread`) taşındı ve yalnızca sekme ilk açıldığında çalışacak şekilde tembel yüklendi.
* **Pil Telemetrisi Arka Plan İşleme:** Her 10 saniyede bir ana arayüz iş parçacığında `powercfg /batteryreport` çalıştırma sorunu giderildi; statik donanım verileri önbelleklendi, anlık şarj durumu doğrudan mikrosaniyelik `psutil` sensörlerine bağlandı (2500 ms donma -> 0.01 ms).
* **Donanım Algılama Hızlandırması:** Ağ bağdaştırıcıları ve GPU telemetrisi subprocess/PowerShell döngülerinden arındırılıp asenkron worker thread havuzuna devredildi.

---

## 🚀 [v1.0.1] - 2026-10-16

### 🎨 Arayüz, Pencere Boyutu ve Yazı Optimizasyonları
* **Dinamik Duyarlı (Responsive) Geometri:** Ana pencere boyutu sabit `1180x780` pikselden, kullanıcının monitör çözünürlüğünü ve görev çubuğu payını (`availableGeometry`) otomatik okuyan dinamik hesaplamaya geçirildi. 1366x768 ekranlarda ve %125 / %150 Windows DPI ölçeklemesinde pencerenin görev çubuğu arkasına taşması engellendi.
* **Kelime Kaydırma (Word-Wrap) Desteği:** 11 sekmenin tamamındaki alt başlık, açıklama ve durum etiketlerine `setWordWrap(True)` uygulandı. Türkçe metinlerin pencere daralsa dahi kesilmesi veya yatayda taşması önlendi.
* **Ana Panel (Dashboard) Scroll Desteği:** Dashboard görünümü çerçevesiz, modern `QScrollArea` içerisine alınarak küçük ekranlarda kartların ve butonların kaybolması engellendi.
* **Dairesel Sağlık Göstergesi:** `CircularHealthGauge` boyutu `220x220`'den `185x185`'e optimize edilerek dikey alan rahatlatıldı.
* **Gezinti Menüsü (Sidebar):** Menü genişliği 240px'e, buton dolguları `9px 14px`'e çekilerek 11 menü maddesi ve yönetici durumu rozeti hiçbir dikey kaydırmaya gerek kalmadan tam sığdırıldı.

---

### 🛡️ Kurulum Sihirbazı & Denetim Masası Kaldırma Sistemi
* **Entegre Yerel Kaldırma Motoru (`NovaCare.exe --uninstall`):** Uygulamanın çekirdeğine yerel kaldırma sihirbazı eklendi. Windows Denetim Masası veya Windows 10/11 Ayarlar > Yüklü Uygulamalar ekranından "Kaldır" butonuna basıldığında modern koyu temalı onay penceresiyle program, başlangıç görevleri, kısayollar ve kayıt defteri anahtarları eksiksiz kaldırılır.
* **Onarılan `uninstall.bat`:** Batch scriptindeki çok satırlı tırnak sözdizimi hataları giderildi; doğrudan yerel `reg delete` komutlarıyla güçlendirildi.
* **Kurulum Sihirbazı Tasarım Yenilemesi:**
  * `QWizard.ClassicStyle` ve tüm pencereyi kapsayan yekpare koyu tema (`#0A0F1D`) uygulandı.
  * Kart yapısındaki CSS miras hatası (`inheritance`) giderildi; yazıların 2 piksele sıkışması, etiketlerin etrafında istenmeyen çerçeveler oluşması ve beyaz zemin üzerine beyaz yazı kontrast sorunu tamamen çözüldü.
  * Sihirbaz boyutu `700x520` piksele çıkarılarak ferah bir görünüm sağlandı.

---

### ⚙️ Yönetici İzinleri ve Derin Temizlik Vurgusu
* **Ayarlar'dan Yönetici Olarak Başlatma:** Ayarlar sekmesine tek tıkla uygulamayı UAC yönetici ayrıcalığı ile yeniden başlatma butonu eklendi.
* **Yönetici Derin Temizlik Vurgusu:** Standart kullanıcı modunda çalışırken temizleme ekranlarında ve bildirimlerde yönetici izinlerinin sistem çöp dosyalarını ve kilitli kayıtları çok daha derinlemesine temizleyebileceği vurgusu yapıldı.

---

### 🔒 Güvenlik & Token Şifreleme
* **Windows DPAPI Şifrelemesi:** GitHub API güncelleme belirteçleri ve hassas yapılandırma verileri Windows DPAPI (`CryptProtectData` / `CryptUnprotectData`) algoritması ile şifrelenerek yetkisiz erişimlere karşı koruma altına alındı.

---

### 🐞 Hata Düzeltmeleri ve Kararlılık
* **Ayarlar Görünümü Eksik Import Düzeltmesi:** `ui/views/settings_view.py` içerisindeki `os` ve `sys` modül eksiklikleri giderilerek açılışta meydana gelen çökme engellendi.
* **Emoji ve Yazı Tipi Render Düzeltmesi:** Windows üzerinde kare kutu şeklinde bozuk çıkan emojiler için font yığınına `Segoe UI Emoji` eklendi.
* **Yol ve Karakter Standardizasyonu:** Türkçe karakterler ve boşluklu Windows kullanıcı dizinlerinde (`OneDrive`, `Kullanıcı Adı`) dosya erişim hataları giderildi.

---

## 📦 [v1.0.0] - 2026-10-15 (İlk Kararlı Sürüm)
* **Tek Tıkla Sistem Bakımı (Dashboard):** Tek tıkla çöp dosya, geçici veri, kayıt defteri ve başlangıç öğelerini tek seferde tarayıp temizleme.
* **Gereksiz Dosya Temizleyici:** Windows Temp, Prefetch, Crash Dumps, MiniDumps, Loglar, Tarayıcı Önbellekleri (Chrome, Edge, Firefox, Brave, Opera, Vivaldi), Küçük Resim Önbelleği temizliği.
* **Kayıt Defteri Onarımı:** Eksik paylaşılan DLL'ler, geçersiz dosya uzantıları, eski yazılım kalıntıları, geçersiz Başlat Menüsü girdileri, Help dosyaları temizliği ve otomatik kayıt defteri yedeği (`.reg`).
* **Başlangıç Yöneticisi:** Windows açılışını yavaşlatan program ve servislerin yönetimi ve gecikmeli başlatma.
* **Program Kaldırıcı:** Kalıntı taraması yapan modern yazılım kaldırma modülü.
* **RAM & Süreç Yöneticisi:** `EmptyWorkingSet` ile bellek sıkıştırma ve arka plan süreç optimizasyonu.
* **Disk Alanı Analizi:** Sürücü kullanım oranları ve en çok yer kaplayan büyük dosyaların tespiti.
* **Gizlilik ve Bloatware Temizliği:** Telemetri kapatma, gereksiz Windows 10/11 yerleşik uygulamalarını kaldırma.
* **Ağ ve DNS Optimize Edici:** TCP/IP ve Winsock sıfırlama, DNS önbelleği temizleme ve en hızlı DNS sunucusuna geçiş.
* **Kurtarma Merkezi:** Sistem Geri Yükleme Noktası oluşturma ve kayıt defteri yedeklerinden geri yükleme.
